"""List audio interfaces visible to the current platform backend."""

from __future__ import annotations

try:
    from _example_bootstrap import add_src_to_path, print_runtime_error
except ImportError:
    from examples._example_bootstrap import add_src_to_path, print_runtime_error

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
