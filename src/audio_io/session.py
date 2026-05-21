"""High-level audio I/O session API."""

from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Full, Queue
import threading
import time
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
        self._last_error: Exception | None = None
        self._lock = threading.RLock()
        self._restart_lock = threading.Lock()
        self._restart_thread: threading.Thread | None = None
        self._restart_attempt_count = 0
        self._stop_requested = False

    def start(self) -> "AudioIOSession":
        """Open and start the backend stream, returning this session for chaining."""

        with self._lock:
            if self._stream is not None:
                return self
            self._stop_requested = False
            self._restart_attempt_count = 0
            self._open_and_start_locked()
        return self

    def stop(self) -> None:
        """Stop and close the stream if it is currently open."""

        with self._lock:
            self._stop_requested = True
            stream = self._stream
            self._stream = None
        self._close_stream(stream)

    def __enter__(self) -> "AudioIOSession":
        return self.start()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.stop()

    @property
    def is_active(self) -> bool:
        with self._lock:
            return bool(self._stream and self._stream.active)

    @property
    def last_status(self) -> object | None:
        return self._last_status

    @property
    def last_error(self) -> Exception | None:
        return self._last_error

    @property
    def restart_attempt_count(self) -> int:
        return self._restart_attempt_count

    def read_input_block(self, timeout: float | None = None) -> AudioArray:
        """Read the next queued input block, blocking until one is available."""

        return self._input_queue.get(timeout=timeout)

    def try_read_input_block(self) -> AudioArray | None:
        """Read one input block without blocking, or return None when empty."""

        try:
            return self._input_queue.get_nowait()
        except Empty:
            return None

    def write_output_block(self, block: ArrayLike, timeout: float | None = None) -> None:
        """Queue one output block for the backend callback to render."""

        output = self._coerce_output_block(block)
        self._output_queue.put(output, timeout=timeout)

    def try_write_output_block(self, block: ArrayLike) -> bool:
        """Queue one output block without blocking, returning False when full."""

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
        """Bridge the backend callback into the public callback/queue API."""

        info = BlockInfo(frame_count=frames, time=time, status=status)
        self._last_status = status

        if indata is not None and self.config.input_channel_count:
            input_block = np.array(indata, copy=True)
            try:
                if self._input_callback:
                    self._input_callback(input_block, info)
                else:
                    self._drop_oldest_and_put(self._input_queue, input_block)
            except Exception as exc:
                self._handle_callback_error(exc)

        if outdata is not None and self.config.output_channel_count:
            try:
                outdata[:] = self._next_output_block(frames, info)
            except Exception as exc:
                self._handle_callback_error(exc)
                outdata[:] = self._silence(frames)

    def _next_output_block(self, frames: int, info: BlockInfo) -> AudioArray:
        """Return one output block, falling back to silence on callback/queue gaps."""

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

    def _open_and_start_locked(self) -> None:
        self._stream = self._backend.open_stream(self.config, self._stream_callback)
        self._stream.start()

    @staticmethod
    def _close_stream(stream: StreamHandle | None) -> None:
        if stream is None:
            return
        stream.stop()
        stream.close()

    def _handle_callback_error(self, exc: Exception) -> None:
        self._last_error = exc
        self._schedule_restart()

    def _schedule_restart(self) -> None:
        if self.config.callback_restart_attempts == 0:
            return
        with self._restart_lock:
            if self._stop_requested:
                return
            if self._restart_thread is not None and self._restart_thread.is_alive():
                return
            if self._restart_attempt_count >= self.config.callback_restart_attempts:
                return
            self._restart_attempt_count += 1
            self._restart_thread = threading.Thread(target=self._restart_worker, daemon=True)
            self._restart_thread.start()

    def _restart_worker(self) -> None:
        while True:
            time.sleep(self.config.callback_restart_delay_seconds)
            try:
                with self._lock:
                    if self._stop_requested or self._stream is None:
                        return
                    stream = self._stream
                    self._stream = None
                try:
                    self._close_stream(stream)
                except Exception as exc:
                    self._last_error = exc
                with self._lock:
                    if self._stop_requested:
                        return
                    self._open_and_start_locked()
                return
            except Exception as exc:
                self._last_error = exc
                with self._restart_lock:
                    if self._stop_requested:
                        return
                    if self._restart_attempt_count >= self.config.callback_restart_attempts:
                        return
                    self._restart_attempt_count += 1

    @staticmethod
    def _drop_oldest_and_put(queue: Queue[AudioArray], block: AudioArray) -> None:
        # Audio callbacks should not block waiting for slow consumers. Keeping
        # the newest block makes level meters and UI displays stay current.
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
