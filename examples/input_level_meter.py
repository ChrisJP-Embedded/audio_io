"""Measure input level in dBFS from an audio input device."""

from __future__ import annotations

import argparse
import math
import time
from collections.abc import Sequence

import numpy as np

try:
    from _example_bootstrap import add_src_to_path, print_runtime_error
except ImportError:
    from examples._example_bootstrap import add_src_to_path, print_runtime_error

add_src_to_path()

from audio_io import AudioIOConfig, AudioIOSession  # noqa: E402


def parse_channels(value: str) -> tuple[int, ...]:
    if not value.strip():
        return ()
    return tuple(int(part.strip()) for part in value.split(","))


def rms_dbfs(block: np.ndarray, *, floor_db: float = -120.0) -> np.ndarray:
    if block.ndim != 2:
        raise ValueError("block must be shaped as (frames, channels)")
    rms = np.sqrt(np.mean(np.square(block.astype(np.float32)), axis=0))
    with np.errstate(divide="ignore"):
        db = 20.0 * np.log10(rms)
    return np.maximum(db, floor_db)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show input RMS level in dBFS.")
    parser.add_argument("--interface", default=None, help="Interface name substring or numeric device index.")
    parser.add_argument("--device", default=None, help="Deprecated alias for --interface.")
    parser.add_argument("--channels", default="0", help="Comma-separated zero-based input channels.")
    parser.add_argument("--sample-rate", type=int, default=48_000, help="Sample rate in Hz.")
    parser.add_argument("--block-words", type=int, default=1024, help="Frames per callback block.")
    parser.add_argument("--seconds", type=float, default=None, help="Run duration. Omit to run until Ctrl+C.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_channels = parse_channels(args.channels)
    interface_arg = args.interface if args.interface is not None else args.device
    if interface_arg is None:
        build_parser().error("--interface is required")
    interface = int(interface_arg) if interface_arg and interface_arg.isdigit() else interface_arg
    config = AudioIOConfig(
        interface=interface,
        input_channels=input_channels,
        sample_rate=args.sample_rate,
        block_words=args.block_words,
    )

    print(f"Measuring channels {input_channels} in dBFS. Press Ctrl+C to stop.")
    start = time.monotonic()
    try:
        with AudioIOSession(config) as session:
            while args.seconds is None or time.monotonic() - start < args.seconds:
                block = session.read_input_block(timeout=1.0)
                levels = rms_dbfs(block)
                level_text = "  ".join(
                    f"ch {channel}: {level:7.2f} dBFS"
                    for channel, level in zip(input_channels, levels, strict=True)
                )
                print(level_text)
    except RuntimeError as exc:
        return print_runtime_error(exc)
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
