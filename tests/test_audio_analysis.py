import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np
import soundfile as sf

from drum_companion.audio.analysis import analyze_wav
from drum_companion.audio.analysis import AudioAnalyzer
from drum_companion.audio.groove import GrooveFollower
from drum_companion.audio.input import AudioBlock
from drum_companion.audio.output import PlaybackCoordinator, SampleBank, SampleMixer


def make_pulse_track(sample_rate: int = 22050) -> np.ndarray:
    duration_seconds = 12.0
    signal = np.zeros(int(sample_rate * duration_seconds), dtype=np.float32)
    click_length = int(sample_rate * 0.025)
    click = np.hanning(click_length).astype(np.float32) * np.sin(
        2 * np.pi * 700 * np.arange(click_length) / sample_rate
    )
    times = list(np.arange(0.2, 5.8, 0.5))
    times.extend(np.arange(6.0, 11.7, 0.4))
    for timestamp in times:
        start = int(timestamp * sample_rate)
        signal[start : start + click_length] += click
    return signal


class TestAudioAnalysis(unittest.TestCase):
    def test_wav_analysis_tracks_tempo_shift_and_absolute_onsets(self):
        sample_rate = 22050
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pulse-shift.wav"
            sf.write(path, make_pulse_track(sample_rate), sample_rate)
            observations = analyze_wav(path, update_interval_seconds=0.5)

        stable = [item for item in observations if 3.0 <= item.timestamp_seconds <= 5.5]
        changed = [item for item in observations if 10.0 <= item.timestamp_seconds <= 11.5]
        self.assertTrue(stable)
        self.assertTrue(changed)
        self.assertAlmostEqual(stable[-1].tempo_bpm, 120.0, delta=8.0)
        self.assertAlmostEqual(changed[-1].tempo_bpm, 150.0, delta=12.0)

        onset_times = [onset for item in observations for onset in item.onset_times_seconds]
        self.assertGreater(len(onset_times), 12)
        self.assertTrue(all(left < right for left, right in zip(onset_times, onset_times[1:])))
        self.assertTrue(all(0.0 <= item.combined_energy <= 1.0 for item in observations))

    def test_pause_lowers_tempo_confidence_and_reports_phrase_break(self):
        sample_rate = 22050
        first = make_pulse_track(sample_rate)[: int(sample_rate * 4)]
        second = make_pulse_track(sample_rate)[int(sample_rate * 6) : int(sample_rate * 10)]
        signal = np.concatenate((first, np.zeros(sample_rate * 2, dtype=np.float32), second))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "phrase-pause.wav"
            sf.write(path, signal, sample_rate)
            observations = analyze_wav(path, update_interval_seconds=0.5)

        stable = [item for item in observations if 2.5 <= item.timestamp_seconds <= 3.8]
        paused = [item for item in observations if 4.8 <= item.timestamp_seconds <= 5.8]
        resumed = [item for item in observations if 8.0 <= item.timestamp_seconds <= 9.5]
        self.assertTrue(stable)
        self.assertTrue(paused)
        self.assertTrue(resumed)
        self.assertGreater(stable[-1].tempo_confidence, 0.2)
        self.assertLess(paused[-1].tempo_confidence, stable[-1].tempo_confidence)
        self.assertFalse(paused[-1].signal_active)
        self.assertIsNotNone(paused[-1].phrase_break_confidence)
        self.assertGreater(paused[-1].phrase_break_confidence, 0.4)
        self.assertTrue(any(item.tempo_bpm is not None for item in resumed))
        self.assertFalse(hasattr(paused[-1], "phrase"))

    def test_irregular_attacks_do_not_claim_a_reliable_tempo(self):
        sample_rate = 22050
        signal = np.zeros(sample_rate * 8, dtype=np.float32)
        click_length = int(sample_rate * 0.025)
        click = np.hanning(click_length).astype(np.float32) * np.sin(
            2 * np.pi * 700 * np.arange(click_length) / sample_rate
        )
        for timestamp in (0.2, 0.55, 1.4, 2.2, 2.35, 4.0, 4.8, 6.5, 7.1):
            start = int(timestamp * sample_rate)
            signal[start : start + click_length] += click

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "irregular.wav"
            sf.write(path, signal, sample_rate)
            observations = analyze_wav(path, update_interval_seconds=0.5)

        latest = observations[-1]
        self.assertLess(latest.tempo_confidence, 0.5)
        self.assertFalse(hasattr(latest, "phrase"))

    def test_analyzed_blocks_update_and_hold_groove_tempo(self):
        sample_rate = 22050
        signal = make_pulse_track(sample_rate)[: int(sample_rate * 4)]
        signal = np.concatenate((signal, np.zeros(sample_rate * 2, dtype=np.float32)))
        analyzer = AudioAnalyzer(sample_rate, update_interval_seconds=0.5)
        follower = GrooveFollower(style="rock", feel="tight", intensity=0.8)
        decisions = []

        for offset in range(0, len(signal), 1024):
            block = signal[offset : offset + 1024]
            observation = analyzer.process_block(
                AudioBlock(block, sample_rate, offset / sample_rate)
            )
            if observation is not None:
                decisions.append((observation, follower.update(observation)))

        reliable = [item for item in decisions if item[1].tempo_bpm is not None]
        paused = [item for item in decisions if not item[0].signal_active]
        self.assertTrue(reliable)
        self.assertTrue(paused)
        self.assertAlmostEqual(reliable[-1][1].tempo_bpm, 120.0, delta=8.0)
        self.assertEqual(paused[-1][1].tempo_bpm, reliable[-1][1].tempo_bpm)
        self.assertEqual(paused[-1][1].effective_intensity, 0.0)

    def test_end_to_end_tempo_shift_pause_and_recovery(self):
        sample_rate = 22050
        signal = make_pulse_track(sample_rate)
        first = signal[: int(sample_rate * 4)]
        second = np.zeros(sample_rate * 2, dtype=np.float32)
        third = np.zeros(sample_rate * 6, dtype=np.float32)
        click_length = int(sample_rate * 0.025)
        click = np.hanning(click_length).astype(np.float32) * np.sin(
            2 * np.pi * 700 * np.arange(click_length) / sample_rate
        )
        for timestamp in np.arange(0.2, 5.8, 0.4):
            start = int(timestamp * sample_rate)
            third[start : start + click_length] += click
        audio = np.concatenate((first, second, third))
        analyzer = AudioAnalyzer(sample_rate, update_interval_seconds=0.5)
        follower = GrooveFollower(style="rock", feel="tight", intensity=0.8)
        updates = []

        for offset in range(0, len(audio), 1024):
            block = audio[offset : offset + 1024]
            observation = analyzer.process_block(
                AudioBlock(block, sample_rate, offset / sample_rate)
            )
            if observation is not None:
                updates.append((observation, follower.update(observation)))

        steady = [decision for observation, decision in updates if 2.5 <= observation.timestamp_seconds <= 3.8]
        paused = [decision for observation, decision in updates if 5.0 <= observation.timestamp_seconds <= 5.8]
        recovered = [decision for observation, decision in updates if 10.0 <= observation.timestamp_seconds <= 11.5]
        self.assertTrue(steady)
        self.assertTrue(paused)
        self.assertTrue(recovered)
        self.assertAlmostEqual(steady[-1].tempo_bpm, 120.0, delta=8.0)
        self.assertEqual(paused[-1].tempo_bpm, steady[-1].tempo_bpm)
        self.assertEqual(paused[-1].effective_intensity, 0.0)
        self.assertAlmostEqual(recovered[-1].tempo_bpm, 150.0, delta=12.0)
        self.assertGreater(recovered[-1].effective_intensity, paused[-1].effective_intensity)

    def test_offline_fixture_renders_from_analysis_through_sample_mixer(self):
        sample_rate = 22050
        source = make_pulse_track(sample_rate)
        first_section = source[: int(sample_rate * 4)]
        pause = np.zeros(sample_rate * 2, dtype=np.float32)
        faster_section = np.zeros(sample_rate * 6, dtype=np.float32)
        click_length = int(sample_rate * 0.025)
        click = np.hanning(click_length).astype(np.float32) * np.sin(
            2 * np.pi * 700 * np.arange(click_length) / sample_rate
        )
        for timestamp in np.arange(0.2, 5.8, 0.4):
            start = int(timestamp * sample_rate)
            faster_section[start : start + click_length] += click
        audio = np.concatenate((first_section, pause, faster_section))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "output-fixture.wav"
            sf.write(path, audio, sample_rate)
            observations = analyze_wav(path, update_interval_seconds=0.5)

        asset_directory = Path(__file__).parents[1] / "drum_companion" / "assets" / "drums"
        bank = SampleBank.load_starter_kit(asset_directory, sample_rate=sample_rate, channels=2)
        mixer = SampleMixer(bank)

        class OfflineOutput:
            def __init__(self):
                self.sample_bank = bank
                self.frame_position = 0
                self.scheduled = []

            def schedule(self, event, frame_position):
                self.scheduled.append((frame_position, event))

        output = OfflineOutput()
        coordinator = PlaybackCoordinator(output, horizon_seconds=0.5, lead_in_seconds=0.05)
        follower = GrooveFollower(style="rock", feel="tight", intensity=0.8)
        decisions = []
        for observation in observations:
            output.frame_position = round(observation.timestamp_seconds * sample_rate)
            decision = follower.update(observation)
            decisions.append((observation, decision))
            coordinator.update(decision)

        stable = [decision for observation, decision in decisions if 2.5 <= observation.timestamp_seconds <= 3.8]
        quiet = [decision for observation, decision in decisions if not observation.signal_active]
        recovered = [decision for observation, decision in decisions if 9.0 <= observation.timestamp_seconds <= 11.5]
        self.assertTrue(stable and quiet and recovered)
        self.assertAlmostEqual(stable[-1].tempo_bpm, 120.0, delta=8.0)
        self.assertEqual(quiet[-1].effective_intensity, 0.0)
        self.assertAlmostEqual(recovered[-1].tempo_bpm, 150.0, delta=12.0)
        self.assertTrue(output.scheduled)

        render_events = [
            replace(event, offset_seconds=frame_position / sample_rate)
            for frame_position, event in output.scheduled
        ]
        rendered = mixer.render_events(render_events, len(audio) + sample_rate)
        self.assertGreater(float(np.sum(np.square(rendered))), 0.0)
        self.assertLessEqual(float(np.max(np.abs(rendered))), 1.0)


if __name__ == "__main__":
    unittest.main()