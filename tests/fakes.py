from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from audio_io.backends import DeviceInfo, resolve_interface, validate_channel_request
from audio_io.config import AudioIOConfig


@dataclass
class FakeStream:
    callback: Callable
    config: AudioIOConfig
    active: bool = False
    closed: bool = False

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False

    def close(self) -> None:
        self.closed = True

    def process(self, indata=None):
        outdata = np.empty((self.config.block_words, self.config.output_channel_count), dtype=self.config.dtype)
        if self.config.output_channel_count == 0:
            outdata = None
        self.callback(indata, outdata, self.config.block_words, None, None)
        return outdata


class FakeBackend:
    def __init__(self) -> None:
        self.stream: FakeStream | None = None

    def open_stream(self, config: AudioIOConfig, callback: Callable) -> FakeStream:
        interface = resolve_interface(self.list_devices(), config.interface)
        validate_channel_request(config, interface)
        self.stream = FakeStream(callback=callback, config=config)
        return self.stream

    def list_devices(self) -> list[DeviceInfo]:
        return [
            DeviceInfo(
                name="Fake Device",
                index=0,
                max_input_channels=2,
                max_output_channels=2,
                default_sample_rate=48_000,
            )
        ]
