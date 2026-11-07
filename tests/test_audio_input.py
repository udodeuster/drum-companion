"""Tests for microphone discovery, capture, and queue behavior."""

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from drum_companion.audio.input import CaptureError, MicrophoneCapture, list_input_devices


DEVICES = [
    {"name": "Built-in mic", "max_input_channels": 1, "default_samplerate": 48000},
    {"name": "Speakers", "max_input_channels": 0, "default_samplerate": 48000},
]


class FakeStream:
    """Provide a controllable audio stream substitute for capture tests."""
    def __init__(self, callback, fail_start=False, **kwargs):
        """Initialize the instance.

        Args:
            callback (object): Callback invoked when the corresponding audio
                event occurs.
            fail_start (object): Whether the test stream should simulate a start
                failure.
            kwargs (object): Additional keyword arguments forwarded to the operation.

        Returns:
            None: No value is returned.
        """
        self.callback = callback
        self.fail_start = fail_start
        self.kwargs = kwargs
        self.stopped = False
        self.closed = False

    def start(self):
        """Start the associated resource or event.

        Returns:
            None: No value is returned.
        """
        if self.fail_start:
            raise RuntimeError("device busy")
        for index in range(3):
            self.callback(
                np.full((4, 1), index, dtype=np.float32),
                4,
                type("TimeInfo", (), {"inputBufferAdcTime": float(index)})(),
                None,
            )

    def stop(self):
        """Stop the associated resource or event.

        Returns:
            None: No value is returned.
        """
        self.stopped = True

    def close(self):
        """Close the associated resource or event.

        Returns:
            None: No value is returned.
        """
        self.closed = True


class TestMicrophoneCapture(unittest.TestCase):
    """Test microphone capture behavior."""
    def test_lists_only_input_devices(self):
        """Exercise the `lists only input devices` test scenario.

        Returns:
            None: No value is returned.
        """
        devices = list_input_devices(device_query=lambda: DEVICES)

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].index, 0)
        self.assertEqual(devices[0].name, "Built-in mic")

    def test_selects_device_and_stops_stream(self):
        """Exercise the `selects device and stops stream` test scenario.

        Returns:
            None: No value is returned.
        """
        streams = []

        def stream_factory(**kwargs):
            """Handle stream factory.

            Args:
                kwargs (object): Additional keyword arguments forwarded to the
                    operation.

            Returns:
                object: The result produced by this operation.
            """
            stream = FakeStream(**kwargs)
            streams.append(stream)
            return stream

        capture = MicrophoneCapture(
            device=0,
            device_query=lambda: DEVICES,
            stream_factory=stream_factory,
            block_size=4,
        )
        capture.start()
        block = capture.read(timeout=0.01)
        capture.stop()

        self.assertEqual(streams[0].kwargs["device"], 0)
        self.assertEqual(block.data.shape, (4,))
        self.assertTrue(streams[0].stopped)
        self.assertTrue(streams[0].closed)

    def test_reports_missing_device_and_start_failure(self):
        """Exercise the `reports missing device and start failure` test scenario.

        Returns:
            None: No value is returned.
        """
        capture = MicrophoneCapture(device=3, device_query=lambda: DEVICES)
        with self.assertRaisesRegex(CaptureError, "not available"):
            capture.start()

        failing = MicrophoneCapture(
            device=0,
            device_query=lambda: DEVICES,
            stream_factory=lambda **kwargs: FakeStream(fail_start=True, **kwargs),
        )
        with self.assertRaisesRegex(CaptureError, "device busy"):
            failing.start()

    def test_queue_overflow_marks_newest_block_discontinuous(self):
        """Exercise the `queue overflow marks newest block discontinuous` test scenario.

        Returns:
            None: No value is returned.
        """
        capture = MicrophoneCapture(
            device=0,
            device_query=lambda: DEVICES,
            stream_factory=FakeStream,
            block_size=4,
            max_queue_blocks=1,
        )
        capture.start()
        block = capture.read(timeout=0.01)

        self.assertGreater(capture.dropped_blocks, 0)
        self.assertTrue(block.discontinuity)
        capture.stop()

    def test_capture_session_does_not_create_recording_files(self):
        """Exercise the `capture session does not create recording files` test scenario.

        Returns:
            None: No value is returned.
        """
        original_directory = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                capture = MicrophoneCapture(
                    device=0,
                    device_query=lambda: DEVICES,
                    stream_factory=FakeStream,
                    block_size=4,
                )
                capture.start()
                capture.read(timeout=0.01)
                capture.stop()
                self.assertEqual(list(Path(directory).iterdir()), [])
            finally:
                os.chdir(original_directory)


if __name__ == "__main__":
    unittest.main()