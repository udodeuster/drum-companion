import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np
import soundfile as sf

from drum_companion.audio.analysis import analyze_wav
from drum_companion.audio.analysis import AudioAnalyzer
from drum_companion.audio.groove import GrooveFollower, generate_accompaniment, pattern_to_events
from drum_companion.audio.input import AudioBlock
from drum_companion.audio.output import PlaybackCoordinator, SampleBank, SampleMixer
from drum_companion.models import AudioAnalysisObservation


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


def make_guitar_strum_track(sample_rate: int = 22050) -> tuple[np.ndarray, tuple[float, ...]]:
    onset_times = tuple(float(value) for value in np.arange(0.25, 4.0, 0.5))
    signal = np.zeros(sample_rate * 8, dtype=np.float32)
    frequencies = (82.4, 110.0, 146.8, 196.0, 246.9, 329.6)
    duration = int(sample_rate * 0.18)
    time = np.arange(duration, dtype=np.float32) / sample_rate
    envelope = np.exp(-24.0 * time)
    for onset_time in onset_times:
        for string_index, frequency in enumerate(frequencies):
            start = round((onset_time + string_index * 0.004) * sample_rate)
            end = start + duration
            note = np.sin(2.0 * np.pi * frequency * time)
            note += 0.35 * np.sin(4.0 * np.pi * frequency * time)
            signal[start:end] += 0.045 * note * envelope
    return signal, onset_times


def make_vocal_phrase_track(sample_rate: int = 22050) -> tuple[np.ndarray, tuple[float, ...]]:
    phrases = ((0.3, 0.42), (1.25, 0.36), (2.4, 0.38), (2.95, 0.24), (4.4, 0.4), (5.1, 0.32), (6.4, 0.45))
    onset_times = tuple(start for start, _ in phrases)
    signal = np.zeros(sample_rate * 8, dtype=np.float32)
    for phrase_index, (onset_time, duration_seconds) in enumerate(phrases):
        duration = round(sample_rate * duration_seconds)
        time = np.arange(duration, dtype=np.float32) / sample_rate
        fundamental = 145.0 + phrase_index * 7.0
        envelope = np.minimum(1.0, time / 0.025) * np.minimum(
            1.0, (duration_seconds - time) / 0.04
        )
        voice = np.zeros(duration, dtype=np.float32)
        for harmonic in range(1, 16):
            frequency = fundamental * harmonic
            formant = 0.35 + np.exp(-((frequency - 720.0) / 320.0) ** 2)
            formant += 0.7 * np.exp(-((frequency - 1450.0) / 480.0) ** 2)
            voice += (formant / harmonic) * np.sin(2.0 * np.pi * frequency * time)
        start = round(onset_time * sample_rate)
        signal[start : start + duration] += 0.035 * voice * envelope
    return signal, onset_times


def make_half_double_ambiguous_track(
    sample_rate: int = 22050,
) -> tuple[np.ndarray, tuple[float, ...], tuple[float, float]]:
    onset_times = tuple(float(value) for value in np.arange(0.25, 7.0, 0.5))
    signal = np.zeros(sample_rate * 8, dtype=np.float32)
    click_length = round(sample_rate * 0.03)
    click_time = np.arange(click_length, dtype=np.float32) / sample_rate
    click = np.hanning(click_length).astype(np.float32) * np.sin(
        2.0 * np.pi * 900.0 * click_time
    )
    for index, onset_time in enumerate(onset_times):
        start = round(onset_time * sample_rate)
        velocity = 0.18 if index % 2 == 0 else 0.08
        signal[start : start + click_length] += velocity * click
    return signal, onset_times, (60.0, 120.0)


