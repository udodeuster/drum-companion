from __future__ import annotations

from dataclasses import dataclass, replace

from drum_companion.audio.groove import DrumEvent, pattern_to_events
from drum_companion.models import GrooveDecision


@dataclass(frozen=True)
class ScheduledDrumEvent:
    frame_position: int
    event: DrumEvent


class GrooveScheduler:
    """Schedule each bar in output-frame time without moving issued events."""

    def __init__(
        self,
        pattern: tuple[str, ...] | list[str],
        *,
        tempo_bpm: float,
        sample_rate: int,
        start_frame: int = 0,
    ) -> None:
        if sample_rate <= 0 or start_frame < 0:
            raise ValueError("sample_rate must be positive and start_frame non-negative")
        if tempo_bpm <= 0:
            raise ValueError("tempo_bpm must be greater than zero")
        if not pattern:
            raise ValueError("pattern must contain at least one step")
        self.pattern = tuple(pattern)
        self.tempo_bpm = float(tempo_bpm)
        self.sample_rate = sample_rate
        self.bar_index = 0
        self._next_bar_exact_frame = float(start_frame)
        self._velocity_scale = 1.0
        self.feel = "tight"
        self._scheduled_bar_starts: list[int] = []

    @property
    def bar_frame_count(self) -> int:
        return round(len(self.pattern) * 30.0 / self.tempo_bpm * self.sample_rate)

    @property
    def next_bar_frame(self) -> int:
        return round(self._next_bar_exact_frame)

    def next_downbeat_frame(self, frame_position: int) -> int:
        self._scheduled_bar_starts = [
            frame for frame in self._scheduled_bar_starts if frame >= frame_position
        ]
        if self._scheduled_bar_starts:
            return self._scheduled_bar_starts[0]
        return self.next_bar_frame

    def update_tempo(self, tempo_bpm: float) -> None:
        if tempo_bpm <= 0:
            raise ValueError("tempo_bpm must be greater than zero")
        self.tempo_bpm = float(tempo_bpm)

    def update_pattern(self, pattern: tuple[str, ...] | list[str]) -> None:
        if not pattern:
            raise ValueError("pattern must contain at least one step")
        self.pattern = tuple(pattern)

    def update_decision(self, decision: GrooveDecision) -> None:
        self.update_pattern(decision.pattern)
        self.feel = decision.feel
        if decision.tempo_bpm is not None:
            self.update_tempo(decision.tempo_bpm)
        self._velocity_scale = max(0.0, min(1.0, decision.effective_intensity))

    def schedule_next_bar(self) -> tuple[ScheduledDrumEvent, ...]:
        bar_start = round(self._next_bar_exact_frame)
        self._scheduled_bar_starts.append(bar_start)
        events = pattern_to_events(
            self.pattern,
            self.tempo_bpm,
            bar_index=self.bar_index,
            feel=self.feel,
        )
        scheduled = tuple(
            ScheduledDrumEvent(
                frame_position=bar_start + round(event.offset_seconds * self.sample_rate),
                event=replace(event, velocity=event.velocity * self._velocity_scale),
            )
            for event in events
        )
        self._next_bar_exact_frame += len(self.pattern) * 30.0 / self.tempo_bpm * self.sample_rate
        self.bar_index += 1
        return scheduled