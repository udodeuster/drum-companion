from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from typing import Mapping

from drum_companion.audio.groove import DrumEvent, pattern_to_events
from drum_companion.groove_library import INSTRUMENTS
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
        track_levels: Mapping[str, float] | None = None,
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
        self.track_levels = {instrument: 1.0 for instrument in INSTRUMENTS}
        if track_levels is not None:
            self.update_track_levels(track_levels)
        self.feel = "tight"
        self._scheduled_bar_starts: list[int] = []

    @property
    def bar_frame_count(self) -> int:
        return round(self._bar_duration_seconds * self.sample_rate)

    @property
    def _bar_duration_seconds(self) -> float:
        step_seconds = (15.0 if len(self.pattern) == 16 else 30.0) / self.tempo_bpm
        return len(self.pattern) * step_seconds

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

    def update_track_levels(self, levels: Mapping[str, float]) -> None:
        if set(levels) != set(INSTRUMENTS):
            raise ValueError(f"Track levels must be exactly {', '.join(INSTRUMENTS)}")
        normalized: dict[str, float] = {}
        for instrument in INSTRUMENTS:
            value = levels[instrument]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{instrument} level must be a number between 0.0 and 1.0")
            level = float(value)
            if not isfinite(level) or not 0.0 <= level <= 1.0:
                raise ValueError(f"{instrument} level must be between 0.0 and 1.0")
            normalized[instrument] = level
        self.track_levels = normalized

    def update_decision(
        self,
        decision: GrooveDecision,
        *,
        pattern: tuple[str, ...] | None = None,
        track_levels: Mapping[str, float] | None = None,
    ) -> None:
        self.update_pattern(decision.pattern if pattern is None else pattern)
        self.update_track_levels(
            {instrument: 1.0 for instrument in INSTRUMENTS}
            if track_levels is None
            else track_levels
        )
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
                event=replace(
                    event,
                    velocity=(
                        event.velocity
                        * self._velocity_scale
                        * self.track_levels[event.instrument]
                    ),
                ),
            )
            for event in events
        )
        self._next_bar_exact_frame += self._bar_duration_seconds * self.sample_rate
        self.bar_index += 1
        return scheduled