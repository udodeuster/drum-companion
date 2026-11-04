from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from math import isfinite
from queue import Empty
from threading import Event, RLock, Thread
from typing import Callable, Mapping

from drum_companion.audio.analysis import AudioAnalyzer
from drum_companion.audio.groove import (
    GrooveFollower,
    STYLE_PROFILES,
    generate_accompaniment,
    saved_groove_to_pattern,
)
from drum_companion.audio.input import CaptureError, MicrophoneCapture
from drum_companion.audio.output import OutputError, PlaybackCoordinator, SampleOutput
from drum_companion.audio.scheduler import GrooveScheduler
from drum_companion.groove_library import INSTRUMENTS, GrooveLibrary, SavedGroove
from drum_companion.models import GrooveDecision


class LiveControlError(RuntimeError):
    """Raised when a live-control request cannot be applied."""


class DeviceRestartRequired(LiveControlError):
    """Raised when an audio device setting changes during an active session."""


@dataclass(frozen=True)
class LiveSettings:
    input_device: int | None = None
    output_device: int | None = None
    selected_groove_id: str | None = None
    drums_enabled: bool = True
    style: str = "rock"
    feel: str = "tight"
    phrase: str = "verse"
    intensity: float = 0.8
    master_level: float = 0.75
    onset_timeout_bars: int = 1
    min_tempo_bpm: int = 40
    max_tempo_bpm: int = 140
    muted: bool = False
    lock_tempo: bool = False


