import threading
import unittest
from queue import Empty
from time import monotonic
from types import SimpleNamespace

from drum_companion.control import DeviceRestartRequired, LiveAudioController


class IdleCapture:
    def __init__(self, **kwargs):
        self.started = False
        self.stopped = False
        self._release = threading.Event()

    def start(self):
        self.started = True

    def read(self, timeout=None):
        self._release.wait(timeout)
        raise Empty

    def stop(self):
        self.stopped = True
        self._release.set()


class FakeOutput:
    def __init__(self, **kwargs):
        self.sample_bank = SimpleNamespace(sample_rate=1000)
        self.master_level = 1.0
        self.is_muted = False
        self.started = False
        self.stopped = False

    def set_master_level(self, level):
        self.master_level = level

    def set_muted(self, muted):
        self.is_muted = muted

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class TestLiveAudioController(unittest.TestCase):
    def wait_for_state(self, controller, state):
        deadline = monotonic() + 1.0
        while monotonic() < deadline:
            if controller.snapshot()["state"] == state:
                return
            threading.Event().wait(0.01)
        self.fail(f"controller did not reach state {state}")

    def test_worker_start_runtime_controls_and_stop(self):
        capture = IdleCapture()
        output = FakeOutput()
        controller = LiveAudioController(
            capture_factory=lambda **kwargs: capture,
            output_factory=lambda **kwargs: output,
        )

        controller.start()
        self.wait_for_state(controller, "running")
        updated = controller.update_settings(
            {"style": "folk", "phrase": "chorus", "master_level": 0.35, "muted": True}
        )
        with self.assertRaises(DeviceRestartRequired):
            controller.update_settings({"input_device": 2})

        self.assertEqual(updated["style"], "folk")
        self.assertEqual(updated["phrase"], "chorus")
        self.assertEqual(output.master_level, 0.35)
        self.assertTrue(output.is_muted)
        self.assertTrue(output.started)

        controller.stop()

        self.assertEqual(controller.snapshot()["state"], "stopped")
        self.assertTrue(capture.started)
        self.assertTrue(capture.stopped)
        self.assertTrue(output.stopped)

    def test_device_selection_and_setting_validation_while_stopped(self):
        controller = LiveAudioController()

        self.assertEqual(controller.settings.onset_timeout_bars, 1)
        for timeout in (0, 1, 2, 4):
            updated = controller.update_settings({"onset_timeout_bars": timeout})
            self.assertEqual(updated["onset_timeout_bars"], timeout)

        updated = controller.update_settings({"input_device": 1, "output_device": 3})

        self.assertEqual(updated["input_device"], 1)
        self.assertEqual(updated["output_device"], 3)
        with self.assertRaisesRegex(ValueError, "intensity"):
            controller.update_settings({"intensity": 1.2})
        for timeout in (-1, 3, 1.5, True):
            with self.assertRaisesRegex(ValueError, "onset_timeout_bars"):
                controller.update_settings({"onset_timeout_bars": timeout})
        with self.assertRaisesRegex(ValueError, "Unsupported setting"):
            controller.update_settings({"unknown": True})

    def test_tempo_range_settings_are_validated_together(self):
        controller = LiveAudioController()

        self.assertEqual((controller.settings.min_tempo_bpm, controller.settings.max_tempo_bpm), (40, 140))
        updated = controller.update_settings({"min_tempo_bpm": 50, "max_tempo_bpm": 120})
        self.assertEqual((updated["min_tempo_bpm"], updated["max_tempo_bpm"]), (50, 120))
        with self.assertRaisesRegex(ValueError, "twice"):
            controller.update_settings({"min_tempo_bpm": 70})
        with self.assertRaisesRegex(ValueError, "min_tempo_bpm"):
            controller.update_settings({"min_tempo_bpm": 10})
        self.assertEqual(controller.settings.min_tempo_bpm, 50)


if __name__ == "__main__":
    unittest.main()