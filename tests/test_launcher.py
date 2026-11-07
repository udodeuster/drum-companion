"""Tests for executable startup and windowed logging behavior."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from drum_companion import launcher


class TestLauncher(unittest.TestCase):
    """Test launcher behavior."""
    def test_missing_streams_are_redirected_to_log_file(self):
        """Exercise the `missing streams are redirected to log file` test scenario.

        Returns:
            None: No value is returned.
        """
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict("os.environ", {"LOCALAPPDATA": directory}), mock.patch.object(
                sys, "stdout", None
            ), mock.patch.object(sys, "stderr", None):
                launcher.ensure_streams()
                print("hello")
                sys.stdout.flush()
                log = Path(directory) / "DrumCompanion" / "app.log"
                self.assertIn("hello", log.read_text(encoding="utf-8"))
                sys.stdout.close()

    def test_no_arguments_start_web_mode_and_open_browser(self):
        """Exercise the `no arguments start web mode and open browser` test scenario.

        Returns:
            None: No value is returned.
        """
        with mock.patch.object(sys, "argv", ["DrumCompanion.exe"]), mock.patch(
            "drum_companion.app.run_cli", return_value=0
        ) as run_cli:
            self.assertEqual(launcher.main(), 0)
        run_cli.assert_called_once_with(["--web", "--open-browser"])


if __name__ == "__main__":
    unittest.main()
