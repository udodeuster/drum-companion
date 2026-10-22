from __future__ import annotations

from collections import deque
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from drum_companion.audio.input import AudioBlock
from drum_companion.models import AudioAnalysisObservation, PerformanceContext


def estimate_performance_context(
    tempo_hint: float,
    voice_energy: float,
    guitar_energy: float,
    phrase: str = "verse",
) -> PerformanceContext:
    """Create a simplified context for the manual/demo CLI mode."""
    if tempo_hint <= 0:
        raise ValueError("tempo_hint must be greater than zero")

    confidence = min(1.0, (voice_energy + guitar_energy) / 2.0 + 0.25)
    return PerformanceContext(
        tempo_bpm=tempo_hint,
        voice_energy=max(0.0, min(1.0, voice_energy)),
        guitar_energy=max(0.0, min(1.0, guitar_energy)),
        phrase=phrase,
        confidence=confidence,
    )


class AudioAnalyzer:
    """Produce rolling observations from audio blocks on a non-capture thread."""

    def __init__(
        self,
        sample_rate: int,
        *,
        window_seconds: float = 6.0,
        update_interval_seconds: float = 0.5,
        hop_length: int = 512,
        min_tempo_bpm: float = 60.0,
        max_tempo_bpm: float = 180.0,
    ) -> None:
        if sample_rate <= 0 or window_seconds <= 0 or update_interval_seconds <= 0:
            raise ValueError("sample rate and analysis durations must be positive")
        self.set_tempo_range(min_tempo_bpm, max_tempo_bpm)
        self.sample_rate = sample_rate
        self.window_samples = int(sample_rate * window_seconds)
        self.update_interval_seconds = update_interval_seconds
        self.hop_length = hop_length
        self._chunks: deque[np.ndarray] = deque()
        self._buffered_samples = 0
        self._processed_samples = 0
        self._last_analysis_seconds = 0.0
        self._last_emitted_onset = -1.0
        self._last_detected_onset = -1.0

    def set_tempo_range(self, min_tempo_bpm: float, max_tempo_bpm: float) -> None:
        # A range narrower than one octave could not fold every estimate into it.
        if min_tempo_bpm <= 0 or max_tempo_bpm < 2.0 * min_tempo_bpm:
            raise ValueError("tempo range must be positive and span at least one octave")
        self.min_tempo_bpm = float(min_tempo_bpm)
        self.max_tempo_bpm = float(max_tempo_bpm)

    def process_block(self, block: AudioBlock) -> AudioAnalysisObservation | None:
        if block.sample_rate != self.sample_rate:
            raise ValueError("audio block sample rate changed during analysis")

        samples = np.asarray(block.data, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return None
        if block.discontinuity:
            self._chunks.clear()
            self._buffered_samples = 0

        self._processed_samples += samples.size
        self._chunks.append(samples.copy())
        self._buffered_samples += samples.size
        self._trim_window()

        timestamp = self._processed_samples / self.sample_rate
        if timestamp - self._last_analysis_seconds < self.update_interval_seconds:
            return None
        self._last_analysis_seconds = timestamp

        window = np.concatenate(tuple(self._chunks))
        energy_window = window[-min(window.size, int(self.sample_rate * 0.75)) :]
        energy = float(np.sqrt(np.mean(np.square(energy_window, dtype=np.float64))))
        energy = float(np.clip(energy, 0.0, 1.0))
        signal_active = energy >= 0.008
        silence_duration = (
            timestamp - self._last_detected_onset if self._last_detected_onset >= 0 else timestamp
        )
        phrase_break_confidence = None
        if self._last_detected_onset >= 0 and silence_duration >= 1.0:
            phrase_break_confidence = float(np.clip((silence_duration - 1.0) / 1.5, 0.0, 1.0))

        if window.size < self.sample_rate * 2:
            return AudioAnalysisObservation(
                timestamp_seconds=timestamp,
                onset_times_seconds=(),
                tempo_bpm=None,
                tempo_confidence=0.0,
                combined_energy=energy,
                energy_confidence=1.0,
                signal_active=signal_active,
                phrase_break_confidence=phrase_break_confidence,
                discontinuity=block.discontinuity,
            )

        onset_envelope = librosa.onset.onset_strength(
            y=window,
            sr=self.sample_rate,
            hop_length=self.hop_length,
        )
        local_onsets = librosa.onset.onset_detect(
            onset_envelope=onset_envelope,
            sr=self.sample_rate,
            hop_length=self.hop_length,
            units="time",
            backtrack=False,
        )
        window_start = timestamp - window.size / self.sample_rate
        absolute_onsets = [window_start + float(onset) for onset in local_onsets]
        if absolute_onsets:
            self._last_detected_onset = absolute_onsets[-1]
            silence_duration = timestamp - self._last_detected_onset
            if silence_duration >= 1.0:
                phrase_break_confidence = float(np.clip((silence_duration - 1.0) / 1.5, 0.0, 1.0))
        new_onsets = tuple(
            onset
            for onset in absolute_onsets
            if onset > self._last_emitted_onset + 0.02 and onset <= timestamp
        )
        if new_onsets:
            self._last_emitted_onset = new_onsets[-1]

        tempo_values, _ = librosa.beat.beat_track(
            onset_envelope=onset_envelope,
            sr=self.sample_rate,
            hop_length=self.hop_length,
            units="time",
        )
        tempo_bpm = float(np.asarray(tempo_values).reshape(-1)[0])
        if np.isfinite(tempo_bpm) and tempo_bpm > 0:
            while tempo_bpm < self.min_tempo_bpm:
                tempo_bpm *= 2.0
            while tempo_bpm > self.max_tempo_bpm:
                tempo_bpm /= 2.0
        else:
            tempo_bpm = 0.0

        intervals = np.diff(np.asarray(local_onsets, dtype=np.float64))
        intervals = intervals[(intervals >= 0.25) & (intervals <= 2.0)]
        if len(intervals) < 2 or tempo_bpm <= 0:
            tempo_bpm_value = None
            tempo_confidence = 0.0
        else:
            variation = float(np.std(intervals) / max(np.mean(intervals), 1e-9))
            enough_events = min(1.0, len(intervals) / 6.0)
            tempo_confidence = float(np.clip(enough_events * np.exp(-2.0 * variation), 0.0, 1.0))
            if silence_duration > 0.7:
                tempo_confidence *= float(np.exp(-1.5 * (silence_duration - 0.7)))
            tempo_bpm_value = tempo_bpm if tempo_confidence >= 0.15 else None

        return AudioAnalysisObservation(
            timestamp_seconds=timestamp,
            onset_times_seconds=new_onsets,
            tempo_bpm=tempo_bpm_value,
            tempo_confidence=tempo_confidence,
            combined_energy=energy,
            energy_confidence=1.0,
            signal_active=signal_active,
            phrase_break_confidence=phrase_break_confidence,
            discontinuity=block.discontinuity,
        )

    def _trim_window(self) -> None:
        while self._buffered_samples > self.window_samples and self._chunks:
            excess = self._buffered_samples - self.window_samples
            first = self._chunks[0]
            if excess >= first.size:
                self._chunks.popleft()
                self._buffered_samples -= first.size
            else:
                self._chunks[0] = first[excess:]
                self._buffered_samples -= excess


def analyze_wav(
    path: str | Path,
    *,
    update_interval_seconds: float = 0.5,
    block_size: int = 1024,
) -> list[AudioAnalysisObservation]:
    """Analyze a WAV file using the same block processor as live capture."""
    samples, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    mono = np.mean(samples, axis=1, dtype=np.float32)
    analyzer = AudioAnalyzer(
        int(sample_rate),
        update_interval_seconds=update_interval_seconds,
    )
    observations: list[AudioAnalysisObservation] = []
    for offset in range(0, len(mono), block_size):
        block_samples = mono[offset : offset + block_size]
        observation = analyzer.process_block(
            AudioBlock(
                data=block_samples,
                sample_rate=int(sample_rate),
                timestamp_seconds=offset / sample_rate,
            )
        )
        if observation is not None:
            observations.append(observation)
    return observations