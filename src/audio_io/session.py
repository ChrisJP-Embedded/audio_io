"""High-level audio I/O session API."""

from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Full, Queue
from typing import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from audio_io.backends import AudioBackend, SoundDeviceBackend, StreamHandle
from audio_io.config import AudioIOConfig

AudioArray = NDArray[np.float32]


@dataclass(frozen=True)
class BlockInfo:
    frame_count: int
    time: object | None = None
    status: object | None = None


InputCallback = Callable[[AudioArray, BlockInfo], None]
OutputCallback = Callable[[int, BlockInfo], ArrayLike | None]


class AudioIOSession:
    """Manage a block-based audio I/O stream.

    If `input_callback` is omitted, captured blocks are placed into an input
    queue and can be read with `read_input_block`.
    If `output_callback` is omitted, playback blocks are read from an output
    queue populated with `write_output_block`; missing data is rendered silent.
    """

    def __init__(
        self,
        config: AudioIOConfig,
        *,
        input_callback: InputCallback | None = None,
        output_callback: OutputCallback | None = None,
        backend: AudioBackend | None = None,
    ) -> None:
        self.config = config
        self._input_callback = input_callback
        self._output_callback = output_callback
        self._backend = backend or SoundDeviceBackend()
        self._input_queue: Queue[AudioArray] = Queue(maxsize=config.input_queue_blocks)
        self._output_queue: Queue[AudioArray] = Queue(maxsize=config.output_queue_blocks)
        self._stream: StreamHandle | None = None
        self._last_status: object | None = None

    def start(self) -> "AudioIOSession":
        if self._stream is not None:
            return self
        self._stream = self._backend.open_stream(self.config, self._stream_callback)
        self._stream.start()
        return self

    def stop(self) -> None:
        if self._stream is None:
            return
        self._stream.stop()
        self._stream.close()
        self._stream = None

    def __enter__(self) -> "AudioIOSession":
        return self.start()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.stop()

    @property
    def is_active(self) -> bool:
        return bool(self._stream and self._stream.active)

    @property
    def last_status(self) -> object | None:
        return self._last_status

    def read_input_block(self, timeout: float | None = None) -> AudioArray:
        return self._input_queue.get(timeout=timeout)

    def try_read_input_block(self) -> AudioArray | None:
        try:
            return self._input_queue.get_nowait()
        except Empty:
            return None

    def write_output_block(self, block: ArrayLike, timeout: float | None = None) -> None:
        output = self._coerce_output_block(block)
        self._output_queue.put(output, timeout=timeout)

    def try_write_output_block(self, block: ArrayLike) -> bool:
        output = self._coerce_output_block(block)
        try:
            self._output_queue.put_nowait(output)
        except Full:
            return False
        return True

    def _stream_callback(
        self,
        indata: AudioArray | None,
        outdata: AudioArray | None,
        frames: int,
        time: object,
        status: object,
    ) -> None:
        info = BlockInfo(frame_count=frames, time=time, status=status)
        self._last_status = status

        if indata is not None and self.config.input_channel_count:
            input_block = np.array(indata, copy=True)
            if self._input_callback:
                self._input_callback(input_block, info)
            else:
                self._drop_oldest_and_put(self._input_queue, input_block)

        if outdata is not None and self.config.output_channel_count:
            outdata[:] = self._next_output_block(frames, info)

    def _next_output_block(self, frames: int, info: BlockInfo) -> AudioArray:
        if self._output_callback:
            block = self._output_callback(frames, info)
            if block is None:
                return self._silence(frames)
            return self._coerce_output_block(block, frames=frames)

        try:
            return self._output_queue.get_nowait()
        except Empty:
            return self._silence(frames)

    def _coerce_output_block(self, block: ArrayLike, frames: int | None = None) -> AudioArray:
        expected_frames = frames or self.config.block_words
        expected_shape = (expected_frames, self.config.output_channel_count)
        output = np.asarray(block, dtype=self.config.dtype)
        if output.shape != expected_shape:
            raise ValueError(f"output block must have shape {expected_shape}, got {output.shape}")
        return output

    def _silence(self, frames: int) -> AudioArray:
        return np.zeros((frames, self.config.output_channel_count), dtype=self.config.dtype)

    @staticmethod
    def _drop_oldest_and_put(queue: Queue[AudioArray], block: AudioArray) -> None:
        try:
            queue.put_nowait(block)
            return
        except Full:
            pass
        try:
            queue.get_nowait()
        except Empty:
            pass
        queue.put_nowait(block)
