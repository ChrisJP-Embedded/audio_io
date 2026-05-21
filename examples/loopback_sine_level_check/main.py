"""Play a sine at a known dBFS level and verify input level."""

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
    try:
        return tuple(int(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise ValueError(f"channels must be comma-separated integers, got {value!r}") from exc


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
        phase_step = 2.0 * math.pi * self.frequency_hz / self.sample_rate
        phases = self._phase + phase_step * np.arange(frames, dtype=np.float32)
        mono = (self.amplitude * np.sin(phases)).astype(np.float32)
        self._phase = float((phases[-1] + phase_step) % (2.0 * math.pi))
        return np.repeat(mono[:, np.newaxis], self.channels, axis=1)


def dbfs_to_peak(dbfs: float) -> float:
    """Convert a dBFS peak level to linear float amplitude."""

    if dbfs > 0.0:
        raise ValueError("sine-dbfs must be less than or equal to 0")
    return 10.0 ** (dbfs / 20.0)


def peak_to_dbfs(peak: np.ndarray, *, floor_db: float = -120.0) -> np.ndarray:
    with np.errstate(divide="ignore"):
        db = 20.0 * np.log10(peak)
    return np.maximum(db, floor_db)


def estimate_sine_peak_dbfs(block: np.ndarray, *, frequency_hz: float, sample_rate: int) -> np.ndarray:
    """Estimate sine peak level per channel using least-squares sine fitting."""

    if block.ndim != 2:
        raise ValueError("block must be shaped as (frames, channels)")
    if len(block) < 3:
        raise ValueError("at least three frames are required to estimate sine level")

    frame_indices = np.arange(len(block), dtype=np.float64)
    radians = 2.0 * math.pi * frequency_hz * frame_indices / sample_rate

    # Fit sin, cos, and DC terms. Combining the sin/cos coefficients recovers
    # amplitude even when the captured signal has an arbitrary phase offset.
    design = np.column_stack((np.sin(radians), np.cos(radians), np.ones(len(block))))
    coefficients, *_ = np.linalg.lstsq(design, block.astype(np.float64), rcond=None)
    sine_coefficients = coefficients[:2, :]
    peak = np.sqrt(np.sum(np.square(sine_coefficients), axis=0))
    return peak_to_dbfs(peak)


def levels_within_tolerance(measured_dbfs: np.ndarray, expected_dbfs: float, tolerance_db: float) -> np.ndarray:
    return np.abs(measured_dbfs - expected_dbfs) <= tolerance_db


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify looped-back sine level in dBFS.")
    parser.add_argument("--interface", required=True, help="Interface name substring or numeric device index.")
    parser.add_argument("--input-channels", default="0", help="Comma-separated zero-based input channels.")
    parser.add_argument("--output-channels", default="0,1", help="Comma-separated zero-based output channels.")
    parser.add_argument("--frequency", type=float, default=1000.0, help="Sine frequency in Hz.")
    parser.add_argument("--sine-dbfs", type=float, default=-12.0, help="Generated sine peak level in dBFS.")
    parser.add_argument("--tolerance-db", type=float, default=1.0, help="Allowed input level error in dB.")
    parser.add_argument("--phase-degrees", type=float, default=0.0, help="Initial sine phase offset in degrees.")
    parser.add_argument("--sample-rate", type=int, default=48_000, help="Sample rate in Hz.")
    parser.add_argument("--block-words", type=int, default=256, help="Frames per callback block.")
    parser.add_argument("--settle-seconds", type=float, default=0.25, help="Warm-up time before measuring.")
    parser.add_argument("--measure-seconds", type=float, default=1.0, help="Measurement capture duration.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        interface = int(args.interface) if args.interface.isdigit() else args.interface
        input_channels = parse_channels(args.input_channels)
        output_channels = parse_channels(args.output_channels)
        amplitude = dbfs_to_peak(args.sine_dbfs)
        config = AudioIOConfig(
            interface=interface,
            input_channels=input_channels,
            output_channels=output_channels,
            sample_rate=args.sample_rate,
            block_words=args.block_words,
        )
        generator = SineGenerator(
            frequency_hz=args.frequency,
            sample_rate=args.sample_rate,
            channels=config.output_channel_count,
            amplitude=amplitude,
            phase_degrees=args.phase_degrees,
        )
    except ValueError as exc:
        return print_config_error(exc)

    print(config.timing_status.console_line())
    print(
        f"Generating {args.frequency:g} Hz at {args.sine_dbfs:g} dBFS peak "
        f"on output channels {output_channels}; measuring input channels {input_channels}."
    )
    try:
        with AudioIOSession(config, output_callback=generator) as session:
            time.sleep(args.settle_seconds)
            blocks = []
            deadline = time.monotonic() + args.measure_seconds
            while time.monotonic() < deadline:
                blocks.append(session.read_input_block(timeout=1.0))
    except AudioIOConfigError as exc:
        return print_config_error(exc)
    except RuntimeError as exc:
        return print_runtime_error(exc)

    if not blocks:
        print("FAIL: no input blocks captured")
        return 1

    measured = estimate_sine_peak_dbfs(
        np.concatenate(blocks, axis=0),
        frequency_hz=args.frequency,
        sample_rate=args.sample_rate,
    )
    passed = levels_within_tolerance(measured, args.sine_dbfs, args.tolerance_db)

    for channel, level, ok in zip(input_channels, measured, passed, strict=True):
        status = "PASS" if ok else "FAIL"
        delta = level - args.sine_dbfs
        print(f"{status}: input ch {channel}: {level:7.2f} dBFS ({delta:+.2f} dB)")

    return 0 if bool(np.all(passed)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
