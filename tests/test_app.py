"""Tests for command-line behavior, analysis models, and playback controls."""

import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

from drum_companion.audio.analysis import estimate_performance_context
from drum_companion.audio.groove import GrooveFollower, build_pattern, generate_accompaniment
from drum_companion.audio.input import CaptureError, InputDevice
from drum_companion.audio.output import OutputDevice, OutputError
from drum_companion.models import AudioAnalysisObservation
from drum_companion.ui import GrooveDashboard, InteractionPreset


class TestDrumCompanionScaffold(unittest.TestCase):
    """Test drum companion scaffold behavior."""
    def test_estimate_performance_context(self):
        """Exercise the `estimate performance context` test scenario.

        Returns:
            None: No value is returned.
        """
        context = estimate_performance_context(96.0, 0.8, 0.9, phrase="chorus")
        self.assertAlmostEqual(context.tempo_bpm, 96.0)
        self.assertEqual(context.phrase, "chorus")
        self.assertGreaterEqual(context.confidence, 0.0)
        self.assertLessEqual(context.confidence, 1.0)

    def test_build_pattern(self):
        """Exercise the `build pattern` test scenario.

        Returns:
            None: No value is returned.
        """
        pattern = build_pattern("rock", "tight", 0.8, bars=1)
        self.assertEqual(len(pattern), 8)
        self.assertTrue(all(isinstance(cell, str) and len(cell) == 3 for cell in pattern))

    def test_generate_accompaniment_respects_phrase_and_feel(self):
        """Exercise the `generate accompaniment respects phrase and feel` test scenario.

        Returns:
            None: No value is returned.
        """
        accompaniment = generate_accompaniment("chorus", "rock", "relaxed", 0.9)
        self.assertIn("A", accompaniment[0])
        self.assertLess(len(accompaniment), 17)

    def test_nonzero_intensity_preserves_core_kick_and_backbeat(self):
        """Exercise the `nonzero intensity preserves core kick and backbeat` test...

        Returns:
            None: No value is returned.
        """
        for style in ("rock", "folk", "indie"):
            reference = None
            for feel in ("tight", "relaxed"):
                for intensity in (0.01, 0.2, 0.55, 1.0):
                    pattern = generate_accompaniment("verse", style, feel, intensity)
                    core_events = tuple(
                        (index, tuple(instrument for instrument in "KS" if instrument in cell))
                        for index, cell in enumerate(pattern)
                        if "K" in cell or "S" in cell
                    )
                    if reference is None:
                        reference = core_events
                    self.assertEqual(core_events, reference)

    def test_relaxed_ghost_snares_follow_auditioned_style_choices(self):
        """Exercise the `relaxed ghost snares follow auditioned style choices` test...

        Returns:
            None: No value is returned.
        """
        for style in ("rock", "folk", "indie"):
            tight = generate_accompaniment("verse", style, "tight", 0.8)
            relaxed = generate_accompaniment("verse", style, "relaxed", 0.8)
            expected_ghost_steps = (1, 5) if style in {"rock", "folk"} else ()

            self.assertEqual(
                tuple(index for index, cell in enumerate(relaxed) if "g" in cell),
                expected_ghost_steps,
            )
            self.assertFalse(any("g" in cell for cell in tight))

    def test_dashboard_renders_status(self):
        """Exercise the `dashboard renders status` test scenario.

        Returns:
            None: No value is returned.
        """
        dashboard = GrooveDashboard(tempo=96.0, phrase="chorus", style="rock", feel="tight", intensity=0.8)
        screen = dashboard.render()
        self.assertIn("96.0 BPM", screen)
        self.assertIn("chorus", screen.lower())
        self.assertIn("rock", screen.lower())

    def test_interaction_preset_parses_user_input(self):
        """Exercise the `interaction preset parses user input` test scenario.

        Returns:
            None: No value is returned.
        """
        preset = InteractionPreset.from_input("chorus", "rock", "tight", "0.8")
        self.assertEqual(preset.phrase, "chorus")
        self.assertEqual(preset.style, "rock")
        self.assertEqual(preset.feel, "tight")
        self.assertAlmostEqual(preset.intensity, 0.8)

    def test_audio_observation_models_combined_input_and_independent_confidence(self):
        """Exercise the `audio observation models combined input and independent...

        Returns:
            None: No value is returned.
        """
        observation = AudioAnalysisObservation(
            timestamp_seconds=2.0,
            onset_times_seconds=(1.5, 2.0),
            tempo_bpm=120.0,
            tempo_confidence=0.85,
            combined_energy=0.6,
            energy_confidence=0.9,
        )

        self.assertEqual(observation.onset_times_seconds, (1.5, 2.0))
        self.assertEqual(observation.combined_energy, 0.6)
        self.assertEqual(observation.tempo_confidence, 0.85)
        self.assertFalse(hasattr(observation, "guitar_energy"))
        self.assertFalse(hasattr(observation, "voice_energy"))

    def test_audio_observation_rejects_out_of_range_confidence(self):
        """Exercise the `audio observation rejects out of range confidence` test...

        Returns:
            None: No value is returned.
        """
        with self.assertRaises(ValueError):
            AudioAnalysisObservation(
                timestamp_seconds=0.0,
                onset_times_seconds=(),
                tempo_bpm=None,
                tempo_confidence=1.1,
                combined_energy=0.0,
                energy_confidence=0.0,
            )

    def test_groove_follower_holds_stable_tempo_and_reduces_low_confidence_energy(self):
        """Exercise the `groove follower holds stable tempo and reduces low...

        Returns:
            None: No value is returned.
        """
        follower = GrooveFollower(style="rock", feel="tight", intensity=0.8, phrase="verse")
        stable = follower.update(
            AudioAnalysisObservation(1.0, (0.5, 1.0), 120.0, 0.9, 0.5, 0.9)
        )
        uncertain = follower.update(
            AudioAnalysisObservation(1.5, (), 90.0, 0.1, 0.1, 0.5, signal_active=False)
        )

        self.assertEqual(stable.tempo_bpm, 120.0)
        self.assertEqual(uncertain.tempo_bpm, 120.0)
        self.assertTrue(uncertain.holding_stable_tempo)
        self.assertEqual(uncertain.effective_intensity, stable.effective_intensity)
        self.assertEqual(uncertain.pattern, stable.pattern)

    def test_groove_follower_preserves_groove_through_active_confidence_dips(self):
        """Exercise the `groove follower preserves groove through active confidence...

        Returns:
            None: No value is returned.
        """
        follower = GrooveFollower(style="rock", feel="tight", intensity=0.8)
        follower.update(AudioAnalysisObservation(0.5, (0.5,), 120.0, 0.9, 0.5, 0.9))

        decision = follower.update(AudioAnalysisObservation(1.0, (1.0,), None, 0.0, 0.3, 0.9))

        self.assertEqual(decision.tempo_bpm, 120.0)
        self.assertEqual(decision.tempo_confidence, 0.0)
        self.assertEqual(decision.effective_intensity, 0.8)
        self.assertTrue(decision.musical_activity_active)

    def test_groove_follower_requires_consistent_evidence_for_octave_tempo_change(self):
        """Exercise the `groove follower requires consistent evidence for octave...

        Returns:
            None: No value is returned.
        """
        follower = GrooveFollower(style="rock", feel="tight", intensity=0.8)
        follower.update(AudioAnalysisObservation(1.0, (1.0,), 120.0, 0.9, 0.5, 0.9))

        first_candidate = follower.update(
            AudioAnalysisObservation(1.5, (1.5,), 60.0, 0.9, 0.5, 0.9)
        )
        unrelated_candidate = follower.update(
            AudioAnalysisObservation(2.0, (2.0,), 120.0, 0.9, 0.5, 0.9)
        )
        restarted_candidate = follower.update(
            AudioAnalysisObservation(2.5, (2.5,), 60.0, 0.9, 0.5, 0.9)
        )

        self.assertEqual(first_candidate.tempo_bpm, 120.0)
        self.assertTrue(first_candidate.holding_stable_tempo)
        self.assertEqual(unrelated_candidate.tempo_bpm, 120.0)
        self.assertEqual(restarted_candidate.tempo_bpm, 120.0)
        self.assertEqual(restarted_candidate.tempo_confidence, 0.9)

        second_candidate = follower.update(
            AudioAnalysisObservation(3.0, (3.0,), 60.0, 0.9, 0.5, 0.9)
        )
        later_candidates = [
            follower.update(
                AudioAnalysisObservation(timestamp, (timestamp,), 60.0, 0.9, 0.5, 0.9)
            )
            for timestamp in (3.5, 4.0, 4.5, 5.0)
        ]
        confirmed_candidate = follower.update(
            AudioAnalysisObservation(5.5, (5.5,), 60.0, 0.9, 0.5, 0.9)
        )

        self.assertEqual(second_candidate.tempo_bpm, 120.0)
        self.assertTrue(all(decision.tempo_bpm == 120.0 for decision in later_candidates))
        self.assertEqual(confirmed_candidate.tempo_bpm, 60.0)
        self.assertFalse(confirmed_candidate.holding_stable_tempo)

        double_time_follower = GrooveFollower(style="rock", feel="tight", intensity=0.8)
        double_time_follower.update(
            AudioAnalysisObservation(1.0, (1.0,), 60.0, 0.9, 0.5, 0.9)
        )
        double_time_candidates = [
            double_time_follower.update(
                AudioAnalysisObservation(timestamp, (timestamp,), 120.0, 0.9, 0.5, 0.9)
            )
            for timestamp in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5)
        ]

        self.assertEqual(
            [decision.tempo_bpm for decision in double_time_candidates],
            [60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 120.0],
        )

    def test_groove_follower_timeout_is_measured_in_bars(self):
        """Exercise the `groove follower timeout is measured in bars` test scenario.

        Returns:
            None: No value is returned.
        """
        for timeout_bars in (0, 1, 2, 4):
            with self.subTest(timeout_bars=timeout_bars):
                follower = GrooveFollower(
                    style="rock",
                    feel="tight",
                    intensity=0.8,
                    onset_timeout_bars=timeout_bars,
                )
                stable = follower.update(AudioAnalysisObservation(0.5, (0.5,), 120.0, 0.9, 0.5, 0.9))
                if timeout_bars == 0:
                    active = stable
                    timeout_time = 0.51
                else:
                    before_timeout = 0.5 + timeout_bars * 2.0 - 0.01
                    active = follower.update(
                        AudioAnalysisObservation(before_timeout, (), None, 0.0, 0.2, 0.9)
                    )
                    timeout_time = 0.5 + timeout_bars * 2.0
                timed_out = follower.update(
                    AudioAnalysisObservation(timeout_time, (), None, 0.0, 0.2, 0.9)
                )

                self.assertTrue(active.musical_activity_active)
                self.assertFalse(timed_out.musical_activity_active)
                self.assertEqual(timed_out.tempo_bpm, 120.0)

    def test_groove_follower_holds_tempo_against_loose_multiples(self):
        """Exercise the `groove follower holds tempo against loose multiples` test...

        Returns:
            None: No value is returned.
        """
        for candidate in (178.0, 176.0, 240.0, 40.0):
            with self.subTest(candidate=candidate):
                follower = GrooveFollower(style="rock", feel="tight", intensity=0.8)
                follower.update(AudioAnalysisObservation(1.0, (1.0,), 80.0, 0.9, 0.5, 0.9))
                decisions = [
                    follower.update(
                        AudioAnalysisObservation(t, (t,), candidate, 0.9, 0.5, 0.9)
                    )
                    for t in (1.5, 2.0, 2.5, 3.0, 3.5)
                ]
                self.assertTrue(all(d.tempo_bpm == 80.0 for d in decisions))

    def test_groove_follower_locks_pulse_octave_while_drums_play(self):
        """Exercise the `groove follower locks pulse octave while drums play` test...

        Returns:
            None: No value is returned.
        """
        follower = GrooveFollower(
            style="rock", feel="tight", intensity=0.8, lock_pulse_octave=True
        )
        follower.update(AudioAnalysisObservation(1.0, (1.0,), 80.0, 0.9, 0.5, 0.9))
        decisions = [
            follower.update(AudioAnalysisObservation(t, (t,), 160.0, 0.9, 0.5, 0.9))
            for t in (2.0, 4.0, 6.0, 8.0, 10.0)
        ]
        for t in (11.0, 14.0, 17.0, 20.0):
            shifted = follower.update(AudioAnalysisObservation(t, (t,), 100.0, 0.9, 0.5, 0.9))

        self.assertTrue(all(d.tempo_bpm == 80.0 for d in decisions))
        self.assertEqual(shifted.tempo_bpm, 100.0)

    def test_groove_follower_holds_first_tempo_against_glitches_and_wander(self):
        """Exercise the `groove follower holds first tempo against glitches and...

        Returns:
            None: No value is returned.
        """
        follower = GrooveFollower(style="rock", feel="tight", intensity=0.8)
        follower.update(AudioAnalysisObservation(1.0, (1.0,), 100.0, 0.9, 0.5, 0.9))
        glitch = follower.update(AudioAnalysisObservation(1.5, (1.5,), 130.0, 0.9, 0.5, 0.9))
        back = follower.update(AudioAnalysisObservation(2.0, (2.0,), 100.0, 0.9, 0.5, 0.9))
        wander = follower.update(AudioAnalysisObservation(2.5, (2.5,), 104.0, 0.9, 0.5, 0.9))

        self.assertEqual(glitch.tempo_bpm, 100.0)
        self.assertEqual(back.tempo_bpm, 100.0)
        self.assertEqual(wander.tempo_bpm, 100.0)

    def test_groove_follower_accepts_sustained_tempo_change_unless_locked(self):
        """Exercise the `groove follower accepts sustained tempo change unless...

        Returns:
            None: No value is returned.
        """
        for lock_tempo, expected in ((False, 130.0), (True, 100.0)):
            with self.subTest(lock_tempo=lock_tempo):
                follower = GrooveFollower(
                    style="rock", feel="tight", intensity=0.8, lock_tempo=lock_tempo
                )
                follower.update(AudioAnalysisObservation(1.0, (1.0,), 100.0, 0.9, 0.5, 0.9))
                for t in (2.0, 4.0, 6.0, 8.0, 10.0, 12.0):
                    decision = follower.update(
                        AudioAnalysisObservation(t, (t,), 130.0, 0.9, 0.5, 0.9)
                    )
                self.assertEqual(decision.tempo_bpm, expected)

    def test_groove_follower_lock_tempo_survives_pause(self):
        """Exercise the `groove follower lock tempo survives pause` test scenario.

        Returns:
            None: No value is returned.
        """
        follower = GrooveFollower(style="rock", feel="tight", intensity=0.8, lock_tempo=True)
        follower.update(AudioAnalysisObservation(1.0, (1.0,), 100.0, 0.9, 0.5, 0.9))
        follower.update(AudioAnalysisObservation(2.0, (), None, 0.0, 0.0, 0.0, signal_active=False))
        resumed = follower.update(AudioAnalysisObservation(20.0, (20.0,), 130.0, 0.9, 0.5, 0.9))

        self.assertEqual(resumed.tempo_bpm, 100.0)

    def test_groove_follower_fades_then_reduces_to_kick_during_pause(self):
        """Exercise the `groove follower fades then reduces to kick during pause`...

        Returns:
            None: No value is returned.
        """
        follower = GrooveFollower(style="rock", feel="tight", intensity=0.8)
        playing = follower.update(AudioAnalysisObservation(1.0, (1.0,), 120.0, 0.9, 0.5, 0.9))
        early = follower.update(AudioAnalysisObservation(1.5, (), None, 0.0, 0.0, 0.0, signal_active=False))
        faded = follower.update(AudioAnalysisObservation(4.0, (), None, 0.0, 0.0, 0.0, signal_active=False))
        reduced = follower.update(AudioAnalysisObservation(14.0, (), None, 0.0, 0.0, 0.0, signal_active=False))
        resumed = follower.update(AudioAnalysisObservation(15.0, (15.0,), 120.0, 0.9, 0.5, 0.9))

        self.assertEqual(early.effective_intensity, playing.effective_intensity)
        self.assertAlmostEqual(faded.effective_intensity, playing.effective_intensity * 0.75)
        self.assertFalse(faded.kick_only)
        self.assertTrue(reduced.kick_only)
        self.assertTrue(set("".join(reduced.pattern)) <= {"K", "-"})
        self.assertFalse(resumed.kick_only)
        self.assertEqual(resumed.effective_intensity, playing.effective_intensity)

    def test_groove_follower_holds_tempo_after_no_onset_timeout(self):
        """Exercise the `groove follower holds tempo after no onset timeout` test...

        Returns:
            None: No value is returned.
        """
        follower = GrooveFollower(
            style="rock",
            feel="tight",
            intensity=0.8,
            onset_timeout_bars=1,
        )
        established = follower.update(
            AudioAnalysisObservation(0.5, (0.5,), 120.0, 0.9, 0.5, 0.9)
        )
        active = follower.update(
            AudioAnalysisObservation(2.49, (), 120.0, 0.9, 0.5, 0.9)
        )
        timed_out = follower.update(
            AudioAnalysisObservation(2.5, (), 150.0, 0.9, 0.5, 0.9)
        )

        self.assertEqual(established.tempo_bpm, 120.0)
        self.assertTrue(active.musical_activity_active)
        self.assertEqual(active.tempo_bpm, 120.0)
        self.assertFalse(timed_out.musical_activity_active)
        self.assertEqual(timed_out.tempo_bpm, 120.0)
        self.assertEqual(timed_out.pattern, active.pattern)

    def test_cli_lists_input_devices_without_opening_capture(self):
        """Exercise the `cli lists input devices without opening capture` test scenario.

        Returns:
            None: No value is returned.
        """
        from drum_companion.app import run_cli

        output = StringIO()
        with patch(
            "drum_companion.app.list_input_devices",
            return_value=[InputDevice(0, "Built-in mic", 1, 48000)],
        ), redirect_stdout(output):
            result = run_cli(["--list-inputs"])

        self.assertEqual(result, 0)
        self.assertIn("Built-in mic", output.getvalue())

    def test_cli_lists_output_devices_without_opening_stream(self):
        """Exercise the `cli lists output devices without opening stream` test scenario.

        Returns:
            None: No value is returned.
        """
        from drum_companion.app import run_cli

        output = StringIO()
        with patch(
            "drum_companion.app.list_output_devices",
            return_value=[OutputDevice(3, "Studio headphones", 2, 48000)],
        ), redirect_stdout(output):
            result = run_cli(["--list-outputs"])

        self.assertEqual(result, 0)
        self.assertIn("Studio headphones", output.getvalue())

    def test_cli_passes_selected_output_to_live_playback(self):
        """Exercise the `cli passes selected output to live playback` test scenario.

        Returns:
            None: No value is returned.
        """
        from drum_companion.app import run_cli

        with patch("drum_companion.app.run_live", return_value=0) as run_live:
            result = run_cli(["--live", "--play-drums", "--output-device", "3", "--style", "folk"])

        self.assertEqual(result, 0)
        run_live.assert_called_once_with(None, "folk", "tight", 0.8, "verse", True, 3, 0.75, 1, 40, 140)

    def test_cli_passes_onset_timeout_to_web_settings(self):
        """Exercise the `cli passes onset timeout to web settings` test scenario.

        Returns:
            None: No value is returned.
        """
        from drum_companion.app import parse_args, run_cli

        self.assertEqual(parse_args(["--web"]).onset_timeout_bars, 1)
        with patch("drum_companion.app.run_web", return_value=0) as run_web:
            result = run_cli(["--web", "--onset-timeout-bars", "4"])

        self.assertEqual(result, 0)
        self.assertEqual(run_web.call_args.args[0].onset_timeout_bars, 4)

        with self.assertRaises(SystemExit):
            parse_args(["--web", "--onset-timeout-bars", "3"])

    def test_live_playback_keys_control_mute_level_and_stop(self):
        """Exercise the `live playback keys control mute level and stop` test scenario.

        Returns:
            None: No value is returned.
        """
        from drum_companion.app import apply_playback_key

        class FakeOutput:
            """Provide a controllable audio output substitute for tests."""
            is_muted = False
            master_level = 0.5

            def set_muted(self, value):
                """Set muted.

                Args:
                    value (object): Value to validate or use.

                Returns:
                    None: No value is returned.
                """
                self.is_muted = value

            def set_master_level(self, value):
                """Set master level.

                Args:
                    value (object): Value to validate or use.

                Returns:
                    None: No value is returned.
                """
                self.master_level = value

        output = FakeOutput()
        self.assertFalse(apply_playback_key("m", output))
        self.assertTrue(output.is_muted)
        self.assertFalse(apply_playback_key("+", output))
        self.assertAlmostEqual(output.master_level, 0.6)
        self.assertFalse(apply_playback_key("-", output))
        self.assertAlmostEqual(output.master_level, 0.5)
        self.assertTrue(apply_playback_key("q", output))

    def test_output_device_failure_falls_back_to_live_analysis(self):
        """Exercise the `output device failure falls back to live analysis` test...

        Returns:
            None: No value is returned.
        """
        from drum_companion.app import run_live

        class FailingOutput:
            """Simulate an audio output that fails during startup."""
            def __init__(self, device=None):
                """Initialize the instance.

                Args:
                    device (object): Audio device index or selected device.

                Returns:
                    None: No value is returned.
                """
                pass

            def set_master_level(self, level):
                """Set master level.

                Args:
                    level (object): Output level to apply.

                Returns:
                    None: No value is returned.
                """
                pass

            def start(self):
                """Start the associated resource or event.

                Returns:
                    None: No value is returned.
                """
                raise OutputError("output device busy")

            def stop(self):
                """Stop the associated resource or event.

                Returns:
                    None: No value is returned.
                """
                pass

        class InterruptingCapture:
            """Simulate an audio capture source that raises an interrupt."""
            started = False
            stopped = False

            def __init__(self, device=None):
                """Initialize the instance.

                Args:
                    device (object): Audio device index or selected device.

                Returns:
                    None: No value is returned.
                """
                pass

            def start(self):
                """Start the associated resource or event.

                Returns:
                    None: No value is returned.
                """
                self.started = True

            def read(self, timeout=None):
                """Read the associated resource or event.

                Args:
                    timeout (object): Maximum time to wait, in seconds.

                Returns:
                    None: No value is returned.
                """
                raise KeyboardInterrupt

            def stop(self):
                """Stop the associated resource or event.

                Returns:
                    None: No value is returned.
                """
                self.stopped = True

        capture = InterruptingCapture()
        errors = StringIO()
        output_text = StringIO()
        with (
            patch("drum_companion.app.MicrophoneCapture", return_value=capture),
            patch("drum_companion.app.SampleOutput", side_effect=FailingOutput),
            redirect_stderr(errors),
            redirect_stdout(output_text),
        ):
            result = run_live(play_drums=True)

        self.assertEqual(result, 0)
        self.assertTrue(capture.started)
        self.assertTrue(capture.stopped)
        self.assertIn("output device busy", errors.getvalue())
        self.assertIn("Live audio analysis started", output_text.getvalue())

    def test_cli_live_mode_stops_capture_on_interrupt(self):
        """Exercise the `cli live mode stops capture on interrupt` test scenario.

        Returns:
            None: No value is returned.
        """
        from drum_companion.app import run_cli

        class InterruptingCapture:
            """Simulate an audio capture source that raises an interrupt."""
            stopped = False

            def __init__(self, device=None):
                """Initialize the instance.

                Args:
                    device (object): Audio device index or selected device.

                Returns:
                    None: No value is returned.
                """
                self.device = device

            def start(self):
                """Start the associated resource or event.

                Returns:
                    None: No value is returned.
                """
                pass

            def read(self, timeout=None):
                """Read the associated resource or event.

                Args:
                    timeout (object): Maximum time to wait, in seconds.

                Returns:
                    None: No value is returned.
                """
                raise KeyboardInterrupt

            def stop(self):
                """Stop the associated resource or event.

                Returns:
                    None: No value is returned.
                """
                self.stopped = True

        capture = InterruptingCapture()
        output = StringIO()
        with patch("drum_companion.app.MicrophoneCapture", return_value=capture), redirect_stdout(output):
            result = run_cli(["--live", "--device", "2"])

        self.assertEqual(result, 0)
        self.assertTrue(capture.stopped)
        self.assertIn("stopped", output.getvalue())

    def test_cli_reports_live_capture_start_errors(self):
        """Exercise the `cli reports live capture start errors` test scenario.

        Returns:
            None: No value is returned.
        """
        from drum_companion.app import run_cli

        class FailingCapture:
            """Simulate an audio capture source that fails during startup."""
            def __init__(self, device=None):
                """Initialize the instance.

                Args:
                    device (object): Audio device index or selected device.

                Returns:
                    None: No value is returned.
                """
                self.device = device

            def start(self):
                """Start the associated resource or event.

                Returns:
                    None: No value is returned.
                """
                raise CaptureError("permission denied")

            def stop(self):
                """Stop the associated resource or event.

                Returns:
                    None: No value is returned.
                """
                pass

        errors = StringIO()
        with patch("drum_companion.app.MicrophoneCapture", return_value=FailingCapture()), redirect_stderr(errors):
            result = run_cli(["--live", "--device", "1"])

        self.assertEqual(result, 1)
        self.assertIn("permission denied", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
