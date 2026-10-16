from __future__ import annotations

from dataclasses import dataclass

from drum_companion.models import AudioAnalysisObservation, GrooveDecision

STYLE_PROFILES = {
    "rock": {"density": 1.0, "accent": 1.0, "kick": [1, 0, 0, 0, 1, 0, 0, 0], "snare": [0, 0, 1, 0, 0, 0, 1, 0], "hihat": [1, 1, 1, 1, 1, 1, 1, 1]},
    "folk": {"density": 0.7, "accent": 0.8, "kick": [1, 0, 0, 0, 1, 0, 0, 1], "snare": [0, 0, 1, 0, 0, 0, 1, 0], "hihat": [0, 1, 0, 1, 0, 1, 0, 1]},
    "indie": {"density": 0.85, "accent": 0.9, "kick": [1, 0, 1, 0, 1, 0, 0, 1], "snare": [0, 0, 1, 0, 0, 0, 1, 0], "hihat": [1, 0, 1, 0, 1, 0, 1, 0]},
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
) -> tuple[DrumEvent, ...]:
    """Translate compact pattern cells into events timed on an eighth-note grid."""
    if tempo_bpm <= 0:
        raise ValueError("tempo_bpm must be greater than zero")
    if bar_index < 0:
        raise ValueError("bar_index must be non-negative")

    variation_bar = bar_index % 4 == 3
    events: list[DrumEvent] = []
    for step_index, cell in enumerate(pattern):
        tokens = set(cell)
        accented = "A" in tokens
        offset_seconds = step_index * 30.0 / tempo_bpm
        instruments: list[str] = []
        if "K" in tokens:
            instruments.append("kick")
        if "S" in tokens:
            instruments.append("snare")
        if "H" in tokens:
            instruments.append(
                "open_hat" if variation_bar and step_index == len(pattern) - 1 else "closed_hat"
            )
        if variation_bar and step_index == 0 and accented:
            instruments.append("cymbal")

        for instrument in instruments:
            base_velocity = {
                "kick": 0.78,
                "snare": 0.72,
                "closed_hat": 0.48,
                "open_hat": 0.64,
                "cymbal": 0.7,
            }[instrument]
            velocity = min(1.0, base_velocity * (1.15 if accented else 1.0))
            events.append(DrumEvent(offset_seconds, instrument, velocity))

    return tuple(events)


def build_pattern(style: str, feel: str, intensity: float, bars: int = 1) -> list[str]:
    """Generate a simple groove pattern for the UI and validation scaffold."""
    normalized_style = style.lower()
    normalized_feel = feel.lower()
    if normalized_style not in STYLE_PROFILES:
        raise ValueError(f"Unsupported style: {style}")

    profile = STYLE_PROFILES[normalized_style]
    sway = 0.5 if normalized_feel == "relaxed" else 1.0
    pattern: list[str] = []

    for _ in range(bars):
        for index in range(len(profile["kick"])):
            kick = "K" if profile["kick"][index] and intensity > 0.2 else "-"
            snare = "S" if profile["snare"][index] and sway > 0.5 else "-"
            hihat = "H" if profile["hihat"][index] else "-"
            pattern.append(f"{kick}{snare}{hihat}")

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
    feel_adjustment = 0.7 if normalized_feel == "relaxed" else 1.0
    effective_intensity = max(0.0, min(1.0, intensity)) * profile["density"] * density_boost * feel_adjustment

    steps: list[str] = []
    for index in range(8):
        accent = "A" if index in (0, 4) and effective_intensity > 0.6 else "-"
        kick = "K" if profile["kick"][index] and effective_intensity > 0.3 else "-"
        snare = "S" if profile["snare"][index] and effective_intensity > 0.45 else "-"
        hihat = "H" if profile["hihat"][index] and effective_intensity > 0.2 else "-"
        steps.append(f"{accent}{kick}{snare}{hihat}")

    return steps


class GrooveFollower:
    """Translate analysis observations into confidence-aware groove updates."""

    def __init__(self, style: str, feel: str, intensity: float, phrase: str = "verse") -> None:
        self.style = style
        self.feel = feel
        self.intensity = max(0.0, min(1.0, intensity))
        self.phrase = phrase
        self._last_stable_tempo: float | None = None

    def update(self, observation: AudioAnalysisObservation) -> GrooveDecision:
        reliable = (
            observation.signal_active
            and not observation.discontinuity
            and observation.tempo_bpm is not None
            and observation.tempo_confidence >= 0.35
        )
        if reliable:
            self._last_stable_tempo = observation.tempo_bpm

        if reliable:
            effective_intensity = self.intensity
        elif not observation.signal_active:
            effective_intensity = 0.0
        elif self._last_stable_tempo is not None:
            effective_intensity = self.intensity * 0.45
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
        return GrooveDecision(
            tempo_bpm=self._last_stable_tempo,
            tempo_confidence=observation.tempo_confidence,
            effective_intensity=effective_intensity,
            pattern=pattern,
            holding_stable_tempo=not reliable and self._last_stable_tempo is not None,
            signal_active=observation.signal_active,
        )
