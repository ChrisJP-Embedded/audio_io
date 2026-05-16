# Usage

This package exposes a block-based audio I/O API that works the same way on
Windows and macOS. The default backend uses `sounddevice`, which wraps
PortAudio.

## Install for Development

```powershell
poetry install
```

Run commands inside the Poetry environment:

```powershell
poetry run python examples/list_devices.py
```

## List Devices

```powershell
poetry run python examples/list_devices.py
```

The printed interface index can be passed as `--interface 2`, or you can pass
part of the interface name, such as `--interface "Focusrite"`.

## Play a 1000 Hz Sine Wave

```powershell
poetry run python examples/sine_output.py --interface 2 --frequency 1000 --channels 0,1 --amplitude 0.2 --phase-degrees 0
```

Useful options:

- `--interface`: interface index or name substring
- `--channels`: comma-separated zero-based output channels
- `--frequency`: sine frequency in Hz
- `--amplitude`: linear amplitude from `0.0` to `1.0`
- `--phase-degrees`: initial sine phase offset in degrees
- `--block-words`: frames per callback block
- `--seconds`: run duration; omit to run until `Ctrl+C`

For example, `--phase-degrees 90` starts the sine wave at the positive peak.

## Measure Input Level in dBFS

```powershell
poetry run python examples/input_level_meter.py --interface 0 --channels 0
```

The meter reports RMS level per selected channel. With the default float audio
format, `0 dBFS` is full scale and quieter signals are negative values.

On macOS, grant microphone permission to the terminal or IDE if the input meter
does not receive samples.

## Use Callbacks

```python
from audio_io import AudioIOConfig, AudioIOSession


def on_input(block, info):
    print(block.shape, info.frame_count)


def on_output(frame_count, info):
    return None


config = AudioIOConfig(
    interface="Built-in",
    input_channels=[0],
    output_channels=[0, 1],
    sample_rate=48_000,
    block_words=256,
)

with AudioIOSession(config, input_callback=on_input, output_callback=on_output):
    input("Press Enter to stop...")
```

Returning `None` from an output callback renders silence for that block.

## Use Queues

```python
from audio_io import AudioIOConfig, AudioIOSession

config = AudioIOConfig(
    interface="Built-in",
    input_channels=[0],
    output_channels=[0, 1],
    block_words=512,
)

with AudioIOSession(config) as session:
    session.write_output_block([[0.0, 0.0]] * config.block_words)
    captured = session.read_input_block(timeout=1.0)
```

If no output block is queued in time, silence is rendered.

## Channel Selection

Channels are zero-based logical interface channels. The caller always sees compact
blocks shaped as `(frames, selected_channels)`.

For example, `output_channels=[0, 2]` means the caller writes two-column blocks,
and the backend routes those columns to hardware channels 1 and 3.

`input_channels` and `output_channels` should be lists or other sequences with
one or more entries when that side of the interface is used:

```python
AudioIOConfig(interface="Focusrite", input_channels=[0], output_channels=[0, 1])
```

The session validates the named interface and channel lists before opening the
stream. Bad interface names raise `InterfaceNotFoundError`. Channel requests
outside the available input/output range raise `InvalidChannelRequestError`, and
the error message names the failing side, such as `input channel request
invalid` or `output channel request invalid`.

## VS Code Tasks

The repo includes `.vscode/tasks.json` with:

- `example: list devices`
- `example: 1000 Hz sine output`
- `example: input dB meter`
- `test: pytest`
- `clean: python caches`
