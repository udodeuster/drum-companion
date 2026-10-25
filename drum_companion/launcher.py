from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def log_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    directory = Path(base) / "DrumCompanion" if base else Path.home() / ".drum-companion"
    return directory / "app.log"


def ensure_streams() -> None:
    """Windowed executables have no console; give print() somewhere to go."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = open(path, "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def main(argv: list[str] | None = None) -> int:
    ensure_streams()
    if argv is None:
        argv = sys.argv[1:] or ["--web", "--open-browser"]
    try:
        from drum_companion.app import run_cli

        return run_cli(argv)
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    raise SystemExit(main())
