"""Sample loading, audio-device output, and scheduled drum playback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Mapping

import librosa
import numpy as np
import soundfile as sf
import sounddevice as sd

from drum_companion.audio.groove import DrumEvent, kick_only_pattern, saved_groove_to_pattern
from drum_companion.audio.scheduler import GrooveScheduler
from drum_companion.groove_library import INSTRUMENTS, SavedGroove
from drum_companion.models import GrooveDecision

_STARTER_KIT_GAINS = {
    "kick": 1.25,
    "tom_high": 0.75,
    "tom_low": 0.75,
    "rimshot": 0.8,
    "clap": 0.8,
    "ride": 0.6,
    "shaker": 0.5,
    "cowbell": 0.6,
}


class AudioAssetError(RuntimeError):
    """Raised when the bundled starter kit cannot be loaded safely."""


class OutputError(RuntimeError):
    """Raised when an output device cannot be selected or opened."""


@dataclass(frozen=True)
class OutputDevice:
    """Describe an available audio output device and its capabilities."""
    index: int
    name: str
    channels: int
    sample_rate: int


def list_output_devices(device_query=sd.query_devices) -> list[OutputDevice]:
    """List output devices.

    Args:
        device_query (object): Callable that returns the available audio devices.

    Returns:
        list[OutputDevice]: The result produced by this operation.
    """
    return [
        OutputDevice(
            index=index,
            name=str(device["name"]),
            channels=int(device["max_output_channels"]),
            sample_rate=int(device["default_samplerate"]),
        )
        for index, device in enumerate(device_query())
        if int(device["max_output_channels"]) > 0
    ]


class SampleBank:
    """Hold decoded drum samples for use by the output mixer."""
    def __init__(
        self,
        samples: Mapping[str, np.ndarray],
        *,
        sample_rate: int,
        channels: int,
    ) -> None:
        """Initialize the instance.

        Args:
            samples (Mapping[str, np.ndarray]): Sequence of audio samples to process.
            sample_rate (int): Audio sampling rate in samples per second.
            channels (int): Number of audio channels supported or requested.

        Returns:
            None: No value is returned.
        """
        if sample_rate <= 0 or channels not in (1, 2):
            raise ValueError("sample_rate must be positive and channels must be mono or stereo")
        self.sample_rate = sample_rate
        self.channels = channels
        self.samples: dict[str, np.ndarray] = {}
        for instrument, audio in samples.items():
            normalized = np.asarray(audio, dtype=np.float32)
            if normalized.ndim != 2 or normalized.shape[1] != channels:
                raise ValueError(f"Sample {instrument} must have {channels} channel(s)")
            if normalized.shape[0] == 0 or not np.isfinite(normalized).all():
                raise ValueError(f"Sample {instrument} must contain finite audio")
            normalized = normalized.copy()
            normalized.setflags(write=False)
            self.samples[instrument] = normalized

    @classmethod
    def load_starter_kit(
        cls,
        asset_directory: str | Path,
        *,
        sample_rate: int,
        channels: int,
    ) -> "SampleBank":
        """Load starter kit.

        Args:
            asset_directory (str | Path): Directory containing bundled audio
                sample assets.
            sample_rate (int): Audio sampling rate in samples per second.
            channels (int): Number of audio channels supported or requested.

        Returns:
            'SampleBank': The result produced by this operation.
        """
        asset_directory = Path(asset_directory)
        manifest_path = asset_directory / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AudioAssetError(f"Unable to read drum kit manifest: {exc}") from exc

        if manifest.get("license") != "CC0-1.0":
            raise AudioAssetError("Starter kit manifest must declare CC0-1.0")
        samples: dict[str, np.ndarray] = {}
        for item in manifest.get("assets", []):
            if item.get("license") != "CC0-1.0" or not item.get("source_url"):
                raise AudioAssetError(f"Asset {item.get('file')} lacks approved provenance")
            try:
                audio, source_rate = sf.read(
                    asset_directory / item["file"],
                    dtype="float32",
                    always_2d=True,
                )
            except (OSError, RuntimeError) as exc:
                raise AudioAssetError(f"Unable to load {item.get('file')}: {exc}") from exc

            if int(source_rate) != sample_rate:
                audio = librosa.resample(
                    audio,
                    orig_sr=int(source_rate),
                    target_sr=sample_rate,
                    axis=0,
                )
            if audio.shape[1] != channels:
                if channels == 1:
                    audio = np.mean(audio, axis=1, keepdims=True, dtype=np.float32)
                elif audio.shape[1] == 1:
                    audio = np.repeat(audio, 2, axis=1)
                else:
                    audio = audio[:, :channels]

            peak = float(np.max(np.abs(audio)))
            if peak > 0.0:
                audio = audio * (0.95 / peak)
            audio *= _STARTER_KIT_GAINS.get(item["instrument"].replace(" ", "_"), 1.0)
            samples[item["instrument"].replace(" ", "_")] = audio

        expected = {
            "closed_hi-hat" if name == "closed_hat" else "open_hi-hat" if name == "open_hat" else name
            for name in INSTRUMENTS
        }
        if set(samples) != expected:
            raise AudioAssetError(f"Starter kit instruments must be {sorted(expected)}")
        samples["closed_hat"] = samples.pop("closed_hi-hat")
        samples["open_hat"] = samples.pop("open_hi-hat")
        return cls(samples, sample_rate=sample_rate, channels=channels)


class SampleMixer:
    """Mix scheduled drum events into output audio frames."""
    def __init__(self, sample_bank: SampleBank) -> None:
        """Initialize the instance.

        Args:
            sample_bank (SampleBank): Loaded collection of drum samples.

        Returns:
            None: No value is returned.
        """
        self.sample_bank = sample_bank

    def render_events(
        self,
        events: tuple[DrumEvent, ...] | list[DrumEvent],
        frame_count: int,
        *,
        master_level: float = 1.0,
        muted: bool = False,
        stopped: bool = False,
    ) -> np.ndarray:
        """Render events.

        Args:
            events (tuple[DrumEvent, ...] | list[DrumEvent]): Scheduled drum
                events to mix or
                process.
            frame_count (int): Number of output audio frames.
            master_level (float): Overall output level.
            muted (bool): Whether audio output should be muted.
            stopped (bool): Whether the associated stream has stopped.

        Returns:
            np.ndarray: The result produced by this operation.
        """
        if frame_count < 0:
            raise ValueError("frame_count must be non-negative")
        if not 0.0 <= master_level <= 1.0:
            raise ValueError("master_level must be between 0.0 and 1.0")
        output = np.zeros((frame_count, self.sample_bank.channels), dtype=np.float32)
        if muted or stopped or frame_count == 0:
            return output

        for event in events:
            if not 0.0 <= event.velocity <= 1.0:
                raise ValueError("event velocity must be between 0.0 and 1.0")
            if event.instrument not in self.sample_bank.samples:
                raise ValueError(f"No sample loaded for {event.instrument}")
            start = max(0, round(event.offset_seconds * self.sample_bank.sample_rate))
            if start >= frame_count:
                continue
            sample = self.sample_bank.samples[event.instrument]
            end = min(frame_count, start + sample.shape[0])
            output[start:end] += sample[: end - start] * event.velocity

        np.clip(output * master_level, -1.0, 1.0, out=output)
        return output


class SampleOutput:
    """Manage audio output and schedule samples on the selected device."""
    def __init__(
        self,
        device: int | None = None,
        *,
        asset_directory: str | Path | None = None,
        sample_bank: SampleBank | None = None,
        device_query=sd.query_devices,
        stream_factory=sd.OutputStream,
        block_size: int = 512,
        max_pending_events: int = 256,
    ) -> None:
        """Initialize the instance.

        Args:
            device (int | None): Audio device index or selected device.
            asset_directory (str | Path | None): Directory containing bundled
                audio sample
                assets.
            sample_bank (SampleBank | None): Loaded collection of drum samples.
            device_query (object): Callable that returns the available audio devices.
            stream_factory (object): Factory that creates the audio stream used
                by the capture.
            block_size (int): Number of audio frames per captured block.
            max_pending_events (int): Maximum number of future events retained by
                the scheduler.

        Returns:
            None: No value is returned.
        """
        if block_size <= 0 or max_pending_events <= 0:
            raise ValueError("block_size and max_pending_events must be positive")
        self.device = device
        self.asset_directory = Path(asset_directory) if asset_directory else (
            Path(__file__).resolve().parent.parent / "assets" / "drums"
        )
        self.sample_bank = sample_bank
        self._device_query = device_query
        self._stream_factory = stream_factory
        self._block_size = block_size
        self._events: Queue[tuple[int, DrumEvent]] = Queue(maxsize=max_pending_events)
        self._pending: list[tuple[int, DrumEvent]] = []
        self._active: list[tuple[np.ndarray, int, float]] = []
        self._stream: object | None = None
        self._frame_position = 0
        self._running = False
        self._muted = False
        self._master_level = 1.0
        self._gain_segments: tuple[tuple[int, int, float, float], ...] = ()
        self._callback_error: str | None = None

    @property
    def is_running(self) -> bool:
        """Handle is running.

        Returns:
            bool: The result produced by this operation.
        """
        return self._running

    @property
    def is_muted(self) -> bool:
        """Handle is muted.

        Returns:
            bool: The result produced by this operation.
        """
        return self._muted

    @property
    def master_level(self) -> float:
        """Handle master level.

        Returns:
            float: The result produced by this operation.
        """
        return self._master_level

    @property
    def frame_position(self) -> int:
        """Handle frame position.

        Returns:
            int: The result produced by this operation.
        """
        return self._frame_position

    @property
    def pending_event_count(self) -> int:
        """Handle pending event count.

        Returns:
            int: The result produced by this operation.
        """
        return self._events.qsize() + len(self._pending)

    @property
    def callback_error(self) -> str | None:
        """Handle callback error.

        Returns:
            str | None: The result produced by this operation.
        """
        return self._callback_error

    def set_master_level(self, level: float) -> None:
        """Set master level.

        Args:
            level (float): Output level to apply.

        Returns:
            None: No value is returned.
        """
        if not 0.0 <= level <= 1.0:
            raise ValueError("master level must be between 0.0 and 1.0")
        self._master_level = float(level)

    def set_muted(self, muted: bool) -> None:
        """Set muted.

        Args:
            muted (bool): Whether audio output should be muted.

        Returns:
            None: No value is returned.
        """
        self._muted = bool(muted)

    def schedule_gain_ramp(self, start_frame: int, end_frame: int, target_gain: float) -> None:
        """Schedule gain ramp.

        Args:
            start_frame (int): Output frame at which the operation starts.
            end_frame (int): Output frame at which it ends.
            target_gain (float): Target linear gain for the operation.

        Returns:
            None: No value is returned.
        """
        if start_frame < 0 or end_frame <= start_frame:
            raise ValueError("gain ramp frames must be non-negative and end after start")
        if not np.isfinite(target_gain) or not 0.0 <= target_gain <= 1.0:
            raise ValueError("target gain must be between 0.0 and 1.0")

        segments = self._gain_segments
        start_gain = self._gain_at_frame(start_frame, segments)
        retained: list[tuple[int, int, float, float]] = []
        for segment_start, segment_end, segment_from, segment_to in segments:
            if segment_start >= start_frame:
                break
            if segment_end <= start_frame:
                retained.append((segment_start, segment_end, segment_from, segment_to))
            else:
                retained.append((segment_start, start_frame, segment_from, start_gain))
                break
        retained.append((start_frame, end_frame, start_gain, float(target_gain)))
        self._gain_segments = tuple(retained)

    @staticmethod
    def _gain_at_frame(
        frame_position: int,
        segments: tuple[tuple[int, int, float, float], ...],
    ) -> float:
        """Handle gain at frame.

        Args:
            frame_position (int): Output-frame position associated with the event.
            segments (tuple[tuple[int, int, float, float], ...]): Audio segments
                or event
                intervals to process.

        Returns:
            float: The result produced by this operation.
        """
        gain = 1.0
        for start_frame, end_frame, start_gain, end_gain in segments:
            if frame_position < start_frame:
                break
            if frame_position < end_frame:
                progress = (frame_position - start_frame) / (end_frame - start_frame)
                return start_gain + (end_gain - start_gain) * progress
            gain = end_gain
        return gain

    def start(self) -> None:
        """Start the associated resource or event.

        Returns:
            None: No value is returned.
        """
        devices = list_output_devices(self._device_query)
        if not devices:
            raise OutputError("No audio output devices are available")
        selected = next((item for item in devices if item.index == self.device), None)
        if self.device is not None and selected is None:
            raise OutputError(f"Output device {self.device} is not available")
        if selected is None:
            selected = devices[0]

        channels = min(2, selected.channels)
        try:
            if self.sample_bank is None:
                self.sample_bank = SampleBank.load_starter_kit(
                    self.asset_directory,
                    sample_rate=selected.sample_rate,
                    channels=channels,
                )
            if self.sample_bank.sample_rate != selected.sample_rate or self.sample_bank.channels != channels:
                raise OutputError("Loaded sample format does not match the selected output device")

            self._stream = self._stream_factory(
                device=selected.index,
                channels=channels,
                samplerate=selected.sample_rate,
                dtype="float32",
                blocksize=self._block_size,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._running = True
            self._frame_position = 0
            self._callback_error = None
        except Exception as exc:
            self._close_stream()
            if isinstance(exc, OutputError):
                raise
            raise OutputError(f"Unable to start audio output: {exc}") from exc

    def schedule(self, event: DrumEvent, frame_position: int) -> None:
        """Schedule the associated resource or event.

        Args:
            event (DrumEvent): Scheduled audio event to process.
            frame_position (int): Output-frame position associated with the event.

        Returns:
            None: No value is returned.
        """
        if not self._running:
            raise OutputError("Audio output is not running")
        if frame_position < self._frame_position:
            raise ValueError("event frame_position is already in the past")
        try:
            self._events.put_nowait((frame_position, event))
        except Full as exc:
            raise OutputError("Audio event queue is full") from exc

    def stop(self) -> None:
        """Stop the associated resource or event.

        Returns:
            None: No value is returned.
        """
        self._running = False
        self._close_stream()
        self._gain_segments = ()
        self._pending.clear()
        self._active.clear()
        while True:
            try:
                self._events.get_nowait()
            except Empty:
                break

    def _audio_callback(self, outdata: np.ndarray, frames: int, time_info: object, status: object) -> None:
        """Handle audio callback.

        Args:
            outdata (np.ndarray): Output audio buffer filled by the audio callback.
            frames (int): Audio frames to process or render.
            time_info (object): Audio callback timing metadata provided by the
                audio backend.
            status (object): HTTP status code or controller status to report.

        Returns:
            None: No value is returned.
        """
        outdata.fill(0.0)
        if not self._running or self.sample_bank is None:
            return
        try:
            block_start = self._frame_position
            block_end = block_start + frames
            while True:
                try:
                    self._pending.append(self._events.get_nowait())
                except Empty:
                    break
            self._pending.sort(key=lambda item: item[0])

            future: list[tuple[int, DrumEvent]] = []
            for event_frame, event in self._pending:
                if event_frame < block_end:
                    samples = self.sample_bank.samples[event.instrument]
                    self._active.append((samples, max(event_frame, block_start), event.velocity))
                else:
                    future.append((event_frame, event))
            self._pending = future

            active_future: list[tuple[np.ndarray, int, float]] = []
            for samples, start_frame, velocity in self._active:
                sample_start = max(0, block_start - start_frame)
                output_start = max(0, start_frame - block_start)
                count = min(frames - output_start, samples.shape[0] - sample_start)
                if count > 0:
                    outdata[output_start : output_start + count] += (
                        samples[sample_start : sample_start + count] * velocity
                    )
                if sample_start + max(count, 0) < samples.shape[0]:
                    active_future.append((samples, start_frame, velocity))
            self._active = active_future
            gain = np.ones(frames, dtype=np.float32)
            frame_positions = np.arange(block_start, block_end, dtype=np.float64)
            for start_frame, end_frame, start_gain, end_gain in self._gain_segments:
                if start_frame >= block_end:
                    break
                if end_frame <= block_start:
                    gain.fill(end_gain)
                    continue
                gain[frame_positions >= end_frame] = end_gain
                ramp_mask = (frame_positions >= start_frame) & (frame_positions < end_frame)
                if np.any(ramp_mask):
                    progress = (frame_positions[ramp_mask] - start_frame) / (end_frame - start_frame)
                    gain[ramp_mask] = start_gain + (end_gain - start_gain) * progress

            np.clip(outdata * (gain[:, np.newaxis] * self._master_level), -1.0, 1.0, out=outdata)
            if self._muted:
                outdata.fill(0.0)
            self._frame_position = block_end
        except Exception as exc:
            outdata.fill(0.0)
            self._callback_error = str(exc)

    def _close_stream(self) -> None:
        """Handle close stream.

        Returns:
            None: No value is returned.
        """
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()


class PlaybackCoordinator:
    """Translate live groove decisions into a short queue of future audio events."""

    def __init__(
        self,
        output: SampleOutput,
        *,
        horizon_seconds: float = 1.0,
        lead_in_seconds: float = 0.1,
    ) -> None:
        """Initialize the instance.

        Args:
            output (SampleOutput): Audio output instance or destination.
            horizon_seconds (float): Look-ahead scheduling horizon in seconds.
            lead_in_seconds (float): Delay before the first scheduled event, in
                seconds.

        Returns:
            None: No value is returned.
        """
        if horizon_seconds <= 0 or lead_in_seconds < 0:
            raise ValueError("horizon must be positive and lead-in non-negative")
        self.output = output
        self.horizon_seconds = horizon_seconds
        self.lead_in_seconds = lead_in_seconds
        self.scheduler: GrooveScheduler | None = None

    def update(self, decision: GrooveDecision, groove: SavedGroove | None = None) -> int:
        """Handle update.

        Args:
            decision (GrooveDecision): Groove decision to apply.
            groove (SavedGroove | None): Groove data to process.

        Returns:
            int: The result produced by this operation.
        """
        if decision.tempo_bpm is None and self.scheduler is None:
            return 0
        if self.output.sample_bank is None:
            raise OutputError("Output sample bank is not loaded")
        pattern = saved_groove_to_pattern(groove) if groove is not None else decision.pattern
        if decision.kick_only:
            pattern = kick_only_pattern(pattern)
        track_levels = groove.levels if groove is not None else None
        if self.scheduler is None:
            if decision.tempo_bpm is None:
                return 0
            sample_rate = self.output.sample_bank.sample_rate
            self.scheduler = GrooveScheduler(
                pattern,
                tempo_bpm=decision.tempo_bpm,
                sample_rate=sample_rate,
                start_frame=self.output.frame_position + round(self.lead_in_seconds * sample_rate),
                track_levels=track_levels,
            )

        self.scheduler.update_decision(decision, pattern=pattern, track_levels=track_levels)
        sample_rate = self.output.sample_bank.sample_rate
        horizon_frame = self.output.frame_position + round(self.horizon_seconds * sample_rate)
        queued = 0
        while self.scheduler.next_bar_frame <= horizon_frame:
            for scheduled in self.scheduler.schedule_next_bar():
                if scheduled.frame_position < self.output.frame_position:
                    continue
                self.output.schedule(scheduled.event, scheduled.frame_position)
                queued += 1
        return queued