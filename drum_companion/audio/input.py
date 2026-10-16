from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Full, Queue
from typing import Callable

import numpy as np
import sounddevice as sd


class CaptureError(RuntimeError):
    """Raised when a microphone cannot be selected or started."""


@dataclass(frozen=True)
class InputDevice:
    index: int
    name: str
    channels: int
    sample_rate: int


@dataclass(frozen=True)
class AudioBlock:
    data: np.ndarray
    sample_rate: int
    timestamp_seconds: float
    discontinuity: bool = False


def list_input_devices(device_query: Callable[[], object] = sd.query_devices) -> list[InputDevice]:
    devices = device_query()
    return [
        InputDevice(
            index=index,
            name=str(device["name"]),
            channels=int(device["max_input_channels"]),
            sample_rate=int(device["default_samplerate"]),
        )
        for index, device in enumerate(devices)
        if int(device["max_input_channels"]) > 0
    ]


class MicrophoneCapture:
    def __init__(
        self,
        device: int | None = None,
        *,
        device_query: Callable[[], object] = sd.query_devices,
        stream_factory: Callable[..., object] = sd.InputStream,
        sample_rate: int | None = None,
        block_size: int = 1024,
        max_queue_blocks: int = 8,
    ) -> None:
        if block_size <= 0 or max_queue_blocks <= 0:
            raise ValueError("block_size and max_queue_blocks must be positive")
        self.device = device
        self._device_query = device_query
        self._stream_factory = stream_factory
        self._requested_sample_rate = sample_rate
        self._block_size = block_size
        self._blocks: Queue[AudioBlock] = Queue(maxsize=max_queue_blocks)
        self._stream: object | None = None
        self._sample_rate = 0
        self.dropped_blocks = 0

    def start(self) -> None:
        devices = list_input_devices(self._device_query)
        if not devices:
            raise CaptureError("No microphone input devices are available")

        selected = next((item for item in devices if item.index == self.device), None)
        if self.device is not None and selected is None:
            raise CaptureError(f"Input device {self.device} is not available")
        if selected is None:
            selected = devices[0]

        self._sample_rate = self._requested_sample_rate or selected.sample_rate
        self._clear_blocks()

        def callback(indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
            samples = np.asarray(indata[:, 0], dtype=np.float32).copy()
            timestamp = float(getattr(time_info, "inputBufferAdcTime", 0.0))
            discontinuity = bool(status) or len(samples) != frames
            block = AudioBlock(samples, self._sample_rate, timestamp, discontinuity)
            try:
                self._blocks.put_nowait(block)
            except Full:
                self.dropped_blocks += 1
                try:
                    self._blocks.get_nowait()
                except Empty:
                    pass
                try:
                    self._blocks.put_nowait(
                        AudioBlock(samples, self._sample_rate, timestamp, True)
                    )
                except Full:
                    self.dropped_blocks += 1

        try:
            self._stream = self._stream_factory(
                device=selected.index,
                channels=1,
                samplerate=self._sample_rate,
                blocksize=self._block_size,
                dtype="float32",
                callback=callback,
            )
            self._stream.start()
        except Exception as exc:
            self._close_stream()
            raise CaptureError(f"Unable to start microphone input: {exc}") from exc

    def read(self, timeout: float | None = None) -> AudioBlock:
        if self._stream is None:
            raise CaptureError("Microphone capture has not been started")
        return self._blocks.get(timeout=timeout)

    def stop(self) -> None:
        self._close_stream()
        self._clear_blocks()

    def _close_stream(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()

    def _clear_blocks(self) -> None:
        while True:
            try:
                self._blocks.get_nowait()
            except Empty:
                return