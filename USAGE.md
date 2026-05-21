# Usage

This package exposes a block-based audio I/O API that works the same way on
Windows and macOS. The default backend uses `sounddevice`, which wraps
PortAudio.

## Install for Development

```powershell
poetry install
```

In VS Code, the root workspace also includes `setup: poetry env`, which installs
the repo development environment with GUI example support.

Install the GUI extra before running pywebview examples in a new environment:

```powershell
poetry install --extras gui
```

Run commands inside the Poetry environment:

```powershell
poetry run audio-io-list-devices
```

## List Devices

```powershell
poetry run audio-io-list-devices
```

The printed interface index can be passed as `--interface 2`, or you can pass
part of the interface name, such as `--interface "Focusrite"`.

## Play a 1000 Hz Sine Wave

```powershell
poetry run audio-io-sine-output --interface 2 --frequency 1000 --channels 0,1 --amplitude 0.2 --phase-degrees 0
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
poetry run audio-io-input-meter --interface 0 --channels 0
```

The meter opens a native pywebview GUI with dB meters, display gain, a live
uPlot waveform, integrated X/Y waveform scaling, and a buffered FFT chart. Use
the waveform panel controls to zoom the visible time window down to a few
milliseconds and tighten the chart Y-axis around quieter signals without
changing the measured dBFS values. With the default float audio format,
`0 dBFS` is full scale and quieter signals are negative values. The default
`--block-words 256` keeps GUI updates responsive while leaving enough samples
for stable RMS readings.

On macOS, grant microphone permission to the terminal or IDE if the input meter
does not receive samples.

## View Web Analysis in a Browser

```powershell
poetry run audio-io-webview-analysis --interface 0 --channels 0
```

The webview analysis example starts a small local HTTP server at
`http://127.0.0.1:8765/`, opens a compact fixed-size pywebview window, and draws
the latest input callback block as a rolling waveform with a live FFT bar chart
below it. The view includes time and amplitude controls for scaling the line
chart. Use `--no-browser` if you want to open the URL yourself, or `--port` to
choose a different local port.

## Check Loopback Sine Level

```powershell
poetry run audio-io-loopback-check --interface 2 --output-channels 0,1 --input-channels 0 --sine-dbfs -12 --tolerance-db 1
```

This plays a sine wave at a known peak dBFS level and measures the selected
input channels. The example exits with `0` when every measured input channel is
within `--tolerance-db` of `--sine-dbfs`; otherwise it exits with `1`.

Useful options:

- `--interface`: full-duplex interface index or name substring
- `--output-channels`: comma-separated zero-based output channels to drive
- `--input-channels`: comma-separated zero-based input channels to verify
- `--sine-dbfs`: generated sine peak level in dBFS
- `--tolerance-db`: allowed input level error in dB
- `--frequency`: sine frequency in Hz
- `--settle-seconds`: warm-up time before measurement
- `--measure-seconds`: capture duration used for the level estimate

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

Exceptions raised by input or output callbacks are caught inside the session
callback boundary. `session.last_error` stores the latest exception. Output
callback failures render silence for the failing block, and the session
schedules up to `callback_restart_attempts` delayed stream restarts, with
`callback_restart_delay_seconds` between attempts. Set
`callback_restart_attempts=0` for no automatic restart attempts.

Use `config.timing_status` to inspect the requested sample-rate/block-size
timing before opening a stream:

```python
print(config.timing_status.console_line())
```

Example output:

```text
Audio timing: fs=192000 Hz, 1/fs=5.208 us, block=256 frames (1.333 ms), callbacks=750.0/s, status=warning - higher glitch risk; consider a larger block
```

The status is based on callback rate. `good` is comfortable, `caution` means
callbacks should stay lightweight, `warning` indicates higher glitch risk, and
`high-risk` means the request is likely fragile in Python callbacks.

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

The example applications catch these configuration errors and return exit code
`1` after printing a short `error:` message.

## API Stability

`audio-io` is pre-1.0. The core `AudioIOConfig`, `AudioIOSession`, backend, and
exception APIs are intended to remain steady across normal `0.1.x` patch
releases. Larger API changes should be called out in `VERSION.md`.

## VS Code Tasks

The repo includes `.vscode/tasks.json` with:

- `setup: poetry env`
- `example: list devices`
- `example: 1000 Hz sine output`
- `example: input dB meter`
- `example: webview analysis`
- `example: loopback sine level check`
- `test: pytest`
- `clean: python caches`
