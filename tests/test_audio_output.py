import unittest

import numpy as np

from drum_companion.audio.groove import DrumEvent, pattern_to_events
from drum_companion.audio.output import (
    OutputError,
    SampleBank,
    SampleMixer,
    SampleOutput,
    PlaybackCoordinator,
    list_output_devices,
)
from drum_companion.audio.scheduler import GrooveScheduler
from drum_companion.models import GrooveDecision


OUTPUT_DEVICES = [
    {"name": "Input only", "max_output_channels": 0, "default_samplerate": 44100},
    {"name": "Speakers", "max_output_channels": 2, "default_samplerate": 10},
]


class FakeOutputStream:
    def __init__(self, callback, fail_start=False, **kwargs):
        self.callback = callback
        self.fail_start = fail_start
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self):
        if self.fail_start:
            raise RuntimeError("output device busy")
        self.started = True

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


class TestGrooveEventMapping(unittest.TestCase):
    def test_maps_pattern_cells_to_timed_instrument_events(self):
        pattern = ("AK-H", "-S-H", "----", "K---", "A---", "-S-H", "----", "---H")
        events = pattern_to_events(pattern, tempo_bpm=120.0, bar_index=1)

        self.assertEqual(
            [(event.offset_seconds, event.instrument) for event in events[:4]],
            [(0.0, "kick"), (0.0, "closed_hat"), (0.25, "snare"), (0.25, "closed_hat")],
        )
        self.assertNotIn("accent", {event.instrument for event in events})
        self.assertGreater(events[0].velocity, events[2].velocity)
        self.assertEqual(events[-1].offset_seconds, 1.75)

    def test_adds_cymbal_and_open_hat_only_on_controlled_variation_bars(self):
        pattern = ("AK-H", "-S-H", "----", "K---", "A---", "-S-H", "----", "---H")
        ordinary_bar = pattern_to_events(pattern, tempo_bpm=120.0, bar_index=1)
        variation_bar = pattern_to_events(pattern, tempo_bpm=120.0, bar_index=3)

        self.assertNotIn("cymbal", {event.instrument for event in ordinary_bar})
        self.assertNotIn("open_hat", {event.instrument for event in ordinary_bar})
        self.assertIn("cymbal", {event.instrument for event in variation_bar})
        self.assertIn("open_hat", {event.instrument for event in variation_bar})

    def test_rejects_invalid_tempo(self):
        with self.assertRaises(ValueError):
            pattern_to_events(("K---",), tempo_bpm=0.0)


class TestSampleMixer(unittest.TestCase):
    def test_mixes_overlapping_voices_with_velocity_and_master_level(self):
        samples = {
            "kick": np.full((6, 2), 0.8, dtype=np.float32),
            "snare": np.full((6, 2), 0.8, dtype=np.float32),
        }
        bank = SampleBank(samples, sample_rate=10, channels=2)
        mixer = SampleMixer(bank)
        output = mixer.render_events(
            (DrumEvent(0.0, "kick", 0.5), DrumEvent(0.2, "snare", 0.5)),
            frame_count=10,
            master_level=0.5,
        )

        self.assertEqual(output.shape, (10, 2))
        self.assertAlmostEqual(float(output[0, 0]), 0.2)
        self.assertAlmostEqual(float(output[2, 0]), 0.4)
        self.assertLessEqual(float(np.max(np.abs(output))), 1.0)

    def test_muted_or_stopped_mixer_returns_silence(self):
        bank = SampleBank({"kick": np.ones((8, 2), dtype=np.float32)}, sample_rate=10, channels=2)
        mixer = SampleMixer(bank)
        event = (DrumEvent(0.0, "kick", 1.0),)

        self.assertFalse(np.any(mixer.render_events(event, 8, muted=True)))
        self.assertFalse(np.any(mixer.render_events(event, 8, stopped=True)))

    def test_loads_and_converts_bundled_kit(self):
        from pathlib import Path

        asset_directory = Path(__file__).parents[1] / "drum_companion" / "assets" / "drums"
        bank = SampleBank.load_starter_kit(asset_directory, sample_rate=48000, channels=1)

        self.assertEqual(set(bank.samples), {"kick", "snare", "closed_hat", "open_hat", "cymbal"})
        for sample in bank.samples.values():
            self.assertEqual(sample.ndim, 2)
            self.assertEqual(sample.shape[1], 1)
            self.assertGreater(sample.shape[0], 0)
            self.assertAlmostEqual(float(np.max(np.abs(sample))), 0.95, delta=0.02)