class TestAudioAnalysis(unittest.TestCase):
    def test_performance_fixtures_have_known_repeatable_ground_truth(self):
        strum, strum_onsets = make_guitar_strum_track()
        strum_repeat, _ = make_guitar_strum_track()
        vocal, vocal_onsets = make_vocal_phrase_track()
        vocal_repeat, _ = make_vocal_phrase_track()
        ambiguous, ambiguous_onsets, candidate_tempos = make_half_double_ambiguous_track()
        ambiguous_repeat, _, _ = make_half_double_ambiguous_track()

        np.testing.assert_array_equal(strum, strum_repeat)
        np.testing.assert_array_equal(vocal, vocal_repeat)
        np.testing.assert_array_equal(ambiguous, ambiguous_repeat)
        self.assertEqual(strum_onsets, tuple(np.arange(0.25, 4.0, 0.5)))
        self.assertEqual(vocal_onsets, (0.3, 1.25, 2.4, 2.95, 4.4, 5.1, 6.4))
        self.assertEqual(ambiguous_onsets, tuple(np.arange(0.25, 7.0, 0.5)))
        self.assertEqual(candidate_tempos, (60.0, 120.0))
        for signal in (strum, vocal, ambiguous):
            self.assertEqual(signal.shape, (22050 * 8,))
            self.assertTrue(np.isfinite(signal).all())
            self.assertGreater(float(np.max(np.abs(signal))), 0.0)

    def test_analyzed_guitar_and_vocal_fixtures_obey_each_onset_timeout(self):
        fixtures = (
            ("guitar", make_guitar_strum_track),
            ("vocal", make_vocal_phrase_track),
        )
        for fixture_name, make_fixture in fixtures:
            samples, _ = make_fixture()
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / f"{fixture_name}-phrases.wav"
                sf.write(path, samples, 22050)
                observations = analyze_wav(path, update_interval_seconds=0.5)
            detected_onsets = tuple(
                onset
                for observation in observations
                for onset in observation.onset_times_seconds
            )

            self.assertGreater(len(detected_onsets), 5)
            self.assertTrue(all(left < right for left, right in zip(detected_onsets, detected_onsets[1:])))
            for timeout_bars in (0, 1, 2, 4):
                with self.subTest(fixture=fixture_name, timeout_bars=timeout_bars):
                    follower = GrooveFollower(
                        style="rock",
                        feel="tight",
                        intensity=0.8,
                        onset_timeout_bars=timeout_bars,
                    )
                    follower.update(
                        AudioAnalysisObservation(0.0, (0.0,), 120.0, 0.9, 0.02, 1.0)
                    )
                    timeout_seconds = 2.0 * timeout_bars
                    last_onset = 0.0
                    onset_index = 0
                    inactive_at = None
                    final_time = detected_onsets[-1] + timeout_seconds + 0.5
                    update_count = int(np.ceil(final_time * 2.0))

                    for update_index in range(1, update_count + 1):
                        timestamp = update_index * 0.5
                        new_onsets = []
                        while (
                            onset_index < len(detected_onsets)
                            and detected_onsets[onset_index] <= timestamp
                        ):
                            if detected_onsets[onset_index] > (update_index - 1) * 0.5:
                                new_onsets.append(detected_onsets[onset_index])
                            onset_index += 1
                        if new_onsets:
                            last_onset = new_onsets[-1]
                        decision = follower.update(
                            AudioAnalysisObservation(
                                timestamp_seconds=timestamp,
                                onset_times_seconds=tuple(new_onsets),
                                tempo_bpm=None,
                                tempo_confidence=0.0,
                                combined_energy=0.02,
                                energy_confidence=1.0,
                                signal_active=True,
                            )
                        )
                        if not decision.musical_activity_active and inactive_at is None:
                            inactive_at = timestamp
                        if timeout_bars and timestamp - last_onset < timeout_seconds:
                            self.assertTrue(decision.musical_activity_active)

                    self.assertIsNotNone(inactive_at)
                    if timeout_bars:
                        self.assertGreaterEqual(inactive_at, last_onset + timeout_seconds)
                        self.assertLessEqual(inactive_at, last_onset + timeout_seconds + 0.5)

    def test_style_and_feel_candidates_render_offline_with_inspectable_timing(self):
        sample_rate = 22050
        asset_directory = Path(__file__).parents[1] / "drum_companion" / "assets" / "drums"
        bank = SampleBank.load_starter_kit(asset_directory, sample_rate=sample_rate, channels=2)
        mixer = SampleMixer(bank)
        rendered_by_style = {}

        for style in ("rock", "folk", "indie"):
            rendered_by_style[style] = {}
            for feel in ("tight", "relaxed"):
                pattern = generate_accompaniment("verse", style, feel, 0.8)
                events = pattern_to_events(pattern, tempo_bpm=96.0, feel=feel)
                frame_count = round(len(pattern) * 30.0 / 96.0 * sample_rate)
                rendered = mixer.render_events(events, frame_count)
                event_offsets = tuple(event.offset_seconds for event in events)

                self.assertTrue(events)
                self.assertEqual(event_offsets, tuple(sorted(event_offsets)))
                self.assertGreater(float(np.max(np.abs(rendered))), 0.0)
                rendered_by_style[style][feel] = rendered

        for candidates in rendered_by_style.values():
            self.assertFalse(np.array_equal(candidates["tight"], candidates["relaxed"]))

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
        self.assertGreater(paused[-1][1].effective_intensity, 0.0)
        self.assertTrue(any("K" in cell or "S" in cell for cell in paused[-1][1].pattern))

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
        self.assertEqual(paused[-1].effective_intensity, steady[-1].effective_intensity)
        self.assertEqual(paused[-1].pattern, steady[-1].pattern)
        self.assertAlmostEqual(recovered[-1].tempo_bpm, 150.0, delta=12.0)
        self.assertEqual(recovered[-1].effective_intensity, paused[-1].effective_intensity)
        self.assertTrue(any("K" in cell or "S" in cell for cell in recovered[-1].pattern))

    def test_ambiguous_pulse_confirmation_preserves_queued_frames_end_to_end(self):
        sample_rate = 22050
        samples, _, candidate_tempos = make_half_double_ambiguous_track(sample_rate)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ambiguous-pulse.wav"
            sf.write(path, samples, sample_rate)
            observations = analyze_wav(path, update_interval_seconds=0.5)

        class OfflineOutput:
            def __init__(self):
                self.sample_bank = SampleBank(
                    {"kick": np.ones((4, 1), dtype=np.float32), "snare": np.ones((4, 1), dtype=np.float32)},
                    sample_rate=1000,
                    channels=1,
                )
                self.frame_position = 0
                self.scheduled = []

            def schedule(self, event, frame_position):
                self.scheduled.append((frame_position, event))

        output = OfflineOutput()
        coordinator = PlaybackCoordinator(output, horizon_seconds=0.5, lead_in_seconds=0.0)
        follower = GrooveFollower(style="rock", feel="tight", intensity=0.8, onset_timeout_bars=4)
        initial = follower.update(
            AudioAnalysisObservation(0.0, (0.0,), 120.0, 0.9, 0.5, 1.0)
        )
        coordinator.update(initial)
        already_scheduled = tuple(output.scheduled)
        ambiguous_observations = [
            min(observations, key=lambda item: abs(item.timestamp_seconds - timestamp))
            for timestamp in (2.0, 2.5, 3.0)
        ]
        decisions = []

        for observation in ambiguous_observations:
            active_observation = replace(
                observation,
                tempo_bpm=candidate_tempos[0],
                tempo_confidence=0.9,
                combined_energy=0.5,
                signal_active=True,
            )
            output.frame_position = round(active_observation.timestamp_seconds * 1000)
            decision = follower.update(active_observation)
            decisions.append(decision)
            coordinator.update(decision)

        self.assertEqual([decision.tempo_bpm for decision in decisions], [120.0, 120.0, 60.0])
        self.assertTrue(decisions[0].holding_stable_tempo)
        self.assertEqual(coordinator.scheduler.tempo_bpm, 60.0)
        self.assertEqual(tuple(output.scheduled[: len(already_scheduled)]), already_scheduled)
        self.assertEqual(
            [frame for frame, _ in output.scheduled],
            sorted(frame for frame, _ in output.scheduled),
        )

    def test_phrase_transition_changes_future_bars_without_moving_queued_hits(self):
        sample_rate = 1000

        class OfflineOutput:
            def __init__(self):
                self.sample_bank = SampleBank(
                    {"kick": np.ones((1, 1), dtype=np.float32)},
                    sample_rate=sample_rate,
                    channels=1,
                )
                self.frame_position = 0
                self.scheduled = []

            def schedule(self, event, frame_position):
                self.scheduled.append((frame_position, event))

        output = OfflineOutput()
        coordinator = PlaybackCoordinator(output, horizon_seconds=0.5, lead_in_seconds=0.0)
        follower = GrooveFollower(style="rock", feel="tight", intensity=0.55, phrase="verse")
        scheduled_at_transition = ()

        for timestamp in (0.0, 1.5, 3.5, 4.0, 5.5, 6.0, 7.5):
            output.frame_position = round(timestamp * sample_rate)
            if timestamp >= 4.0:
                follower.phrase = "chorus"
            decision = follower.update(
                AudioAnalysisObservation(
                    timestamp_seconds=timestamp,
                    onset_times_seconds=(),
                    tempo_bpm=120.0,
                    tempo_confidence=0.9,
                    combined_energy=0.5,
                    energy_confidence=0.9,
                )
            )
            coordinator.update(decision)
            if timestamp == 4.0:
                scheduled_at_transition = tuple(output.scheduled)

        verse_kick = next(
            event for frame, event in output.scheduled
            if frame == 0 and event.instrument == "kick"
        )
        chorus_kick = next(
            event for frame, event in output.scheduled
            if frame == 6000 and event.instrument == "kick"
        )
        scheduled_frames = [frame for frame, _ in output.scheduled]

        self.assertGreater(chorus_kick.velocity, verse_kick.velocity)
        self.assertEqual(tuple(output.scheduled[: len(scheduled_at_transition)]), scheduled_at_transition)
        self.assertEqual(scheduled_frames, sorted(scheduled_frames))

    def test_offline_fixture_renders_from_analysis_through_sample_mixer(self):
        sample_rate = 22050
        source = make_pulse_track(sample_rate)
        first_section = source[: int(sample_rate * 4)]
        pause = np.zeros(sample_rate * 5, dtype=np.float32)
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
                self.gain_ramps = []

            def schedule(self, event, frame_position):
                self.scheduled.append((frame_position, event))

            def gain_at_frame(self, frame_position):
                gain = 1.0
                for start_frame, end_frame, start_gain, end_gain in self.gain_ramps:
                    if frame_position < start_frame:
                        break
                    if frame_position < end_frame:
                        progress = (frame_position - start_frame) / (end_frame - start_frame)
                        return start_gain + (end_gain - start_gain) * progress
                    gain = end_gain
                return gain

            def schedule_gain_ramp(self, start_frame, end_frame, target_gain):
                start_gain = self.gain_at_frame(start_frame)
                self.gain_ramps = [ramp for ramp in self.gain_ramps if ramp[0] < start_frame]
                self.gain_ramps.append((start_frame, end_frame, start_gain, target_gain))

            def gain_curve(self, frame_count):
                return np.fromiter(
                    (self.gain_at_frame(frame) for frame in range(frame_count)),
                    dtype=np.float32,
                    count=frame_count,
                )

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
        self.assertGreater(quiet[-1].effective_intensity, 0.0)
        self.assertAlmostEqual(recovered[-1].tempo_bpm, 150.0, delta=12.0)
        self.assertTrue(output.scheduled)

        render_events = [
            replace(event, offset_seconds=frame_position / sample_rate)
            for frame_position, event in output.scheduled
        ]
        rendered = mixer.render_events(render_events, len(audio) + sample_rate)
        rendered *= output.gain_curve(len(rendered))[:, np.newaxis]
        self.assertGreater(float(np.sum(np.square(rendered))), 0.0)
        self.assertLessEqual(float(np.max(np.abs(rendered))), 1.0)
        fade = next(ramp for ramp in output.gain_ramps if ramp[3] == 0.0)
        recovery = next(ramp for ramp in output.gain_ramps if ramp[3] == 1.0)
        self.assertTrue(any(frame == recovery[0] for frame, _ in output.scheduled))
        self.assertGreater(float(np.sum(np.square(rendered[fade[0] : fade[1]]))), 0.0)
        self.assertEqual(output.gain_at_frame(fade[1]), 0.0)
        self.assertEqual(recovery[0], fade[1])
        self.assertGreater(output.gain_at_frame(recovery[1] - 1), 0.0)
        self.assertGreater(float(np.sum(np.square(rendered[recovery[1] :]))), 0.0)


if __name__ == "__main__":
    unittest.main()