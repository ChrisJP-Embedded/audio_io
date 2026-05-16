"""Configuration types for audio I/O sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SampleDType = Literal["float32", "int16", "int32"]


@dataclass(frozen=True)
class AudioIOConfig:
    """Configuration for an audio input/output stream.

    `block_words` is the number of sample frames per callback block. Each frame
    contains one word per selected channel.

    Channel indices are zero-based logical device channels. For example,
    `output_channels=(0, 2)` asks the backend to write only hardware output
    channels 1 and 3 while presenting a compact two-column block to callers.
    """

    device: str | int | None = None
    input_channels: tuple[int, ...] = ()
    output_channels: tuple[int, ...] = ()
    sample_rate: int = 48_000
    block_words: int = 256
    dtype: SampleDType = "float32"
    input_queue_blocks: int = 8
    output_queue_blocks: int = 8

    def __post_init__(self) -> None:
        if self.block_words <= 0:
            raise ValueError("block_words must be greater than zero")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero")
        if self.input_queue_blocks <= 0:
            raise ValueError("input_queue_blocks must be greater than zero")
        if self.output_queue_blocks <= 0:
            raise ValueError("output_queue_blocks must be greater than zero")
        if len(set(self.input_channels)) != len(self.input_channels):
            raise ValueError("input_channels cannot contain duplicates")
        if len(set(self.output_channels)) != len(self.output_channels):
            raise ValueError("output_channels cannot contain duplicates")
        if any(channel < 0 for channel in self.input_channels + self.output_channels):
            raise ValueError("channel indices must be zero or greater")

    @property
    def input_channel_count(self) -> int:
        return len(self.input_channels)

    @property
    def output_channel_count(self) -> int:
        return len(self.output_channels)
