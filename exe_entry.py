"""Windowed entry point for launching the app and flushing output streams."""

import os
import sys

from drum_companion.launcher import main

if __name__ == "__main__":
    code = main()
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            stream.flush()
    # Leftover audio worker threads must not keep the windowed app alive after Quit.
    os._exit(code)
