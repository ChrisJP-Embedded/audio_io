"""Play a continuous sine wave through an audio output device."""

from __future__ import annotations

import argparse
import math
import time
from collections.abc import Sequence

import numpy as np

try:
    from _example_bootstrap import add_src_to_path, print_config_error, print_runtime_error
except ImportError:
    try:
        from examples._example_bootstrap import add_src_to_path, print_config_error, print_runtime_error
    except ImportError:
        import sys

        def add_src_to_path() -> None:
            return

        def print_config_error(exc: Exception) -> int:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        def print_runtime_error(exc: RuntimeError) -> int:
            print(f"error: {exc}", file=sys.stderr)
            return 1

add_src_to_path()

from audio_io import AudioIOConfig, AudioIOConfigError, AudioIOSession  # noqa: E402


def parse_channels(value: str) -> tuple[int, ...]:
    """Parse comma-separated zero-based channel indices from the CLI."""

    if not value.strip():
        return ()
    return tuple(int(part.strip()) for part in value.split(","))


class SineGenerator:
    def __init__(
        self,
        *,
        frequency_hz: float,
        sample_rate: int,
        channels: int,
        amplitude: float,
        phase_degrees: float = 0.0,
    ) -> None:
        if not 0.0 <= amplitude <= 1.0:
            raise ValueError("amplitude must be between 0.0 and 1.0")
        self.frequency_hz = frequency_hz
        self.sample_rate = sample_rate
        self.channels = channels
        self.amplitude = amplitude
        self._phase = math.radians(phase_degrees) % (2.0 * math.pi)

    def __call__(self, frames: int, info: object) -> np.ndarray:
        # Keep phase continuous across callback blocks so the waveform does not
        # click at block boundaries.
        phase_step = 2.0 * math.pi * self.frequency_hz / self.sample_rate
        phases = self._phase + phase_step * np.arange(frames, dtype=np.float32)
        mono = (self.amplitude * np.sin(phases)).astype(np.float32)
        self._phase = float((phases[-1] + phase_step) % (2.0 * math.pi))
        return np.repeat(mono[:, np.newaxis], self.channels, axis=1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Play a continuous sine wave.")
    parser.add_argument("--interface", default=None, help="Interface name substring or numeric device index.")
    parser.add_argument("--device", default=None, help="Deprecated alias for --interface.")
    parser.add_argument("--channels", default="0,1", help="Comma-separated zero-based output channels.")
    parser.add_argument("--frequency", type=float, default=1000.0, help="Sine frequency in Hz.")
    parser.add_argument("--amplitude", type=float, default=0.2, help="Linear amplitude from 0.0 to 1.0.")
    parser.add_argument("--phase-degrees", type=float, default=0.0, help="Initial sine phase offset in degrees.")
    parser.add_argument("--sample-rate", type=int, default=48_000, help="Sample rate in Hz.")
    parser.add_argument("--block-words", type=int, default=256, help="Frames per callback block.")
    parser.add_argument("--seconds", type=float, default=None, help="Run duration. Omit to run until Ctrl+C.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_channels = parse_channels(args.channels)
    interface_arg = args.interface if args.interface is not None else args.device
    if interface_arg is None:
        build_parser().error("--interface is required")
    interface = int(interface_arg) if interface_arg and interface_arg.isdigit() else interface_arg

    config = AudioIOConfig(
        interface=interface,
        output_channels=output_channels,
        sample_rate=args.sample_rate,
        block_words=args.block_words,
    )
    generator = SineGenerator(
        frequency_hz=args.frequency,
        sample_rate=args.sample_rate,
        channels=config.output_channel_count,
        amplitude=args.amplitude,
        phase_degrees=args.phase_degrees,
    )

    print(
        f"Playing {args.frequency:g} Hz at {args.phase_degrees:g} degrees "
        f"on channels {output_channels}. Press Ctrl+C to stop."
    )
    try:
        with AudioIOSession(config, output_callback=generator):
            if args.seconds is None:
                while True:
                    time.sleep(0.25)
            else:
                time.sleep(args.seconds)
    except AudioIOConfigError as exc:
        return print_config_error(exc)
    except RuntimeError as exc:
        return print_runtime_error(exc)
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
