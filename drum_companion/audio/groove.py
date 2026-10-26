from __future__ import annotations

from dataclasses import dataclass

from drum_companion.groove_library import INSTRUMENTS, SavedGroove
from drum_companion.models import AudioAnalysisObservation, GrooveDecision

_OCTAVE_TEMPO_CONFIRMATION_SECONDS = 3.0

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
    """Translate compact pattern cells into timed eighth-note events."""
    if tempo_bpm <= 0:
        raise ValueError("tempo_bpm must be greater than zero")
    if bar_index < 0:
        raise ValueError("bar_index must be non-negative")
    normalized_feel = feel.lower()
    if normalized_feel not in {"tight", "relaxed"}:
        raise ValueError(f"Unsupported feel: {feel}")

    variation_bar = len(pattern) != 16 and bar_index % 4 == 3
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
            instruments.append(
                "open_hat" if variation_bar and step_index == len(pattern) - 1 else "closed_hat"
            )
        if "O" in tokens:
            instruments.append("open_hat")
        if "C" in tokens:
            instruments.append("cymbal")
        for token, instrument in _EXTRA_TOKENS.items():
            if token in tokens:
                instruments.append(instrument)
        if variation_bar and step_index == len(pattern) - 1 and "T" not in tokens and "S" not in tokens:
            instruments.append("tom_low")
        if variation_bar and step_index == 0 and accented:
            instruments.append("cymbal")

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


def saved_groove_to_pattern(groove: SavedGroove) -> tuple[str, ...]:
    """Encode authored track states as sixteen scheduler cells."""
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
    """Generate a simple groove pattern for the UI and validation scaffold."""
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
    """Create a phrase-aware accompaniment pattern tailored to a solo-performance context."""
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
    ) -> None:
        if isinstance(onset_timeout_bars, bool) or onset_timeout_bars not in {0, 1, 2, 4}:
            raise ValueError("onset_timeout_bars must be one of 0, 1, 2, or 4 bars")
        self.style = style
        self.feel = feel
        self.intensity = max(0.0, min(1.0, intensity))
        self.phrase = phrase
        self.onset_timeout_bars = onset_timeout_bars
        # With drum playback, microphone bleed of the drums can look like a double-time pulse.
        self.lock_pulse_octave = lock_pulse_octave
        self._last_stable_tempo: float | None = None
        self._last_detected_onset: float | None = None
        self._last_pattern: tuple[str, ...] | None = None
        self._last_effective_intensity = 0.0
        self._pending_octave_tempo: float | None = None
        self._pending_octave_observations = 0
        self._pending_octave_since_seconds: float | None = None

    def update(self, observation: AudioAnalysisObservation) -> GrooveDecision:
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
            if (
                self._last_stable_tempo is not None
                and self._is_octave_tempo_change(self._last_stable_tempo, observation.tempo_bpm)
            ):
                if self.lock_pulse_octave:
                    pass
                elif (
                    self._pending_octave_tempo is not None
                    and abs(observation.tempo_bpm - self._pending_octave_tempo)
                    <= self._pending_octave_tempo * 0.05
                ):
                    self._pending_octave_observations += 1
                else:
                    self._pending_octave_tempo = observation.tempo_bpm
                    self._pending_octave_observations = 1
                    self._pending_octave_since_seconds = observation.timestamp_seconds
                if (
                    self._pending_octave_observations >= 3
                    and self._pending_octave_since_seconds is not None
                    and observation.timestamp_seconds - self._pending_octave_since_seconds
                    >= _OCTAVE_TEMPO_CONFIRMATION_SECONDS
                ):
                    self._last_stable_tempo = observation.tempo_bpm
                    tempo_update_accepted = True
                    self._pending_octave_tempo = None
                    self._pending_octave_observations = 0
                    self._pending_octave_since_seconds = None
            else:
                self._last_stable_tempo = observation.tempo_bpm
                tempo_update_accepted = True
                self._pending_octave_tempo = None
                self._pending_octave_observations = 0
                self._pending_octave_since_seconds = None
        else:
            self._pending_octave_tempo = None
            self._pending_octave_observations = 0
            self._pending_octave_since_seconds = None

        if not musical_activity_active and self._last_pattern is not None:
            effective_intensity = self._last_effective_intensity
            pattern = self._last_pattern
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
        )

    @staticmethod
    def _is_octave_tempo_change(stable_tempo: float, candidate_tempo: float) -> bool:
        ratio = candidate_tempo / stable_tempo
        return any(abs(ratio / factor - 1.0) <= 0.15 for factor in (0.25, 1 / 3, 0.5, 2.0, 3.0, 4.0))
