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

The printed device index can be passed as `--device 2`, or you can pass part of
the device name, such as `--device "Focusrite"`.

## Play a 1000 Hz Sine Wave

```powershell
poetry run python examples/sine_output.py --frequency 1000 --channels 0,1 --amplitude 0.2
```

Useful options:

- `--device`: device index or name substring
- `--channels`: comma-separated zero-based output channels
- `--frequency`: sine frequency in Hz
- `--amplitude`: linear amplitude from `0.0` to `1.0`
- `--block-words`: frames per callback block
- `--seconds`: run duration; omit to run until `Ctrl+C`

## Measure Input Level in dBFS

```powershell
poetry run python examples/input_level_meter.py --channels 0
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
    device="Built-in",
    input_channels=(0,),
    output_channels=(0, 1),
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
    input_channels=(0,),
    output_channels=(0, 1),
    block_words=512,
)

with AudioIOSession(config) as session:
    session.write_output_block([[0.0, 0.0]] * config.block_words)
    captured = session.read_input_block(timeout=1.0)
```

If no output block is queued in time, silence is rendered.

## Channel Selection

Channels are zero-based logical device channels. The caller always sees compact
blocks shaped as `(frames, selected_channels)`.

For example, `output_channels=(0, 2)` means the caller writes two-column blocks,
and the backend routes those columns to hardware channels 1 and 3.

## VS Code Tasks

The repo includes `.vscode/tasks.json` with:

- `example: list devices`
- `example: 1000 Hz sine output`
- `example: input dB meter`
- `test: pytest`
- `clean: python caches`
