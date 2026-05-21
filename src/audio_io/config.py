"""Configuration types for audio I/O sessions."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from typing import Literal

SampleDType = Literal["float32", "int16", "int32"]
VALID_SAMPLE_DTYPES = ("float32", "int16", "int32")


@dataclass(frozen=True)
class AudioTimingStatus:
    """Derived timing and callback-load information for an audio config."""

    sample_rate: int
    block_words: int
    sample_period_seconds: float
    block_duration_seconds: float
    callbacks_per_second: float
    status: str
    message: str

    @property
    def sample_period_microseconds(self) -> float:
        return self.sample_period_seconds * 1_000_000.0

    @property
    def block_duration_milliseconds(self) -> float:
        return self.block_duration_seconds * 1_000.0

    def console_line(self) -> str:
        return (
            f"Audio timing: fs={self.sample_rate:g} Hz, "
            f"1/fs={self.sample_period_microseconds:.3f} us, "
            f"block={self.block_words} frames ({self.block_duration_milliseconds:.3f} ms), "
            f"callbacks={self.callbacks_per_second:.1f}/s, "
            f"status={self.status} - {self.message}"
        )


@dataclass(frozen=True)
class AudioIOConfig:
    """Configuration for an audio input/output stream.

    `block_words` is the number of sample frames per callback block. Each frame
    contains one word per selected channel.

    Channel indices are zero-based logical interface channels. For example,
    `output_channels=(0, 2)` asks the backend to write only hardware output
    channels 1 and 3 while presenting a compact two-column block to callers.

    Callback exceptions are contained by `AudioIOSession`. By default the
    session schedules up to three delayed stream restarts after such errors.
    """

    interface: str | int | None = None
    input_channels: Sequence[int] = ()
    output_channels: Sequence[int] = ()
    sample_rate: int = 48_000
    block_words: int = 256
    dtype: SampleDType = "float32"
    input_queue_blocks: int = 8
    output_queue_blocks: int = 8
    callback_restart_attempts: int = 3
    callback_restart_delay_seconds: float = 0.5
    device: str | int | None = None

    def __post_init__(self) -> None:
        # `device` is kept as a compatibility alias while `interface` is the
        # preferred name used by the rest of the package.
        if self.interface is not None and self.device is not None and self.interface != self.device:
            raise ValueError("interface and device cannot name different audio interfaces")
        if self.interface is None and self.device is not None:
            object.__setattr__(self, "interface", self.device)

        # Store channel selections immutably so sessions can safely reuse the
        # same config object across callbacks and backend validation.
        object.__setattr__(self, "input_channels", tuple(self.input_channels))
        object.__setattr__(self, "output_channels", tuple(self.output_channels))

        if self.block_words <= 0:
            raise ValueError("block_words must be greater than zero")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero")
        if self.input_queue_blocks <= 0:
            raise ValueError("input_queue_blocks must be greater than zero")
        if self.output_queue_blocks <= 0:
            raise ValueError("output_queue_blocks must be greater than zero")
        if self.dtype not in VALID_SAMPLE_DTYPES:
            raise ValueError(f"dtype must be one of {VALID_SAMPLE_DTYPES!r}")
        if self.callback_restart_attempts < 0:
            raise ValueError("callback_restart_attempts must be zero or greater")
        if self.callback_restart_delay_seconds < 0:
            raise ValueError("callback_restart_delay_seconds must be zero or greater")
        if len(set(self.input_channels)) != len(self.input_channels):
            raise ValueError("input_channels cannot contain duplicates")
        if len(set(self.output_channels)) != len(self.output_channels):
            raise ValueError("output_channels cannot contain duplicates")
        if any(channel < 0 for channel in self.input_channels + self.output_channels):
            raise ValueError("channel indices must be zero or greater")
        if not self.input_channels and not self.output_channels:
            raise ValueError("at least one input or output channel must be configured")

    @property
    def input_channel_count(self) -> int:
        return len(self.input_channels)

    @property
    def output_channel_count(self) -> int:
        return len(self.output_channels)

    @property
    def timing_status(self) -> AudioTimingStatus:
        callbacks_per_second = self.sample_rate / self.block_words
        status, message = _callback_rate_status(callbacks_per_second)
        return AudioTimingStatus(
            sample_rate=self.sample_rate,
            block_words=self.block_words,
            sample_period_seconds=1.0 / self.sample_rate,
            block_duration_seconds=self.block_words / self.sample_rate,
            callbacks_per_second=callbacks_per_second,
            status=status,
            message=message,
        )


def _callback_rate_status(callbacks_per_second: float) -> tuple[str, str]:
    if callbacks_per_second <= 250.0:
        return "good", "comfortable callback rate"
    if callbacks_per_second <= 500.0:
        return "caution", "keep callbacks lightweight"
    if callbacks_per_second <= 1000.0:
        return "warning", "higher glitch risk; consider a larger block"
    return "high-risk", "very high Python callback rate; use a larger block"
