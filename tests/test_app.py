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
    def test_estimate_performance_context(self):
        context = estimate_performance_context(96.0, 0.8, 0.9, phrase="chorus")
        self.assertAlmostEqual(context.tempo_bpm, 96.0)
        self.assertEqual(context.phrase, "chorus")
        self.assertGreaterEqual(context.confidence, 0.0)
        self.assertLessEqual(context.confidence, 1.0)

    def test_build_pattern(self):
        pattern = build_pattern("rock", "tight", 0.8, bars=1)
        self.assertEqual(len(pattern), 8)
        self.assertTrue(all(isinstance(cell, str) and len(cell) == 3 for cell in pattern))

    def test_generate_accompaniment_respects_phrase_and_feel(self):
        accompaniment = generate_accompaniment("chorus", "rock", "relaxed", 0.9)
        self.assertIn("A", accompaniment[0])
        self.assertLess(len(accompaniment), 17)

    def test_dashboard_renders_status(self):
        dashboard = GrooveDashboard(tempo=96.0, phrase="chorus", style="rock", feel="tight", intensity=0.8)
        screen = dashboard.render()
        self.assertIn("96.0 BPM", screen)
        self.assertIn("chorus", screen.lower())
        self.assertIn("rock", screen.lower())

    def test_interaction_preset_parses_user_input(self):
        preset = InteractionPreset.from_input("chorus", "rock", "tight", "0.8")
        self.assertEqual(preset.phrase, "chorus")
        self.assertEqual(preset.style, "rock")
        self.assertEqual(preset.feel, "tight")
        self.assertAlmostEqual(preset.intensity, 0.8)

    def test_audio_observation_models_combined_input_and_independent_confidence(self):
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
        self.assertEqual(uncertain.effective_intensity, 0.0)
        self.assertLess(sum("K" in step or "S" in step for step in uncertain.pattern),
                        sum("K" in step or "S" in step for step in stable.pattern))

    def test_cli_lists_input_devices_without_opening_capture(self):
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
        from drum_companion.app import run_cli

        with patch("drum_companion.app.run_live", return_value=0) as run_live:
            result = run_cli(["--live", "--play-drums", "--output-device", "3", "--style", "folk"])

        self.assertEqual(result, 0)
        run_live.assert_called_once_with(None, "folk", "tight", 0.8, "verse", True, 3, 0.75)

    def test_live_playback_keys_control_mute_level_and_stop(self):
        from drum_companion.app import apply_playback_key

        class FakeOutput:
            is_muted = False
            master_level = 0.5

            def set_muted(self, value):
                self.is_muted = value

            def set_master_level(self, value):
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
        from drum_companion.app import run_live

        class FailingOutput:
            def __init__(self, device=None):
                pass

            def set_master_level(self, level):
                pass

            def start(self):
                raise OutputError("output device busy")

            def stop(self):
                pass

        class InterruptingCapture:
            started = False
            stopped = False

            def __init__(self, device=None):
                pass

            def start(self):
                self.started = True

            def read(self, timeout=None):
                raise KeyboardInterrupt

            def stop(self):
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
        from drum_companion.app import run_cli

        class InterruptingCapture:
            stopped = False

            def __init__(self, device=None):
                self.device = device

            def start(self):
                pass

            def read(self, timeout=None):
                raise KeyboardInterrupt

            def stop(self):
                self.stopped = True

        capture = InterruptingCapture()
        output = StringIO()
        with patch("drum_companion.app.MicrophoneCapture", return_value=capture), redirect_stdout(output):
            result = run_cli(["--live", "--device", "2"])

        self.assertEqual(result, 0)
        self.assertTrue(capture.stopped)
        self.assertIn("stopped", output.getvalue())

    def test_cli_reports_live_capture_start_errors(self):
        from drum_companion.app import run_cli

        class FailingCapture:
            def __init__(self, device=None):
                self.device = device

            def start(self):
                raise CaptureError("permission denied")

            def stop(self):
                pass

        errors = StringIO()
        with patch("drum_companion.app.MicrophoneCapture", return_value=FailingCapture()), redirect_stderr(errors):
            result = run_cli(["--live", "--device", "1"])

        self.assertEqual(result, 1)
        self.assertIn("permission denied", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
