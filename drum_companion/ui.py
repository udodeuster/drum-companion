from __future__ import annotations

from dataclasses import dataclass

from drum_companion.audio.groove import generate_accompaniment


@dataclass(frozen=True)
class InteractionPreset:
    phrase: str
    style: str
    feel: str
    intensity: float

    @classmethod
    def from_input(cls, phrase: str, style: str, feel: str, intensity: str | float) -> "InteractionPreset":
        normalized_phrase = (phrase or "verse").lower()
        normalized_style = (style or "rock").lower()
        normalized_feel = (feel or "tight").lower()
        value = float(intensity)
        return cls(
            phrase=normalized_phrase,
            style=normalized_style,
            feel=normalized_feel,
            intensity=max(0.0, min(1.0, value)),
        )


class GrooveDashboard:
    def __init__(self, tempo: float, phrase: str, style: str, feel: str, intensity: float):
        self.tempo = float(tempo)
        self.phrase = phrase.lower()
        self.style = style.lower()
        self.feel = feel.lower()
        self.intensity = max(0.0, min(1.0, float(intensity)))

    def render(self) -> str:
        accompaniment = generate_accompaniment(self.phrase, self.style, self.feel, self.intensity)
        preview = " ".join(accompaniment[:8])
        lines = [
            "+------------------------------------------+",
            "| Drum Companion - Solo Performance       |",
            f"| Tempo: {self.tempo:>6.1f} BPM           |",
            f"| Phrase: {self.phrase:<8}             |",
            f"| Style: {self.style:<8}             |",
            f"| Feel: {self.feel:<8}               |",
            f"| Intensity: {self.intensity:>4.2f}            |",
            f"| Groove: {preview:<32} |",
            "+------------------------------------------+",
        ]
        return "\n".join(lines)
