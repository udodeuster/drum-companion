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
    def __init__(self, callback, fail_start=False, **kwargs):
        self.callback = callback
        self.fail_start = fail_start
        self.kwargs = kwargs
        self.stopped = False
        self.closed = False

    def start(self):
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
        self.stopped = True

    def close(self):
        self.closed = True


class TestMicrophoneCapture(unittest.TestCase):
    def test_lists_only_input_devices(self):
        devices = list_input_devices(device_query=lambda: DEVICES)

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].index, 0)
        self.assertEqual(devices[0].name, "Built-in mic")

    def test_selects_device_and_stops_stream(self):
        streams = []

        def stream_factory(**kwargs):
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