class TestSampleOutput(unittest.TestCase):
    def make_output(self, device=1, fail_start=False):
        self.streams = []

        def stream_factory(**kwargs):
            stream = FakeOutputStream(fail_start=fail_start, **kwargs)
            self.streams.append(stream)
            return stream

        bank = SampleBank(
            {"kick": np.full((6, 2), 0.5, dtype=np.float32)},
            sample_rate=10,
            channels=2,
        )
        return SampleOutput(
            device=device,
            sample_bank=bank,
            device_query=lambda: OUTPUT_DEVICES,
            stream_factory=stream_factory,
            block_size=4,
        )

    def test_lists_only_output_devices(self):
        devices = list_output_devices(device_query=lambda: OUTPUT_DEVICES)

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].index, 1)
        self.assertEqual(devices[0].name, "Speakers")

    def test_selects_output_and_callback_renders_scheduled_sample(self):
        output = self.make_output()
        output.start()
        output.schedule(DrumEvent(0.0, "kick", 0.8), frame_position=1)
        rendered = np.empty((4, 2), dtype=np.float32)
        self.streams[0].callback(rendered, 4, None, None)
        output.stop()

        self.assertEqual(self.streams[0].kwargs["device"], 1)
        self.assertTrue(self.streams[0].stopped)
        self.assertTrue(self.streams[0].closed)
        self.assertTrue(np.allclose(rendered[0], 0.0))
        self.assertTrue(np.allclose(rendered[1:], 0.4))

    def test_reports_unavailable_device_and_stream_start_failure(self):
        missing = self.make_output(device=7)
        with self.assertRaisesRegex(OutputError, "not available"):
            missing.start()

        failing = self.make_output(fail_start=True)
        with self.assertRaisesRegex(OutputError, "output device busy"):
            failing.start()
        self.assertTrue(self.streams[0].closed)

    def test_mute_and_master_level_do_not_change_frame_schedule(self):
        output = self.make_output()
        output.start()
        output.schedule(DrumEvent(0.0, "kick", 1.0), frame_position=0)
        full_level = np.empty((4, 2), dtype=np.float32)
        self.streams[0].callback(full_level, 4, None, None)

        output.set_master_level(0.5)
        output.schedule(DrumEvent(0.0, "kick", 1.0), frame_position=6)
        half_level = np.empty((4, 2), dtype=np.float32)
        self.streams[0].callback(half_level, 4, None, None)
        output.set_muted(True)
        output.schedule(DrumEvent(0.0, "kick", 1.0), frame_position=8)
        muted = np.empty((4, 2), dtype=np.float32)
        self.streams[0].callback(muted, 4, None, None)

        self.assertTrue(np.allclose(full_level, 0.5))
        self.assertTrue(np.allclose(half_level, 0.25))
        self.assertFalse(np.any(muted))
        self.assertEqual(output.frame_position, 12)

    def test_stop_clears_pending_events_and_closes_stream(self):
        output = self.make_output()
        output.start()
        output.schedule(DrumEvent(0.0, "kick", 1.0), frame_position=20)
        output.stop()

        self.assertFalse(output.is_running)
        self.assertEqual(output.pending_event_count, 0)
        self.assertTrue(self.streams[0].stopped)
        self.assertTrue(self.streams[0].closed)


class TestGrooveScheduler(unittest.TestCase):
    def test_tempo_change_only_changes_unscheduled_bars(self):
        pattern = ("AK-H", "-S-H", "----", "K---", "A---", "-S-H", "----", "---H")
        scheduler = GrooveScheduler(pattern, tempo_bpm=120.0, sample_rate=1000)
        first_bar = scheduler.schedule_next_bar()
        first_positions = tuple(item.frame_position for item in first_bar)

        scheduler.update_tempo(60.0)
        next_bar = scheduler.schedule_next_bar()

        self.assertEqual(tuple(item.frame_position for item in first_bar), first_positions)
        self.assertEqual(first_bar[0].frame_position, 0)
        self.assertEqual(next_bar[0].frame_position, 2000)
        self.assertEqual(next_bar[2].frame_position - next_bar[0].frame_position, 500)

    def test_groove_decisions_scale_future_sample_velocity_and_recover(self):
        pattern = ("AK-H", "-S-H", "----", "K---", "A---", "-S-H", "----", "---H")
        scheduler = GrooveScheduler(pattern, tempo_bpm=120.0, sample_rate=1000)
        reliable = GrooveDecision(120.0, 0.9, 0.8, pattern, False, True)
        uncertain = GrooveDecision(120.0, 0.1, 0.36, ("----",) * 8, True, True)
        recovered = GrooveDecision(150.0, 0.8, 0.8, pattern, False, True)

        scheduler.update_decision(reliable)
        reliable_bar = scheduler.schedule_next_bar()
        scheduler.update_decision(uncertain)
        uncertain_bar = scheduler.schedule_next_bar()
        after_uncertain_frame = scheduler.next_bar_frame
        scheduler.update_decision(recovered)
        recovered_bar = scheduler.schedule_next_bar()

        reliable_hit = next(item for item in reliable_bar if item.event.instrument == "kick")
        uncertain_hit = next((item for item in uncertain_bar if item.event.instrument == "kick"), None)
        recovered_hit = next(item for item in recovered_bar if item.event.instrument == "kick")
        self.assertIsNone(uncertain_hit)
        self.assertEqual(after_uncertain_frame, 4000)
        self.assertGreater(recovered_hit.frame_position, after_uncertain_frame - 2000)
        self.assertEqual(recovered_hit.event.velocity, reliable_hit.event.velocity)
        self.assertEqual(recovered_bar[0].frame_position, 4000)


