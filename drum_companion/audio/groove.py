"""Groove generation, event mapping, and confidence-aware tempo following."""

from __future__ import annotations

import math
from dataclasses import dataclass

from drum_companion.groove_library import INSTRUMENTS, SavedGroove
from drum_companion.models import AudioAnalysisObservation, GrooveDecision

_OCTAVE_TEMPO_CONFIRMATION_SECONDS = 3.0
_TEMPO_CHANGE_CONFIRMATION_SECONDS = 8.0
_TEMPO_ANCHOR_BAND = 0.06
_TEMPO_REANCHOR_SECONDS = 4.0
_PAUSE_FADE_AFTER_BARS = 1.0
_PAUSE_KICK_ONLY_AFTER_BARS = 5.0
_PAUSE_FADE_FACTOR = 0.75

_EXTRA_TOKENS = {
    "R": "rimshot",
    "P": "clap",
    "t": "tom_high",
    "T": "tom_low",
    "D": "ride",
    "X": "shaker",
    "B": "cowbell",
}

STYLE_PROFILES = {
    "rock": {"density": 1.0, "accent": 1.0, "kick": [1, 0, 0, 0, 1, 0, 0, 0], "snare": [0, 0, 1, 0, 0, 0, 1, 0], "hihat": [1, 1, 1, 1, 1, 1, 1, 1], "ghost_snare_steps": [1, 5]},
    "folk": {"density": 0.7, "accent": 0.8, "kick": [1, 0, 0, 0, 1, 0, 0, 1], "snare": [0, 0, 1, 0, 0, 0, 1, 0], "hihat": [0, 1, 0, 1, 0, 1, 0, 1], "ghost_snare_steps": [1, 5]},
    "indie": {"density": 0.85, "accent": 0.9, "kick": [1, 0, 1, 0, 1, 0, 0, 1], "snare": [0, 0, 1, 0, 0, 0, 1, 0], "hihat": [1, 0, 1, 0, 1, 0, 1, 0], "ghost_snare_steps": []},
}


@dataclass(frozen=True)
class DrumEvent:
    """Represent a drum hit and its timing within a groove."""
    offset_seconds: float
    instrument: str
    velocity: float


def pattern_to_events(
    pattern: tuple[str, ...] | list[str],
    tempo_bpm: float,
    *,
    bar_index: int = 0,
    feel: str = "tight",
) -> tuple[DrumEvent, ...]:
    """Translate compact pattern cells into timed eighth-note events.

    Args:
        pattern (tuple[str, ...] | list[str]): Drum pattern to process.
        tempo_bpm (float): Tempo in beats per minute.
        bar_index (int): Zero-based index of the musical bar.
        feel (str): Timing feel used for the groove.

    Returns:
        tuple[DrumEvent, ...]: The result produced by this operation.
    """
    if tempo_bpm <= 0:
        raise ValueError("tempo_bpm must be greater than zero")
    if bar_index < 0:
        raise ValueError("bar_index must be non-negative")
    normalized_feel = feel.lower()
    if normalized_feel not in {"tight", "relaxed"}:
        raise ValueError(f"Unsupported feel: {feel}")

    step_seconds = (15.0 if len(pattern) == 16 else 30.0) / tempo_bpm
    events: list[DrumEvent] = []
    for step_index, cell in enumerate(pattern):
        tokens = set(cell)
        accented = "A" in tokens
        offset_seconds = step_index * step_seconds
        swing_step = step_index % (4 if len(pattern) == 16 else 2)
        if normalized_feel == "relaxed" and swing_step == (2 if len(pattern) == 16 else 1):
            offset_seconds += 0.05 * 60.0 / tempo_bpm
        instruments: list[str] = []
        if "K" in tokens:
            instruments.append("kick")
        if "S" in tokens:
            instruments.append("snare")
        if "H" in tokens:
            instruments.append("closed_hat")
        if "O" in tokens:
            instruments.append("open_hat")
        if "C" in tokens:
            instruments.append("cymbal")
        for token, instrument in _EXTRA_TOKENS.items():
            if token in tokens:
                instruments.append(instrument)
        for instrument in instruments:
            base_velocity = {
                "kick": 0.78,
                "snare": 0.72,
                "closed_hat": 0.48,
                "open_hat": 0.64,
                "cymbal": 0.7,
                "rimshot": 0.7,
                "clap": 0.7,
                "tom_high": 0.72,
                "tom_low": 0.74,
                "ride": 0.55,
                "shaker": 0.4,
                "cowbell": 0.6,
            }[instrument]
            velocity = min(1.0, base_velocity * (1.15 if accented else 1.0))
            events.append(DrumEvent(offset_seconds, instrument, velocity))
        if "g" in tokens and bar_index % 4 in {1, 3}:
            events.append(DrumEvent(offset_seconds, "snare", 0.14))

    return tuple(events)


