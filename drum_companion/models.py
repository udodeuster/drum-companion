"""Immutable data models shared by audio analysis and groove generation."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class AudioAnalysisObservation:
    """Confidence-aware measurements from one mixed audio input."""

    timestamp_seconds: float
    onset_times_seconds: tuple[float, ...]
    tempo_bpm: float | None
    tempo_confidence: float
    combined_energy: float
    energy_confidence: float
    signal_active: bool = True
    phrase_break_confidence: float | None = None
    discontinuity: bool = False

    def __post_init__(self) -> None:
        """Validate the instance fields after initialization.

        Returns:
            None: No value is returned.
        """
        if not isfinite(self.timestamp_seconds) or self.timestamp_seconds < 0:
            raise ValueError("timestamp_seconds must be finite and non-negative")
        if self.tempo_bpm is not None and (not isfinite(self.tempo_bpm) or self.tempo_bpm <= 0):
            raise ValueError("tempo_bpm must be positive and finite when provided")
        for value, name in (
            (self.tempo_confidence, "tempo_confidence"),
            (self.combined_energy, "combined_energy"),
            (self.energy_confidence, "energy_confidence"),
        ):
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0")
        if self.phrase_break_confidence is not None and (
            not isfinite(self.phrase_break_confidence)
            or not 0.0 <= self.phrase_break_confidence <= 1.0
        ):
            raise ValueError("phrase_break_confidence must be between 0.0 and 1.0")
        if any(not isfinite(onset) or onset < 0 for onset in self.onset_times_seconds):
            raise ValueError("onset times must be finite and non-negative")


@dataclass(frozen=True)
class GrooveDecision:
    """Pattern and tempo decision derived from the latest analysis update."""

    tempo_bpm: float | None
    tempo_confidence: float
    effective_intensity: float
    pattern: tuple[str, ...]
    holding_stable_tempo: bool
    signal_active: bool
    musical_activity_active: bool = True
    feel: str = "tight"
    kick_only: bool = False


@dataclass(frozen=True)
class PerformanceContext:
    """Represents the musical context inferred from the lead performance."""

    tempo_bpm: float
    voice_energy: float
    guitar_energy: float
    phrase: str
    confidence: float


@dataclass(frozen=True)
class GrooveSettings:
    """Runtime settings for a generated accompaniment pattern."""

    style: str
    feel: str
    intensity: float
    bars: int = 1
