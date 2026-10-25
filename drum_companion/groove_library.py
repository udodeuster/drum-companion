from __future__ import annotations

from dataclasses import dataclass
import json
from math import isfinite
import os
from pathlib import Path
import tempfile
from threading import RLock
from types import MappingProxyType
from typing import Mapping
from uuid import UUID, uuid4


INSTRUMENTS = ("kick", "snare", "closed_hat", "open_hat", "cymbal")
STEPS_PER_GROOVE = 16
_LIBRARY_VERSION = 1


class GrooveLibraryError(RuntimeError):
    """Raised when the persistent groove library cannot be read or saved."""


@dataclass(frozen=True)
class SavedGroove:
    id: str
    name: str
    tracks: Mapping[str, tuple[bool, ...]]
    levels: Mapping[str, float]

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise ValueError("Groove id must be a UUID string")
        try:
            normalized_id = str(UUID(self.id))
        except (ValueError, AttributeError) as exc:
            raise ValueError("Groove id must be a UUID string") from exc
        if normalized_id != self.id:
            raise ValueError("Groove id must use canonical UUID format")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Groove name must not be empty")
        if self.name != self.name.strip():
            raise ValueError("Groove name must not start or end with whitespace")
        if set(self.tracks) != set(INSTRUMENTS):
            raise ValueError(f"Groove tracks must be exactly {', '.join(INSTRUMENTS)}")
        if set(self.levels) != set(INSTRUMENTS):
            raise ValueError(f"Groove levels must be exactly {', '.join(INSTRUMENTS)}")

        normalized_tracks: dict[str, tuple[bool, ...]] = {}
        for instrument in INSTRUMENTS:
            steps = tuple(self.tracks[instrument])
            if len(steps) != STEPS_PER_GROOVE:
                raise ValueError(f"{instrument} track must contain exactly {STEPS_PER_GROOVE} steps")
            if any(type(step) is not bool for step in steps):
                raise ValueError(f"{instrument} steps must be booleans")
            normalized_tracks[instrument] = steps

        normalized_levels: dict[str, float] = {}
        for instrument in INSTRUMENTS:
            level = self.levels[instrument]
            if isinstance(level, bool) or not isinstance(level, (int, float)):
                raise ValueError(f"{instrument} level must be a number between 0.0 and 1.0")
            numeric_level = float(level)
            if not isfinite(numeric_level) or not 0.0 <= numeric_level <= 1.0:
                raise ValueError(f"{instrument} level must be between 0.0 and 1.0")
            normalized_levels[instrument] = numeric_level

        object.__setattr__(self, "tracks", MappingProxyType(normalized_tracks))
        object.__setattr__(self, "levels", MappingProxyType(normalized_levels))

    @classmethod
    def create(
        cls,
        name: str,
        tracks: Mapping[str, tuple[bool, ...]],
        levels: Mapping[str, float],
    ) -> "SavedGroove":
        return cls(str(uuid4()), name, tracks, levels)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "tracks": {instrument: list(self.tracks[instrument]) for instrument in INSTRUMENTS},
            "levels": dict(self.levels),
        }


class GrooveLibrary:
    """Persistent, host-local collection of explicitly saved grooves."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else self.default_path()
        self._lock = RLock()

    @staticmethod
    def default_path() -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "DrumCompanion" / "grooves.json"
        if os.name == "nt":
            return Path.home() / "AppData" / "Local" / "DrumCompanion" / "grooves.json"
        return Path.home() / ".local" / "share" / "DrumCompanion" / "grooves.json"

    def list_grooves(self) -> tuple[SavedGroove, ...]:
        with self._lock:
            return self._read()

    def get_groove(self, groove_id: str) -> SavedGroove | None:
        with self._lock:
            return next((groove for groove in self._read() if groove.id == groove_id), None)

    def save_groove(self, groove: SavedGroove) -> tuple[SavedGroove, ...]:
        if not isinstance(groove, SavedGroove):
            raise ValueError("Only validated SavedGroove instances can be saved")
        with self._lock:
            grooves = list(self._read())
            for index, existing in enumerate(grooves):
                if existing.id == groove.id:
                    if any(
                        other.id != groove.id and other.name.casefold() == groove.name.casefold()
                        for other in grooves
                    ):
                        raise ValueError(f"A groove named {groove.name!r} already exists")
                    grooves[index] = groove
                    break
                if existing.name.casefold() == groove.name.casefold():
                    raise ValueError(f"A groove named {groove.name!r} already exists")
            else:
                grooves.append(groove)
            self._write(tuple(grooves))
            return tuple(grooves)

    def delete_groove(self, groove_id: str) -> tuple[SavedGroove, ...]:
        with self._lock:
            grooves = self._read()
            remaining = tuple(groove for groove in grooves if groove.id != groove_id)
            if len(remaining) == len(grooves):
                raise LookupError("The saved groove does not exist")
            self._write(remaining)
            return remaining

    def _read(self) -> tuple[SavedGroove, ...]:
        if not self.path.exists():
            if self.path.parent.exists() and not self.path.parent.is_dir():
                raise GrooveLibraryError(f"Unable to read groove library {self.path}: parent is not a directory")
            return ()
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if (
                not isinstance(document, dict)
                or set(document) != {"version", "grooves"}
                or isinstance(document["version"], bool)
                or not isinstance(document["version"], int)
                or document["version"] != _LIBRARY_VERSION
                or not isinstance(document["grooves"], list)
            ):
                raise ValueError("Unsupported or invalid groove library format")
            grooves = tuple(self._parse_groove(item) for item in document["grooves"])
            ids: set[str] = set()
            names: set[str] = set()
            for groove in grooves:
                if groove.id in ids:
                    raise ValueError(f"Duplicate groove id {groove.id}")
                if groove.name.casefold() in names:
                    raise ValueError(f"Duplicate groove name {groove.name!r}")
                ids.add(groove.id)
                names.add(groove.name.casefold())
            return grooves
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
            raise GrooveLibraryError(f"Unable to read groove library {self.path}: {exc}") from exc

    @staticmethod
    def _parse_groove(item: object) -> SavedGroove:
        if not isinstance(item, dict) or set(item) != {"id", "name", "tracks", "levels"}:
            raise ValueError("Each groove must contain id, name, tracks, and levels")
        if not isinstance(item["tracks"], dict) or not isinstance(item["levels"], dict):
            raise ValueError("Groove tracks and levels must be objects")
        return SavedGroove(
            id=item["id"],
            name=item["name"],
            tracks=item["tracks"],
            levels=item["levels"],
        )

    def _write(self, grooves: tuple[SavedGroove, ...]) -> None:
        document = {
            "version": _LIBRARY_VERSION,
            "grooves": [groove.to_dict() for groove in grooves],
        }
        temporary_path: str | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = temporary_file.name
                json.dump(document, temporary_file, ensure_ascii=False, indent=2, allow_nan=False)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.path)
        except (OSError, TypeError, ValueError) as exc:
            raise GrooveLibraryError(f"Unable to save groove library {self.path}: {exc}") from exc
        finally:
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
