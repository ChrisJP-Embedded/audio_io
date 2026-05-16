"""Audio backend interfaces and the sounddevice implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

import numpy as np
from numpy.typing import NDArray

from audio_io.config import AudioIOConfig

AudioBlock = NDArray[np.float32]
StreamCallback = Callable[[AudioBlock | None, AudioBlock | None, int, object, object], None]


@dataclass(frozen=True)
class DeviceInfo:
    name: str
    index: int
    max_input_channels: int
    max_output_channels: int
    default_sample_rate: float


class StreamHandle(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def close(self) -> None:
        ...

    @property
    def active(self) -> bool:
        ...


class AudioBackend(Protocol):
    def open_stream(self, config: AudioIOConfig, callback: StreamCallback) -> StreamHandle:
        ...

    def list_devices(self) -> list[DeviceInfo]:
        ...


class SoundDeviceBackend:
    """Backend backed by python-sounddevice."""

    def __init__(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "sounddevice is required for real audio devices. "
                "Install audio-io with its default dependencies."
            ) from exc
        self._sd = sd

    def open_stream(self, config: AudioIOConfig, callback: StreamCallback) -> StreamHandle:
        device = self._resolve_device(config.device)
        input_channel_span = _channel_span(config.input_channels)
        output_channel_span = _channel_span(config.output_channels)

        stream_kwargs = {
            "samplerate": config.sample_rate,
            "blocksize": config.block_words,
            "dtype": config.dtype,
            "device": device,
        }

        if config.input_channel_count and config.output_channel_count:
            return self._sd.Stream(
                **stream_kwargs,
                channels=(input_channel_span, output_channel_span),
                callback=_duplex_callback(config, callback),
            )
        if config.input_channel_count:
            return self._sd.InputStream(
                **stream_kwargs,
                channels=input_channel_span,
                callback=_input_callback(config, callback),
            )
        if config.output_channel_count:
            return self._sd.OutputStream(
                **stream_kwargs,
                channels=output_channel_span,
                callback=_output_callback(config, callback),
            )
        raise ValueError("At least one input or output channel must be configured")

    def list_devices(self) -> list[DeviceInfo]:
        devices = self._sd.query_devices()
        return [
            DeviceInfo(
                name=str(device["name"]),
                index=index,
                max_input_channels=int(device["max_input_channels"]),
                max_output_channels=int(device["max_output_channels"]),
                default_sample_rate=float(device["default_samplerate"]),
            )
            for index, device in enumerate(devices)
        ]

    def _resolve_device(self, device: str | int | None) -> str | int | None:
        if not isinstance(device, str):
            return device

        matches = [info for info in self.list_devices() if device.lower() in info.name.lower()]
        if not matches:
            raise ValueError(f"No audio device matched {device!r}")
        if len(matches) > 1:
            names = ", ".join(match.name for match in matches[:5])
            raise ValueError(f"Device name {device!r} matched multiple devices: {names}")
        return matches[0].index


def list_devices(backend: AudioBackend | None = None) -> list[DeviceInfo]:
    selected_backend = backend or SoundDeviceBackend()
    return selected_backend.list_devices()


def _channel_span(channels: tuple[int, ...]) -> int:
    if not channels:
        return 0
    return max(channels) + 1


def _select_channels(block: AudioBlock, channels: tuple[int, ...]) -> AudioBlock:
    if tuple(channels) == tuple(range(len(channels))):
        return block
    return np.ascontiguousarray(block[:, channels])


def _write_channels(target: AudioBlock, source: AudioBlock, channels: tuple[int, ...]) -> None:
    target[:] = 0
    if tuple(channels) == tuple(range(len(channels))):
        target[:] = source
        return
    target[:, channels] = source


def _duplex_callback(config: AudioIOConfig, callback: StreamCallback):
    def wrapped(indata: AudioBlock, outdata: AudioBlock, frames: int, time: object, status: object) -> None:
        selected_input = _select_channels(indata, config.input_channels)
        compact_output = np.zeros((frames, config.output_channel_count), dtype=config.dtype)
        callback(selected_input, compact_output, frames, time, status)
        _write_channels(outdata, compact_output, config.output_channels)

    return wrapped


def _input_callback(config: AudioIOConfig, callback: StreamCallback):
    def wrapped(indata: AudioBlock, frames: int, time: object, status: object) -> None:
        callback(_select_channels(indata, config.input_channels), None, frames, time, status)

    return wrapped


def _output_callback(config: AudioIOConfig, callback: StreamCallback):
    def wrapped(outdata: AudioBlock, frames: int, time: object, status: object) -> None:
        compact_output = np.zeros((frames, config.output_channel_count), dtype=config.dtype)
        callback(None, compact_output, frames, time, status)
        _write_channels(outdata, compact_output, config.output_channels)

    return wrapped