def kick_only_pattern(pattern: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Handle kick only pattern.

    Args:
        pattern (tuple[str, ...] | list[str]): Drum pattern to process.

    Returns:
        tuple[str, ...]: The result produced by this operation.
    """
    return tuple("K" if "K" in cell else "-" for cell in pattern)


def saved_groove_to_pattern(groove: SavedGroove) -> tuple[str, ...]:
    """Encode authored track states as sixteen scheduler cells.

    Args:
        groove (SavedGroove): Groove data to process.

    Returns:
        tuple[str, ...]: The result produced by this operation.
    """
    tokens = {
        "kick": "K",
        "snare": "S",
        "closed_hat": "H",
        "open_hat": "O",
        "cymbal": "C",
        "rimshot": "R",
        "clap": "P",
        "tom_high": "t",
        "tom_low": "T",
        "ride": "D",
        "shaker": "X",
        "cowbell": "B",
    }
    return tuple(
        "".join(token for instrument, token in tokens.items() if groove.tracks[instrument][step])
        or "----"
        for step in range(16)
    )


def build_pattern(style: str, feel: str, intensity: float, bars: int = 1) -> list[str]:
    """Generate a simple groove pattern for the UI and validation scaffold.

    Args:
        style (str): Drum-groove style name.
        feel (str): Timing feel used for the groove.
        intensity (float): Normalized groove intensity between zero and one.
        bars (int): Number of musical bars to process or generate.

    Returns:
        list[str]: The result produced by this operation.
    """
    normalized_style = style.lower()
    normalized_feel = feel.lower()
    if normalized_style not in STYLE_PROFILES:
        raise ValueError(f"Unsupported style: {style}")

    profile = STYLE_PROFILES[normalized_style]
    pattern: list[str] = []
    active = intensity > 0.0

    for _ in range(bars):
        for index in range(len(profile["kick"])):
            kick = "K" if profile["kick"][index] and active else "-"
            snare = "S" if profile["snare"][index] and active else "-"
            hihat = "H" if profile["hihat"][index] else "-"
            ghost = (
                "g"
                if active
                and normalized_feel == "relaxed"
                and index in profile["ghost_snare_steps"]
                else ""
            )
            pattern.append(f"{kick}{snare}{hihat}{ghost}")

    return pattern


def generate_accompaniment(phrase: str, style: str, feel: str, intensity: float) -> list[str]:
    """Create a phrase-aware accompaniment pattern tailored to a solo-performance...

    Args:
        phrase (str): Musical phrase or section name.
        style (str): Drum-groove style name.
        feel (str): Timing feel used for the groove.
        intensity (float): Normalized groove intensity between zero and one.

    Returns:
        list[str]: The result produced by this operation.
    """
    normalized_phrase = phrase.lower()
    normalized_style = style.lower()
    normalized_feel = feel.lower()
    if normalized_style not in STYLE_PROFILES:
        raise ValueError(f"Unsupported style: {style}")

    profile = STYLE_PROFILES[normalized_style]
    density_boost = 1.25 if normalized_phrase == "chorus" else 1.0
    effective_intensity = max(0.0, min(1.0, intensity)) * profile["density"] * density_boost

    steps: list[str] = []
    for index in range(8):
        accent = "A" if index in (0, 4) and effective_intensity > 0.6 else "-"
        kick = "K" if profile["kick"][index] and effective_intensity > 0.0 else "-"
        snare = "S" if profile["snare"][index] and effective_intensity > 0.0 else "-"
        hihat = "H" if profile["hihat"][index] and effective_intensity > 0.2 else "-"
        ghost = (
            "g"
            if normalized_feel == "relaxed" and index in profile["ghost_snare_steps"]
            else "-"
        )
        extras = ""
        if normalized_style == "folk":
            if index == 6 and effective_intensity > 0.3:
                extras += "R"
            if index % 2 == 1 and effective_intensity > 0.4:
                extras += "X"
        elif normalized_style == "indie" and normalized_phrase == "chorus" and profile["hihat"][index]:
            if effective_intensity > 0.2:
                hihat = "-"
                extras += "D"
        steps.append(f"{accent}{kick}{snare}{hihat}{ghost}{extras}")

    return steps


class GrooveFollower:
    """Translate analysis observations into confidence-aware groove updates."""

    def __init__(
        self,
        style: str,
        feel: str,
        intensity: float,
        phrase: str = "verse",
        onset_timeout_bars: int = 1,
        lock_pulse_octave: bool = False,
        lock_tempo: bool = False,
    ) -> None:
        """Initialize the instance.

        Args:
            style (str): Drum-groove style name.
            feel (str): Timing feel used for the groove.
            intensity (float): Normalized groove intensity between zero and one.
            phrase (str): Musical phrase or section name.
            onset_timeout_bars (int): Number of bars allowed without an onset
                before timing out.
            lock_pulse_octave (bool): Whether to prevent octave pulse changes.
            lock_tempo (bool): Whether to hold the current tempo estimate.

        Returns:
            None: No value is returned.
        """
        if isinstance(onset_timeout_bars, bool) or onset_timeout_bars not in {0, 1, 2, 4}:
            raise ValueError("onset_timeout_bars must be one of 0, 1, 2, or 4 bars")
        self.style = style
        self.feel = feel
        self.intensity = max(0.0, min(1.0, intensity))
        self.phrase = phrase
        self.onset_timeout_bars = onset_timeout_bars
        # With drum playback, microphone bleed of the drums can look like a
        # double-time pulse.
        self.lock_pulse_octave = lock_pulse_octave
        # Keeps the first reliable tempo for the whole session.
        self.lock_tempo = lock_tempo
        self._pause_started_seconds: float | None = None
        self._last_stable_tempo: float | None = None
        self._last_detected_onset: float | None = None
        self._last_pattern: tuple[str, ...] | None = None
        self._last_effective_intensity = 0.0
        self._pending_octave_tempo: float | None = None
        self._pending_octave_observations = 0
        self._pending_octave_since_seconds: float | None = None
        self._free_tempo_until = -math.inf

    def update(self, observation: AudioAnalysisObservation) -> GrooveDecision:
        """Handle update.

        Args:
            observation (AudioAnalysisObservation): Audio-analysis observation to
                process.

        Returns:
            GrooveDecision: The result produced by this operation.
        """
        if observation.onset_times_seconds:
            self._last_detected_onset = max(observation.onset_times_seconds)

        onset_timeout_seconds = (
            240.0 * self.onset_timeout_bars / self._last_stable_tempo
            if self._last_stable_tempo is not None
            else None
        )
        onset_age = (
            observation.timestamp_seconds - self._last_detected_onset
            if self._last_detected_onset is not None
            else None
        )
        onset_timed_out = (
            onset_timeout_seconds is not None
            and onset_age is not None
            and (onset_age > 0.0 if self.onset_timeout_bars == 0 else onset_age >= onset_timeout_seconds)
        )
        musical_activity_active = observation.signal_active and not onset_timed_out

        reliable = (
            musical_activity_active
            and not observation.discontinuity
            and observation.tempo_bpm is not None
            and observation.tempo_confidence >= 0.35
        )
        tempo_update_accepted = False
        if reliable and observation.tempo_bpm is not None:
            candidate = observation.tempo_bpm
            anchor = self._last_stable_tempo
            is_octave = anchor is not None and self._is_octave_tempo_change(anchor, candidate)
            if anchor is None:
                self._accept_tempo(candidate)
                tempo_update_accepted = True
            elif self.lock_tempo or (is_octave and self.lock_pulse_octave):
                pass
            elif observation.timestamp_seconds < self._free_tempo_until:
                self._accept_tempo(candidate)
                tempo_update_accepted = True
            elif not is_octave and abs(candidate / anchor - 1.0) <= _TEMPO_ANCHOR_BAND:
                self._clear_pending_tempo()
            else:
                # A different tempo must persist before it replaces the anchor.
                if (
                    self._pending_octave_tempo is not None
                    and abs(candidate - self._pending_octave_tempo)
                    <= self._pending_octave_tempo * 0.05
                ):
                    self._pending_octave_observations += 1
                else:
                    self._pending_octave_tempo = candidate
                    self._pending_octave_observations = 1
                    self._pending_octave_since_seconds = observation.timestamp_seconds
                confirmation_seconds = (
                    _OCTAVE_TEMPO_CONFIRMATION_SECONDS if is_octave else _TEMPO_CHANGE_CONFIRMATION_SECONDS
                )
                if (
                    self._pending_octave_observations >= 3
                    and self._pending_octave_since_seconds is not None
                    and observation.timestamp_seconds - self._pending_octave_since_seconds
                    >= confirmation_seconds
                ):
                    self._accept_tempo(candidate)
                    tempo_update_accepted = True
        else:
            self._clear_pending_tempo()

        if not musical_activity_active:
            self._free_tempo_until = math.inf
            if self._pause_started_seconds is None:
                self._pause_started_seconds = observation.timestamp_seconds
        else:
            if self._pause_started_seconds is not None:
                # After a pause the tempo may re-anchor briefly, then it is held again.
                self._free_tempo_until = observation.timestamp_seconds + _TEMPO_REANCHOR_SECONDS
            self._pause_started_seconds = None

        kick_only = False
        if not musical_activity_active and self._last_pattern is not None:
            effective_intensity = self._last_effective_intensity
            pattern = self._last_pattern
            paused_bars = self._paused_bars(observation.timestamp_seconds)
            if paused_bars >= _PAUSE_FADE_AFTER_BARS:
                effective_intensity *= _PAUSE_FADE_FACTOR
            if paused_bars >= _PAUSE_KICK_ONLY_AFTER_BARS:
                kick_only = True
                pattern = kick_only_pattern(pattern)
        else:
            if musical_activity_active and self._last_stable_tempo is not None:
                effective_intensity = self.intensity
            elif musical_activity_active and reliable:
                effective_intensity = self.intensity
            elif not musical_activity_active:
                effective_intensity = 0.0
            else:
                effective_intensity = self.intensity * 0.2

            pattern = tuple(
                generate_accompaniment(
                    self.phrase,
                    self.style,
                    self.feel,
                    effective_intensity,
                )
            )
            if musical_activity_active:
                self._last_pattern = pattern
                self._last_effective_intensity = effective_intensity
        return GrooveDecision(
            tempo_bpm=self._last_stable_tempo,
            tempo_confidence=observation.tempo_confidence,
            effective_intensity=effective_intensity,
            pattern=pattern,
            holding_stable_tempo=not tempo_update_accepted and self._last_stable_tempo is not None,
            signal_active=observation.signal_active,
            musical_activity_active=musical_activity_active,
            feel=self.feel,
            kick_only=kick_only,
        )

    def _accept_tempo(self, tempo_bpm: float) -> None:
        """Handle accept tempo.

        Args:
            tempo_bpm (float): Tempo in beats per minute.

        Returns:
            None: No value is returned.
        """
        self._last_stable_tempo = tempo_bpm
        self._clear_pending_tempo()

    def _clear_pending_tempo(self) -> None:
        """Handle clear pending tempo.

        Returns:
            None: No value is returned.
        """
        self._pending_octave_tempo = None
        self._pending_octave_observations = 0
        self._pending_octave_since_seconds = None

    def _paused_bars(self, timestamp_seconds: float) -> float:
        """Handle paused bars.

        Args:
            timestamp_seconds (float): Observation time in seconds from the start
                of capture.

        Returns:
            float: The result produced by this operation.
        """
        if self._pause_started_seconds is None or self._last_stable_tempo is None:
            return 0.0
        return (timestamp_seconds - self._pause_started_seconds) * self._last_stable_tempo / 240.0

    @staticmethod
    def _is_octave_tempo_change(stable_tempo: float, candidate_tempo: float) -> bool:
        """Handle is octave tempo change.

        Args:
            stable_tempo (float): Currently accepted stable tempo in beats per
                minute.
            candidate_tempo (float): New tempo candidate being evaluated for
                stability.

        Returns:
            bool: The result produced by this operation.
        """
        ratio = candidate_tempo / stable_tempo
        return any(abs(ratio / factor - 1.0) <= 0.15 for factor in (0.25, 1 / 3, 0.5, 2.0, 3.0, 4.0))
