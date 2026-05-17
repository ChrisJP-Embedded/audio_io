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

See [USAGE.md](USAGE.md) for API usage, [examples/README.md](examples/README.md)
for runnable example scripts, and [VERSION.md](VERSION.md) for release notes.

## Install

```powershell
poetry install
```

Run commands inside the Poetry environment:

```powershell
poetry run audio-io-list-devices
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
    interface="Focusrite USB",
    input_channels=[0, 1],
    output_channels=[0, 1],
    sample_rate=48_000,
    block_words=256,
)

with AudioIOSession(config, input_callback=on_input, output_callback=on_output) as session:
    input_devices = session.is_active
```

Channel selections are zero-based and compacted for the caller. For example,
`output_channels=[0, 2]` lets the caller write two-column output blocks; the
backend routes those columns to hardware channels 1 and 3.

At startup, the backend validates the named interface and requested input/output
channel lists. Invalid requests raise `InterfaceNotFoundError` or
`InvalidChannelRequestError` with a message that names the failing side.
The example CLIs catch these errors and print a short `error:` message.

## Queue usage

```python
from audio_io import AudioIOConfig, AudioIOSession

config = AudioIOConfig(
    interface="Built-in Audio",
    input_channels=[0],
    output_channels=[0, 1],
    block_words=512,
)

with AudioIOSession(config) as session:
    session.write_output_block([[0.0, 0.0]] * config.block_words)
    captured = session.read_input_block(timeout=1.0)
```

## Interface lookup

```python
from audio_io import list_devices

for device in list_devices():
    print(device.name, device.max_input_channels, device.max_output_channels)
```

From the command line:

```powershell
poetry run audio-io-list-devices
```

## Example Apps

Play a 1000 Hz sine wave on output channels 0 and 1:

```powershell
poetry run audio-io-sine-output --interface 2 --frequency 1000 --channels 0,1 --amplitude 0.2 --phase-degrees 0
```

Show a GUI RMS input level meter with scalable waveform and FFT views on input channel 0:

```powershell
poetry run audio-io-input-meter --interface 0 --channels 0
```

Show a live input waveform in your browser:

```powershell
poetry run audio-io-live-waveform --interface 0 --channels 0
```

Generate a known-level sine and verify the measured input level is present
within tolerance:

```powershell
poetry run audio-io-loopback-check --interface 2 --output-channels 0,1 --input-channels 0 --sine-dbfs -12 --tolerance-db 1
```

Both examples accept `--interface`, which can be a device name substring or a
numeric device index from `audio-io-list-devices`. Replace `0` and `2` with
the interface indices or names reported by your machine:

```powershell
poetry run audio-io-sine-output --interface "Focusrite" --channels 0,1
poetry run audio-io-input-meter --interface 2 --channels 0 --block-words 1024
```

The sine example accepts `--phase-degrees` to apply an initial phase offset to
the generated waveform. For example, `--phase-degrees 90` starts the tone at the
positive peak.

The examples run through the same package API on Windows and macOS. On macOS,
you may need to grant microphone permission to the terminal or IDE before input
metering can receive samples.
