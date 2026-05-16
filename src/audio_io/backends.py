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


class AudioIOConfigError(ValueError):
    """Raised when a requested interface or channel layout is invalid."""


class InterfaceNotFoundError(AudioIOConfigError):
    """Raised when an interface name or index cannot be resolved."""


class InvalidChannelRequestError(AudioIOConfigError):
    """Raised when a channel list is incompatible with an interface."""


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
        device_info = resolve_interface(self.list_devices(), config.interface)
        validate_channel_request(config, device_info)
        input_channel_span = _channel_span(config.input_channels)
        output_channel_span = _channel_span(config.output_channels)

        stream_kwargs = {
            "samplerate": config.sample_rate,
            "blocksize": config.block_words,
            "dtype": config.dtype,
            "device": device_info.index,
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
        raise AudioIOConfigError("at least one input or output channel must be configured")

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


def list_devices(backend: AudioBackend | None = None) -> list[DeviceInfo]:
    selected_backend = backend or SoundDeviceBackend()
    return selected_backend.list_devices()


def resolve_interface(devices: list[DeviceInfo], interface: str | int | None) -> DeviceInfo:
    if not devices:
        raise InterfaceNotFoundError("No audio interfaces are available")

    if interface is None:
        raise InterfaceNotFoundError("audio interface must be named with AudioIOConfig.interface")

    if isinstance(interface, int):
        for device in devices:
            if device.index == interface:
                return device
        raise InterfaceNotFoundError(f"No audio interface has index {interface}")

    matches = [info for info in devices if interface.lower() in info.name.lower()]
    if not matches:
        raise InterfaceNotFoundError(f"No audio interface matched {interface!r}")
    if len(matches) > 1:
        names = ", ".join(match.name for match in matches[:5])
        raise InterfaceNotFoundError(f"Audio interface name {interface!r} matched multiple interfaces: {names}")
    return matches[0]


def validate_channel_request(config: AudioIOConfig, interface: DeviceInfo) -> None:
    _validate_channel_list(
        side="input",
        channels=config.input_channels,
        available=interface.max_input_channels,
        interface=interface,
    )
    _validate_channel_list(
        side="output",
        channels=config.output_channels,
        available=interface.max_output_channels,
        interface=interface,
    )


def _validate_channel_list(
    *,
    side: str,
    channels: tuple[int, ...],
    available: int,
    interface: DeviceInfo,
) -> None:
    if not channels:
        return
    invalid = [channel for channel in channels if channel >= available]
    if invalid:
        raise InvalidChannelRequestError(
            f"{side} channel request invalid for {side} channel list {list(channels)!r}: "
            f"interface {interface.name!r} has {available} {side} channel(s); "
            f"invalid channel(s): {invalid!r}"
        )


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
