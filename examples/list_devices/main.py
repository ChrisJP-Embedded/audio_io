"""List audio interfaces visible to the current platform backend."""

from __future__ import annotations

try:
    from _example_bootstrap import add_src_to_path, print_runtime_error
except ImportError:
    try:
        from examples._example_bootstrap import add_src_to_path, print_runtime_error
    except ImportError:
        import sys

        def add_src_to_path() -> None:
            return

        def print_runtime_error(exc: RuntimeError) -> int:
            print(f"error: {exc}", file=sys.stderr)
            return 1

add_src_to_path()

from audio_io import list_devices  # noqa: E402


def main() -> int:
    try:
        for device in list_devices():
            print(
                f"{device.index:>2}: {device.name} "
                f"in={device.max_input_channels} out={device.max_output_channels} "
                f"default_sr={device.default_sample_rate:g}"
            )
    except RuntimeError as exc:
        return print_runtime_error(exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