class LiveAudioController:
    """Own a background audio session and serialize runtime settings updates."""

    _device_fields = frozenset({"input_device", "output_device", "drums_enabled"})
    _setting_fields = frozenset(LiveSettings.__dataclass_fields__)
    _phrases = frozenset({"verse", "chorus", "bridge"})

    def __init__(
        self,
        settings: LiveSettings | None = None,
        *,
        capture_factory: Callable[..., MicrophoneCapture] = MicrophoneCapture,
        output_factory: Callable[..., SampleOutput] = SampleOutput,
        groove_library: GrooveLibrary | None = None,
    ) -> None:
        self._lock = RLock()
        self._settings = settings or LiveSettings()
        self._capture_factory = capture_factory
        self._output_factory = output_factory
        self._groove_library = groove_library or GrooveLibrary()
        self._state = "stopped"
        self._error: str | None = None
        self._output_error: str | None = None
        self._thread: Thread | None = None
        self._stop_event = Event()
        self._capture: MicrophoneCapture | None = None
        self._output: SampleOutput | None = None
        self._last_detected_tempo_bpm: float | None = None
        self._preview_state = "stopped"
        self._preview_error: str | None = None
        self._preview_tempo_bpm: float | None = None
        self._preview_draft: SavedGroove | None = None
        self._preview_thread: Thread | None = None
        self._preview_stop_event = Event()
        self._preview_output: SampleOutput | None = None
        self._status = {
            "tempo_bpm": None,
            "tempo_confidence": 0.0,
            "combined_energy": 0.0,
            "signal_active": False,
            "pattern": [],
        }
        self._validate_settings(self._settings)

    @property
    def settings(self) -> LiveSettings:
        with self._lock:
            return self._settings

    def start(self) -> None:
        with self._lock:
            if self._preview_thread is not None and self._preview_thread.is_alive():
                raise LiveControlError("Stop the groove preview before starting the live session")
            if self._thread is not None and self._thread.is_alive():
                raise LiveControlError("The live session is already active")
            self._stop_event = Event()
            self._state = "starting"
            self._error = None
            self._output_error = None
            self._status = {
                "tempo_bpm": None,
                "tempo_confidence": 0.0,
                "combined_energy": 0.0,
                "signal_active": False,
                "pattern": [],
            }
            self._thread = Thread(target=self._run, name="drum-companion-audio", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            thread = self._thread
            if thread is None or not thread.is_alive():
                if self._state != "error":
                    self._state = "stopped"
                return
            self._state = "stopping"
            self._stop_event.set()

        thread.join(timeout)
        if thread.is_alive():
            raise LiveControlError("The live audio worker did not stop in time")

    def start_preview(self, values: Mapping[str, object]) -> dict[str, object]:
        draft = self._normalize_preview_draft(values)
        tempo_bpm = self._normalize_preview_tempo(values.get("tempo_bpm"))
        with self._lock:
            if self._state in {"starting", "running", "stopping"} or (
                self._thread is not None and self._thread.is_alive()
            ):
                raise LiveControlError(
                    "Stop the live session before starting the groove preview"
                )
            if self._preview_thread is not None and self._preview_thread.is_alive():
                raise LiveControlError("The groove preview is already active")
            if tempo_bpm is None:
                tempo_bpm = self._last_detected_tempo_bpm or 100.0
            self._preview_draft = draft
            self._preview_tempo_bpm = tempo_bpm
            self._preview_error = None
            self._preview_state = "starting"
            self._preview_stop_event = Event()
            self._preview_thread = Thread(
                target=self._run_preview,
                name="drum-companion-preview",
                daemon=True,
            )
            self._preview_thread.start()
        return self.snapshot()

    def update_preview(self, values: Mapping[str, object]) -> dict[str, object]:
        draft = self._normalize_preview_draft(values)
        tempo_bpm = self._normalize_preview_tempo(values.get("tempo_bpm"))
        with self._lock:
            if self._preview_state not in {"starting", "running"}:
                raise LiveControlError("The groove preview is not active")
            self._preview_draft = draft
            if tempo_bpm is not None:
                self._preview_tempo_bpm = tempo_bpm
        return self.snapshot()

    def stop_preview(self, timeout: float = 5.0) -> dict[str, object]:
        with self._lock:
            thread = self._preview_thread
            if thread is None or not thread.is_alive():
                if self._preview_state != "error":
                    self._preview_state = "stopped"
                return self.snapshot()
            self._preview_state = "stopping"
            self._preview_stop_event.set()

        thread.join(timeout)
        if thread.is_alive():
            raise LiveControlError("The groove preview worker did not stop in time")
        return self.snapshot()

    def update_settings(self, values: Mapping[str, object]) -> dict[str, object]:
        unknown = set(values) - self._setting_fields
        if unknown:
            raise ValueError(f"Unsupported setting(s): {', '.join(sorted(unknown))}")

        normalized = {name: self._normalize_setting(name, value) for name, value in values.items()}
        if normalized.get("selected_groove_id") is not None:
            selected = self._groove_library.get_groove(normalized["selected_groove_id"])
            if selected is None:
                raise ValueError("The selected saved groove does not exist")
        with self._lock:
            if self._state in {"starting", "running", "stopping"} and self._device_fields.intersection(normalized):
                raise DeviceRestartRequired("Stop the live session before changing audio devices or drum playback")
            candidate = replace(self._settings, **normalized)
            self._validate_settings(candidate)
            self._settings = candidate
            output = self._output
            preview_output = self._preview_output
            settings = self._settings

        if output is not None:
            if "master_level" in normalized:
                output.set_master_level(settings.master_level)
            if "muted" in normalized:
                output.set_muted(settings.muted)
        if preview_output is not None:
            if "master_level" in normalized:
                preview_output.set_master_level(settings.master_level)
            if "muted" in normalized:
                preview_output.set_muted(settings.muted)
        return asdict(settings)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            preview_tempo = self._preview_tempo_bpm
            if preview_tempo is None:
                preview_tempo = self._last_detected_tempo_bpm or 100.0
            return {
                "state": self._state,
                "running": self._state in {"starting", "running", "stopping"},
                "error": self._error,
                "output_error": self._output_error,
                "last_tempo_bpm": self._last_detected_tempo_bpm,
                "preview": {
                    "state": self._preview_state,
                    "running": self._preview_state in {"starting", "running", "stopping"},
                    "error": self._preview_error,
                    "tempo_bpm": preview_tempo,
                    "draft": (
                        {
                            "tracks": {
                                instrument: list(self._preview_draft.tracks[instrument])
                                for instrument in INSTRUMENTS
                            },
                            "levels": dict(self._preview_draft.levels),
                        }
                        if self._preview_draft is not None
                        else None
                    ),
                },
                "settings": asdict(self._settings),
                **self._status,
            }

    def list_saved_grooves(self) -> list[dict[str, object]]:
        return [groove.to_dict() for groove in self._groove_library.list_grooves()]

    def automatic_groove_pattern(self) -> list[str]:
        with self._lock:
            current = self._status["pattern"]
            settings = self._settings
        if current:
            return list(current)
        return generate_accompaniment(
            settings.phrase,
            settings.style,
            settings.feel,
            settings.intensity,
        )

    def save_saved_groove(self, values: Mapping[str, object]) -> dict[str, object]:
        allowed = {"id", "name", "tracks", "levels"}
        if set(values) - allowed or not {"name", "tracks", "levels"}.issubset(values):
            raise ValueError("A groove must contain name, tracks, and levels, with only an optional id")
        if not isinstance(values["tracks"], Mapping) or not isinstance(values["levels"], Mapping):
            raise ValueError("Groove tracks and levels must be objects")
        if "id" in values:
            groove = SavedGroove(
                id=values["id"],
                name=values["name"],
                tracks=values["tracks"],
                levels=values["levels"],
            )
        else:
            groove = SavedGroove.create(
                name=values["name"],
                tracks=values["tracks"],
                levels=values["levels"],
            )
        self._groove_library.save_groove(groove)
        return groove.to_dict()

    def delete_saved_groove(self, groove_id: object) -> dict[str, object]:
        if not isinstance(groove_id, str):
            raise ValueError("A groove id is required")
        with self._lock:
            if self._groove_library.get_groove(groove_id) is None:
                raise LookupError("The saved groove does not exist")
            # Fall back to Auto before deleting so a running session never sees a missing groove.
            if self._settings.selected_groove_id == groove_id:
                self._settings = replace(self._settings, selected_groove_id=None)
            self._groove_library.delete_groove(groove_id)
        return {"settings": asdict(self._settings)}

    @staticmethod
    def _normalize_preview_draft(values: Mapping[str, object]) -> SavedGroove:
        if set(values) - {"tracks", "levels", "tempo_bpm"} or not {
            "tracks",
            "levels",
        }.issubset(values):
            raise ValueError("A preview draft must contain tracks and levels")
        if not isinstance(values["tracks"], Mapping) or not isinstance(
            values["levels"], Mapping
        ):
            raise ValueError("Preview draft tracks and levels must be objects")
        return SavedGroove.create("Preview", values["tracks"], values["levels"])

    @staticmethod
    def _normalize_preview_tempo(value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Preview tempo must be a number between 30 and 300 BPM")
        tempo_bpm = float(value)
        if not isfinite(tempo_bpm) or not 30.0 <= tempo_bpm <= 300.0:
            raise ValueError("Preview tempo must be between 30 and 300 BPM")
        return tempo_bpm

    def _run_preview(self) -> None:
        output: SampleOutput | None = None
        try:
            settings = self.settings
            output = self._output_factory(device=settings.output_device)
            output.set_master_level(settings.master_level)
            output.set_muted(settings.muted)
            output.start()
            if output.sample_bank is None:
                raise OutputError("Output sample bank is not loaded")
            with self._lock:
                self._preview_output = output
                self._preview_state = "running"

            sample_rate = output.sample_bank.sample_rate
            lead_in_frames = round(0.1 * sample_rate)
            draft, tempo_bpm = self._preview_values()
            pattern = saved_groove_to_pattern(draft)
            scheduler = GrooveScheduler(
                pattern,
                tempo_bpm=tempo_bpm,
                sample_rate=sample_rate,
                start_frame=output.frame_position + lead_in_frames,
                track_levels=draft.levels,
            )

            while not self._preview_stop_event.is_set():
                draft, tempo_bpm = self._preview_values()
                pattern = saved_groove_to_pattern(draft)
                settings = self.settings
                decision = GrooveDecision(
                    tempo_bpm=tempo_bpm,
                    tempo_confidence=1.0,
                    effective_intensity=settings.intensity,
                    pattern=pattern,
                    holding_stable_tempo=False,
                    signal_active=True,
                    feel=settings.feel,
                )
                scheduler.update_decision(
                    decision,
                    pattern=pattern,
                    track_levels=draft.levels,
                )
                for scheduled in scheduler.schedule_next_bar():
                    if scheduled.frame_position >= output.frame_position:
                        output.schedule(scheduled.event, scheduled.frame_position)

                schedule_frame = scheduler.next_bar_frame - lead_in_frames
                while (
                    not self._preview_stop_event.is_set()
                    and output.frame_position < schedule_frame
                ):
                    if output.callback_error:
                        raise OutputError(output.callback_error)
                    self._preview_stop_event.wait(0.02)
        except Exception as exc:
            with self._lock:
                self._preview_error = str(exc)
                self._preview_state = "error"
        finally:
            if output is not None:
                try:
                    output.stop()
                except Exception as exc:
                    with self._lock:
                        self._preview_error = str(exc)
                        self._preview_state = "error"
            with self._lock:
                self._preview_output = None
                if self._preview_state != "error":
                    self._preview_state = "stopped"

    def _preview_values(self) -> tuple[SavedGroove, float]:
        with self._lock:
            if self._preview_draft is None or self._preview_tempo_bpm is None:
                raise LiveControlError("The groove preview has no draft or tempo")
            return self._preview_draft, self._preview_tempo_bpm

    def _run(self) -> None:
        capture: MicrophoneCapture | None = None
        output: SampleOutput | None = None
        try:
            settings = self.settings
            capture = self._capture_factory(device=settings.input_device)
            with self._lock:
                self._capture = capture
            capture.start()

            coordinator: PlaybackCoordinator | None = None
            if settings.drums_enabled:
                output = self._output_factory(device=settings.output_device)
                with self._lock:
                    self._output = output
                output.set_master_level(settings.master_level)
                output.set_muted(settings.muted)
                try:
                    output.start()
                    coordinator = PlaybackCoordinator(output)
                except OutputError as exc:
                    self._output_error = str(exc)
                    self._stop_output(output)
                    output = None
                    with self._lock:
                        self._output = None

            analyzer: AudioAnalyzer | None = None
            follower = GrooveFollower(
                style=settings.style,
                feel=settings.feel,
                intensity=settings.intensity,
                phrase=settings.phrase,
                onset_timeout_bars=settings.onset_timeout_bars,
                lock_pulse_octave=settings.drums_enabled,
                lock_tempo=settings.lock_tempo,
            )
            with self._lock:
                self._state = "running"

            while not self._stop_event.is_set():
                try:
                    block = capture.read(timeout=0.25)
                except Empty:
                    continue

                settings = self.settings
                follower.style = settings.style
                follower.feel = settings.feel
                follower.intensity = settings.intensity
                follower.phrase = settings.phrase
                follower.onset_timeout_bars = settings.onset_timeout_bars
                follower.lock_tempo = settings.lock_tempo
                if output is not None:
                    output.set_master_level(settings.master_level)
                    output.set_muted(settings.muted)

                if analyzer is None:
                    analyzer = AudioAnalyzer(
                        block.sample_rate,
                        min_tempo_bpm=settings.min_tempo_bpm,
                        max_tempo_bpm=settings.max_tempo_bpm,
                    )
                else:
                    analyzer.set_tempo_range(settings.min_tempo_bpm, settings.max_tempo_bpm)
                observation = analyzer.process_block(block)
                if observation is None:
                    continue

                decision = follower.update(observation)
                with self._lock:
                    if decision.tempo_bpm is not None:
                        self._last_detected_tempo_bpm = decision.tempo_bpm
                if coordinator is not None:
                    selected_groove = (
                        self._groove_library.get_groove(settings.selected_groove_id)
                        if settings.selected_groove_id is not None
                        else None
                    )
                    if settings.selected_groove_id is not None and selected_groove is None:
                        raise LiveControlError("The selected saved groove no longer exists")
                    coordinator.update(decision, selected_groove)
                with self._lock:
                    self._status = {
                        "tempo_bpm": decision.tempo_bpm,
                        "tempo_confidence": decision.tempo_confidence,
                        "combined_energy": observation.combined_energy,
                        "signal_active": decision.signal_active,
                        "pattern": list(decision.pattern),
                    }
        except (CaptureError, OutputError, OSError, ValueError) as exc:
            with self._lock:
                self._error = str(exc)
                self._state = "error"
        except Exception as exc:
            with self._lock:
                self._error = str(exc)
                self._state = "error"
        finally:
            if capture is not None:
                self._stop_capture(capture)
            if output is not None:
                self._stop_output(output)
            with self._lock:
                self._capture = None
                self._output = None
                if self._state != "error":
                    self._state = "stopped"

    @staticmethod
    def _stop_capture(capture: MicrophoneCapture) -> None:
        try:
            capture.stop()
        except Exception:
            pass

    @staticmethod
    def _stop_output(output: SampleOutput) -> None:
        try:
            output.stop()
        except Exception:
            pass

    @classmethod
    def _normalize_setting(cls, name: str, value: object) -> object:
        if name in {"input_device", "output_device"}:
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative device index or null")
            return value
        if name == "selected_groove_id":
            if value is None:
                return None
            if not isinstance(value, str) or not value:
                raise ValueError("selected_groove_id must be a UUID string or null")
            from uuid import UUID

            try:
                if str(UUID(value)) != value:
                    raise ValueError
            except ValueError as exc:
                raise ValueError("selected_groove_id must be a canonical UUID string or null") from exc
            return value
        if name in {"drums_enabled", "muted", "lock_tempo"}:
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a boolean")
            return value
        if name == "style":
            if not isinstance(value, str) or value.lower() not in STYLE_PROFILES:
                raise ValueError(f"style must be one of {', '.join(sorted(STYLE_PROFILES))}")
            return value.lower()
        if name == "feel":
            if not isinstance(value, str) or value.lower() not in {"tight", "relaxed"}:
                raise ValueError("feel must be tight or relaxed")
            return value.lower()
        if name == "phrase":
            if not isinstance(value, str) or value.lower() not in cls._phrases:
                raise ValueError(f"phrase must be one of {', '.join(sorted(cls._phrases))}")
            return value.lower()
        if name == "onset_timeout_bars":
            if isinstance(value, bool) or not isinstance(value, int) or value not in {0, 1, 2, 4}:
                raise ValueError("onset_timeout_bars must be one of 0, 1, 2, or 4 bars")
            return value
        if name in {"min_tempo_bpm", "max_tempo_bpm"}:
            if isinstance(value, bool) or not isinstance(value, int) or not 30 <= value <= 300:
                raise ValueError(f"{name} must be a whole number between 30 and 300")
            return value
        if name in {"intensity", "master_level"}:
            if isinstance(value, bool):
                raise ValueError(f"{name} must be a number between 0.0 and 1.0")
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be a number between 0.0 and 1.0") from exc
            if not isfinite(number) or not 0.0 <= number <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0")
            return number
        raise ValueError(f"Unsupported setting: {name}")

    @classmethod
    def _validate_settings(cls, settings: LiveSettings) -> None:
        for name, value in asdict(settings).items():
            cls._normalize_setting(name, value)
        if settings.max_tempo_bpm < 2 * settings.min_tempo_bpm:
            raise ValueError("max_tempo_bpm must be at least twice min_tempo_bpm")