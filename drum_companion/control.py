from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from math import isfinite
from queue import Empty
from threading import Event, RLock, Thread
from typing import Callable, Mapping

from drum_companion.audio.analysis import AudioAnalyzer
from drum_companion.audio.groove import GrooveFollower, STYLE_PROFILES
from drum_companion.audio.input import CaptureError, MicrophoneCapture
from drum_companion.audio.output import OutputError, PlaybackCoordinator, SampleOutput


class LiveControlError(RuntimeError):
    """Raised when a live-control request cannot be applied."""


class DeviceRestartRequired(LiveControlError):
    """Raised when an audio device setting changes during an active session."""


@dataclass(frozen=True)
class LiveSettings:
    input_device: int | None = None
    output_device: int | None = None
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
    ) -> None:
        self._lock = RLock()
        self._settings = settings or LiveSettings()
        self._capture_factory = capture_factory
        self._output_factory = output_factory
        self._state = "stopped"
        self._error: str | None = None
        self._output_error: str | None = None
        self._thread: Thread | None = None
        self._stop_event = Event()
        self._capture: MicrophoneCapture | None = None
        self._output: SampleOutput | None = None
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

    def update_settings(self, values: Mapping[str, object]) -> dict[str, object]:
        unknown = set(values) - self._setting_fields
        if unknown:
            raise ValueError(f"Unsupported setting(s): {', '.join(sorted(unknown))}")

        normalized = {name: self._normalize_setting(name, value) for name, value in values.items()}
        with self._lock:
            if self._state in {"starting", "running", "stopping"} and self._device_fields.intersection(normalized):
                raise DeviceRestartRequired("Stop the live session before changing audio devices or drum playback")
            candidate = replace(self._settings, **normalized)
            self._validate_settings(candidate)
            self._settings = candidate
            output = self._output
            settings = self._settings

        if output is not None:
            if "master_level" in normalized:
                output.set_master_level(settings.master_level)
            if "muted" in normalized:
                output.set_muted(settings.muted)
        return asdict(settings)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "state": self._state,
                "running": self._state in {"starting", "running", "stopping"},
                "error": self._error,
                "output_error": self._output_error,
                "settings": asdict(self._settings),
                **self._status,
            }

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
                if coordinator is not None:
                    coordinator.update(decision)
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
        if name in {"drums_enabled", "muted"}:
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