class TestPlaybackCoordinator(unittest.TestCase):
    def test_live_decisions_queue_future_bars_without_moving_existing_hits(self):
        class FakeOutput:
            frame_position = 0
            sample_bank = SampleBank(
                {"kick": np.ones((4, 2), dtype=np.float32)}, sample_rate=1000, channels=2
            )

            def __init__(self):
                self.scheduled = []

            def schedule(self, event, frame_position):
                self.scheduled.append((frame_position, event))

        pattern = ("AK-H", "-S-H", "----", "K---", "A---", "-S-H", "----", "---H")
        output = FakeOutput()
        coordinator = PlaybackCoordinator(output, horizon_seconds=0.5, lead_in_seconds=0.0)
        reliable = GrooveDecision(120.0, 0.9, 0.8, pattern, False, True)
        uncertain = GrooveDecision(120.0, 0.1, 0.0, ("----",) * 8, True, False)
        recovered = GrooveDecision(150.0, 0.8, 0.8, pattern, False, True)

        coordinator.update(reliable)
        original = tuple(output.scheduled)
        output.frame_position = 2000
        coordinator.update(uncertain)
        output.frame_position = 4000
        coordinator.update(recovered)

        self.assertEqual(tuple(output.scheduled[: len(original)]), original)
        self.assertGreater(len(output.scheduled), len(original))
        self.assertTrue(any(frame >= 4000 for frame, _ in output.scheduled[len(original) :]))

    def test_reliable_pause_and_recovery_decisions_reach_audio_callback(self):
        devices = [{"name": "Speakers", "max_output_channels": 2, "default_samplerate": 1000}]
        bank = SampleBank(
            {"kick": np.full((32, 2), 0.5, dtype=np.float32)},
            sample_rate=1000,
            channels=2,
        )
        streams = []

        def stream_factory(**kwargs):
            stream = FakeOutputStream(**kwargs)
            streams.append(stream)
            return stream

        output = SampleOutput(
            device=0,
            sample_bank=bank,
            device_query=lambda: devices,
            stream_factory=stream_factory,
        )
        output.start()
        pattern = ("K---", "----", "----", "----", "K---", "----", "----", "----")
        coordinator = PlaybackCoordinator(output, horizon_seconds=0.5, lead_in_seconds=0.0)
        reliable = GrooveDecision(120.0, 0.9, 0.8, pattern, False, True)
        pause = GrooveDecision(120.0, 0.1, 0.0, ("----",) * 8, True, False)
        recovered = GrooveDecision(150.0, 0.8, 0.8, pattern, False, True)

        coordinator.update(reliable)
        first_bar = np.empty((2000, 2), dtype=np.float32)
        streams[0].callback(first_bar, 2000, None, None)
        coordinator.update(pause)
        pause_bar = np.empty((2000, 2), dtype=np.float32)
        streams[0].callback(pause_bar, 2000, None, None)
        coordinator.update(recovered)
        recovery_bar = np.empty((1600, 2), dtype=np.float32)
        streams[0].callback(recovery_bar, 1600, None, None)
        output.stop()

        self.assertGreater(float(np.max(np.abs(first_bar))), 0.0)
        self.assertFalse(np.any(pause_bar))
        self.assertGreater(float(np.max(np.abs(recovery_bar))), 0.0)
        self.assertEqual(output.frame_position, 5600)


if __name__ == "__main__":
    unittest.main()