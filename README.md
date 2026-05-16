# audio-io

`audio-io` is a small Python package scaffold for block-based audio input and output.
It supports two usage styles:

- callback driven sessions, where callers receive input blocks and provide output blocks
- queue driven sessions, where callers read captured blocks and write playback blocks manually

The real device backend uses [`sounddevice`](https://python-sounddevice.readthedocs.io/),
which wraps PortAudio and runs on Windows and macOS. Platform-specific device
behavior stays inside the backend, while the public API uses the same
configuration object on both operating systems.
Tests use an in-memory fake backend, so they do not require audio hardware.

See [USAGE.md](USAGE.md) for practical examples and [VERSION.md](VERSION.md)
for release notes.

## Install

```powershell
python -m pip install -e ".[dev]"
```

If build isolation cannot download build tools in a restricted environment, use:

```powershell
python -m pip install --no-build-isolation -e ".[dev]"
```

## Callback usage

```python
from audio_io import AudioIOConfig, AudioIOSession

def on_input(block, info):
    print(block.shape, info)

def on_output(frame_count, info):
    # Return one block shaped as (frames, output_channels).
    return None  # Silence for this block.

config = AudioIOConfig(
    device="Focusrite USB",
    input_channels=(0, 1),
    output_channels=(0, 1),
    sample_rate=48_000,
    block_words=256,
)

with AudioIOSession(config, input_callback=on_input, output_callback=on_output) as session:
    input_devices = session.is_active
```

Channel selections are zero-based and compacted for the caller. For example,
`output_channels=(0, 2)` lets the caller write two-column output blocks; the
backend routes those columns to hardware channels 1 and 3.

## Queue usage

```python
from audio_io import AudioIOConfig, AudioIOSession

config = AudioIOConfig(
    device="Built-in Audio",
    input_channels=(0,),
    output_channels=(0, 1),
    block_words=512,
)

with AudioIOSession(config) as session:
    session.write_output_block([[0.0, 0.0]] * config.block_words)
    captured = session.read_input_block(timeout=1.0)
```

## Device lookup

```python
from audio_io import list_devices

for device in list_devices():
    print(device.name, device.max_input_channels, device.max_output_channels)
```

From the command line:

```powershell
python examples/list_devices.py
```

## Example Apps

Play a 1000 Hz sine wave on output channels 0 and 1:

```powershell
python examples/sine_output.py --frequency 1000 --channels 0,1 --amplitude 0.2
```

Measure RMS input level in dBFS on input channel 0:

```powershell
python examples/input_level_meter.py --channels 0
```

Both examples accept `--device`, which can be a device name substring or a
numeric device index from `examples/list_devices.py`:

```powershell
python examples/sine_output.py --device "Focusrite" --channels 0,1
python examples/input_level_meter.py --device 2 --channels 0 --block-words 1024
```

The examples run through the same package API on Windows and macOS. On macOS,
you may need to grant microphone permission to the terminal or IDE before input
metering can receive samples.
