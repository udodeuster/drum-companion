import threading
import tempfile
import unittest
from queue import Empty
from time import monotonic
from types import SimpleNamespace

from drum_companion.control import DeviceRestartRequired, LiveAudioController
from drum_companion.audio.output import PlaybackCoordinator
from drum_companion.groove_library import GrooveLibrary, INSTRUMENTS, SavedGroove
from drum_companion.models import GrooveDecision


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


class PreviewOutput(FakeOutput):
    def __init__(self, *, fail_start=False, fail_stop=False, **kwargs):
        super().__init__(**kwargs)
        self.sample_bank = SimpleNamespace(sample_rate=1000)
        self.frame_position = 0
        self.scheduled = []
        self.fail_start = fail_start
        self.fail_stop = fail_stop
        self.callback_error = None

    def start(self):
        if self.fail_start:
            raise RuntimeError("preview output unavailable")
        self.started = True

    def schedule(self, event, frame_position):
        self.scheduled.append((frame_position, event))

    def stop(self):
        self.stopped = True
        if self.fail_stop:
            raise RuntimeError("preview output close failed")


class TestLiveAudioController(unittest.TestCase):
    def wait_for_state(self, controller, state):
        deadline = monotonic() + 1.0
        while monotonic() < deadline:
            if controller.snapshot()["state"] == state:
                return
            threading.Event().wait(0.01)
        self.fail(f"controller did not reach state {state}")

    def wait_for_preview_state(self, controller, state):
        deadline = monotonic() + 1.0
        while monotonic() < deadline:
            if controller.snapshot()["preview"]["state"] == state:
                return
            threading.Event().wait(0.01)
        self.fail(f"preview did not reach state {state}")

    @staticmethod
    def preview_draft(instrument="kick", level=1.0):
        tracks = {name: [False] * 16 for name in INSTRUMENTS}
        tracks[instrument][0] = True
        levels = {name: 1.0 for name in INSTRUMENTS}
        levels[instrument] = level
        return {
            "tracks": tracks,
            "levels": levels,
        }

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

    def test_saved_groove_selection_is_validated_and_can_return_to_auto(self):
        with tempfile.TemporaryDirectory() as directory:
            library = GrooveLibrary(f"{directory}\\grooves.json")
            groove = SavedGroove.create(
                "Verse",
                {instrument: [False] * 16 for instrument in INSTRUMENTS},
                {instrument: 1.0 for instrument in INSTRUMENTS},
            )
            library.save_groove(groove)
            controller = LiveAudioController(groove_library=library)

            self.assertEqual(
                controller.update_settings({"selected_groove_id": groove.id})["selected_groove_id"],
                groove.id,
            )
            self.assertIsNone(controller.update_settings({"selected_groove_id": None})["selected_groove_id"])
            with self.assertRaisesRegex(ValueError, "does not exist"):
                controller.update_settings({"selected_groove_id": "22345678-1234-5678-1234-567812345678"})
            with self.assertRaisesRegex(ValueError, "UUID"):
                controller.update_settings({"selected_groove_id": "not-an-id"})

    def test_deleting_selected_groove_falls_back_to_auto(self):
        with tempfile.TemporaryDirectory() as directory:
            library = GrooveLibrary(f"{directory}\\grooves.json")
            tracks = {instrument: [False] * 16 for instrument in INSTRUMENTS}
            levels = {instrument: 1.0 for instrument in INSTRUMENTS}
            controller = LiveAudioController(groove_library=library)
            groove = controller.save_saved_groove({"name": "Verse", "tracks": tracks, "levels": levels})
            renamed = controller.save_saved_groove({**groove, "name": "Chorus"})
            controller.update_settings({"selected_groove_id": groove["id"]})

            self.assertEqual(renamed["id"], groove["id"])
            self.assertEqual([item["name"] for item in controller.list_saved_grooves()], ["Chorus"])
            result = controller.delete_saved_groove(groove["id"])

            self.assertIsNone(result["settings"]["selected_groove_id"])
            self.assertEqual(controller.list_saved_grooves(), [])
            with self.assertRaises(LookupError):
                controller.delete_saved_groove(groove["id"])
            with self.assertRaises(ValueError):
                controller.delete_saved_groove(None)

    def test_saving_as_creates_a_copy_without_changing_the_source_groove(self):
        with tempfile.TemporaryDirectory() as directory:
            library = GrooveLibrary(f"{directory}\\grooves.json")
            controller = LiveAudioController(groove_library=library)
            source_tracks = {instrument: [False] * 16 for instrument in INSTRUMENTS}
            source_tracks["kick"][0] = True
            levels = {instrument: 1.0 for instrument in INSTRUMENTS}
            source = controller.save_saved_groove(
                {"name": "Verse", "tracks": source_tracks, "levels": levels}
            )
            edited_tracks = {instrument: list(source_tracks[instrument]) for instrument in INSTRUMENTS}
            edited_tracks["snare"][4] = True

            saved_copy = controller.save_saved_groove(
                {"name": "Verse Copy", "tracks": edited_tracks, "levels": levels}
            )
            self.assertFalse(library.get_groove(source["id"]).tracks["snare"][4])
            updated_source = controller.save_saved_groove(
                {
                    "id": source["id"],
                    "name": source["name"],
                    "tracks": edited_tracks,
                    "levels": levels,
                }
            )

            self.assertNotEqual(saved_copy["id"], source["id"])
            self.assertEqual(updated_source["id"], source["id"])
            self.assertTrue(library.get_groove(source["id"]).tracks["snare"][4])
            self.assertTrue(library.get_groove(saved_copy["id"]).tracks["snare"][4])
            self.assertEqual(
                {groove["name"] for groove in controller.list_saved_grooves()},
                {"Verse", "Verse Copy"},
            )

    def test_live_groove_draft_overrides_auto_output_without_persisting(self):
        output = PreviewOutput()
        with tempfile.TemporaryDirectory() as directory:
            controller = LiveAudioController(
                groove_library=GrooveLibrary(f"{directory}\\grooves.json")
            )
            draft = self.preview_draft("snare", 0.5)
            for instrument in INSTRUMENTS:
                if instrument != "snare":
                    draft["levels"][instrument] = 0.0
            controller.update_live_groove_draft(
                {"selected_groove_id": None, **draft}
            )
            decision = GrooveDecision(
                tempo_bpm=120.0,
                tempo_confidence=1.0,
                effective_intensity=0.8,
                pattern=("K",) * 8,
                holding_stable_tempo=False,
                signal_active=True,
            )
            coordinator = PlaybackCoordinator(output, horizon_seconds=3.0)
            coordinator.update(decision, controller._groove_for_playback(controller.settings))

            audible_events = [
                event.instrument for _, event in output.scheduled if event.velocity > 0
            ]
            self.assertTrue(audible_events)
            self.assertEqual(set(audible_events), {"snare"})
            self.assertEqual(controller.list_saved_grooves(), [])

            source_tracks = {instrument: [False] * 16 for instrument in INSTRUMENTS}
            source_tracks["kick"][0] = True
            source = controller.save_saved_groove(
                {
                    "name": "Saved",
                    "tracks": source_tracks,
                    "levels": {instrument: 1.0 for instrument in INSTRUMENTS},
                }
            )
            controller.update_settings({"selected_groove_id": source["id"]})
            selected = controller._groove_for_playback(controller.settings)
            self.assertTrue(selected.tracks["kick"][0])
            self.assertFalse(selected.tracks["snare"][0])

    def test_saving_selected_groove_is_allowed_during_live_playback(self):
        with tempfile.TemporaryDirectory() as directory:
            library = GrooveLibrary(f"{directory}\\grooves.json")
            controller = LiveAudioController(
                capture_factory=IdleCapture,
                output_factory=FakeOutput,
                groove_library=library,
            )
            groove = controller.save_saved_groove(
                {"name": "Active", **self.preview_draft()}
            )
            controller.update_settings({"selected_groove_id": groove["id"]})
            controller.start()
            try:
                self.wait_for_state(controller, "running")
                tracks = {instrument: [False] * 16 for instrument in INSTRUMENTS}
                tracks["snare"][4] = True
                updated = controller.save_saved_groove(
                    {
                        "id": groove["id"],
                        "name": groove["name"],
                        "tracks": tracks,
                        "levels": groove["levels"],
                    }
                )

                self.assertEqual(updated["tracks"]["snare"][4], True)
                self.assertEqual(controller.snapshot()["state"], "running")
                self.assertEqual(
                    controller.snapshot()["settings"]["selected_groove_id"],
                    groove["id"],
                )
                self.assertEqual(library.get_groove(groove["id"]).tracks["snare"][4], True)
            finally:
                controller.stop()

    def test_saving_non_selected_groove_does_not_change_live_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            library = GrooveLibrary(f"{directory}\\grooves.json")
            controller = LiveAudioController(
                capture_factory=IdleCapture,
                output_factory=FakeOutput,
                groove_library=library,
            )
            active = controller.save_saved_groove(
                {"name": "Active", **self.preview_draft()}
            )
            other = controller.save_saved_groove(
                {"name": "Other", **self.preview_draft("snare")}
            )
            controller.update_settings({"selected_groove_id": active["id"]})
            controller.start()
            try:
                self.wait_for_state(controller, "running")
                tracks = {instrument: [False] * 16 for instrument in INSTRUMENTS}
                tracks["ride"][8] = True
                updated = controller.save_saved_groove(
                    {
                        "id": other["id"],
                        "name": other["name"],
                        "tracks": tracks,
                        "levels": other["levels"],
                    }
                )

                self.assertTrue(updated["tracks"]["ride"][8])
                self.assertEqual(controller.snapshot()["state"], "running")
                self.assertEqual(
                    controller.snapshot()["settings"]["selected_groove_id"],
                    active["id"],
                )
                self.assertEqual(library.get_groove(active["id"]), SavedGroove(**active))
            finally:
                controller.stop()

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

    def test_preview_uses_default_or_last_live_tempo_and_validates_manual_tempo(self):
        output = PreviewOutput()
        controller = LiveAudioController(output_factory=lambda **kwargs: output)

        self.assertEqual(controller.snapshot()["preview"]["tempo_bpm"], 100.0)
        controller.start_preview(self.preview_draft())
        self.wait_for_preview_state(controller, "running")
        self.assertEqual(controller.snapshot()["preview"]["tempo_bpm"], 100.0)
        controller.stop_preview()

        with controller._lock:
            controller._last_detected_tempo_bpm = 126.5
        controller.start_preview(self.preview_draft())
        self.wait_for_preview_state(controller, "running")
        self.assertEqual(controller.snapshot()["preview"]["tempo_bpm"], 126.5)
        controller.stop_preview()

        for tempo in (29, 301, True, "120"):
            with self.assertRaisesRegex(ValueError, "Preview tempo"):
                controller.start_preview({**self.preview_draft(), "tempo_bpm": tempo})
        controller.start_preview({**self.preview_draft(), "tempo_bpm": 300})
        self.wait_for_preview_state(controller, "running")
        self.assertEqual(controller.snapshot()["preview"]["tempo_bpm"], 300.0)
        controller.stop_preview()

    def test_preview_is_independent_of_capture_and_exclusive_with_live_session(self):
        output = PreviewOutput()
        capture = IdleCapture()
        controller = LiveAudioController(
            capture_factory=lambda **kwargs: capture,
            output_factory=lambda **kwargs: output,
        )

        controller.start_preview(self.preview_draft())
        self.wait_for_preview_state(controller, "running")
        with self.assertRaisesRegex(RuntimeError, "Stop the groove preview"):
            controller.start()
        self.assertFalse(capture.started)
        controller.stop_preview()
        self.assertTrue(output.stopped)

        controller.start()
        self.wait_for_state(controller, "running")
        with self.assertRaisesRegex(RuntimeError, "Stop the live session"):
            controller.start_preview(self.preview_draft())
        controller.stop()
        self.assertTrue(capture.stopped)

    def test_preview_applies_unsaved_draft_at_next_bar_and_reports_output_failures(self):
        output = PreviewOutput()
        with tempfile.TemporaryDirectory() as directory:
            controller = LiveAudioController(
                output_factory=lambda **kwargs: output,
                groove_library=GrooveLibrary(f"{directory}\\grooves.json"),
            )
            controller.start_preview({**self.preview_draft("kick"), "tempo_bpm": 300})
            self.wait_for_preview_state(controller, "running")
            deadline = monotonic() + 1.0
            while not output.scheduled and monotonic() < deadline:
                threading.Event().wait(0.01)
            self.assertTrue(output.scheduled)
            first_bar = tuple(output.scheduled)

            controller.update_preview(
                {**self.preview_draft("snare", 0.5), "tempo_bpm": 300}
            )
            output.frame_position = 800
            deadline = monotonic() + 1.0
            while len(output.scheduled) == len(first_bar) and monotonic() < deadline:
                threading.Event().wait(0.01)

            self.assertEqual(tuple(output.scheduled[: len(first_bar)]), first_bar)
            second_bar_hits = [
                (frame, event.instrument)
                for frame, event in output.scheduled[len(first_bar) :]
                if event.velocity > 0
            ]
            self.assertEqual(second_bar_hits, [(900, "snare")])
            second_bar_event = next(
                event
                for frame, event in output.scheduled[len(first_bar) :]
                if frame == 900 and event.instrument == "snare"
            )
            self.assertAlmostEqual(second_bar_event.velocity, 0.72 * 0.5 * 0.8)
            self.assertEqual(controller.list_saved_grooves(), [])
            controller.stop_preview()
            self.assertTrue(output.stopped)

        failed_output = PreviewOutput(fail_start=True)
        failed_controller = LiveAudioController(
            output_factory=lambda **kwargs: failed_output
        )
        failed_controller.start_preview(self.preview_draft())
        self.wait_for_preview_state(failed_controller, "error")
        self.assertIn("preview output unavailable", failed_controller.snapshot()["preview"]["error"])
        self.assertTrue(failed_output.stopped)

        callback_failure = PreviewOutput()
        callback_controller = LiveAudioController(
            output_factory=lambda **kwargs: callback_failure
        )
        callback_controller.start_preview(self.preview_draft())
        self.wait_for_preview_state(callback_controller, "running")
        deadline = monotonic() + 1.0
        while not callback_failure.scheduled and monotonic() < deadline:
            threading.Event().wait(0.01)
        callback_failure.callback_error = "audio callback failed"
        self.wait_for_preview_state(callback_controller, "error")
        self.assertEqual(
            callback_controller.snapshot()["preview"]["error"],
            "audio callback failed",
        )
        self.assertTrue(callback_failure.stopped)

        close_failure = PreviewOutput(fail_stop=True)
        close_controller = LiveAudioController(
            output_factory=lambda **kwargs: close_failure
        )
        close_controller.start_preview(self.preview_draft())
        self.wait_for_preview_state(close_controller, "running")
        close_controller.stop_preview()
        self.assertEqual(close_controller.snapshot()["preview"]["state"], "error")
        self.assertIn("preview output close failed", close_controller.snapshot()["preview"]["error"])


if __name__ == "__main__":
    unittest.main()