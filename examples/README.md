# Examples

These scripts exercise the public `audio_io` API against real audio devices.
Run them from the repository root through Poetry:

```powershell
poetry install
poetry run audio-io-list-devices
```

Each example lives in its own directory with a local `README.md`. The folders
are intended to be easy starting points for a new app: copy the folder, keep the
root `pyproject.toml` dependency set or add `audio-io` plus the same runtime
dependencies to your app, then adapt `main.py`.

This repository intentionally has only one Poetry project file at the root. The
top-level `pyproject.toml` owns the package, all example dependencies, and the
console scripts below.

Use [list_devices](list_devices/README.md) first to find the interface index or name to
pass to the other examples. Interface names can be exact names, substrings, or
numeric device indices.

## List Devices

```powershell
poetry run audio-io-list-devices
```

Example output:

```text
 0: Built-in Audio in=2 out=2 default_sr=48000
 2: Focusrite USB in=2 out=2 default_sr=48000
```

## Play a Sine Wave

```powershell
poetry run audio-io-sine-output --interface 2 --frequency 1000 --channels 0,1 --amplitude 0.2 --seconds 5
```

Useful options:

- `--interface`: interface index or name substring
- `--channels`: comma-separated zero-based output channels
- `--frequency`: sine frequency in Hz
- `--amplitude`: linear amplitude from `0.0` to `1.0`
- `--phase-degrees`: initial phase offset
- `--seconds`: run duration; omit to run until `Ctrl+C`

## Measure Input Level

```powershell
poetry run audio-io-input-meter --interface 0 --channels 0 --block-words 1024
```

The meter prints RMS level in dBFS for each selected input channel. With the
default float format, `0 dBFS` is full scale and quieter signals are negative.

## View a Live Waveform

```powershell
poetry run audio-io-live-waveform --interface 0 --channels 0
```

This starts a local web display at `http://127.0.0.1:8765/` and opens it in your
default browser. The page polls the latest input block and draws each selected
channel on its own lane. Use the time and amplitude sliders to zoom the rolling
line chart while it is running.

Useful options:

- `--interface`: interface index or name substring
- `--channels`: comma-separated zero-based input channels
- `--block-words`: frames captured per callback block
- `--host` and `--port`: local HTTP bind address
- `--no-browser`: print the URL without opening a browser

## Check a Loopback Level

Patch an output channel back into an input channel, then run:

```powershell
poetry run audio-io-loopback-check --interface 2 --output-channels 0,1 --input-channels 0 --sine-dbfs -12 --tolerance-db 1
```

The script generates a sine wave at the requested peak level, captures input for
the measurement window, and exits with `0` when every selected input channel is
within tolerance.

## Channel Numbering

All channel arguments are zero-based logical interface channels. For example,
`--channels 0,1` selects hardware channels 1 and 2, while `--channels 0,2`
selects hardware channels 1 and 3.

Inside callbacks and queued blocks, selected channels are compacted. A sparse
selection such as `output_channels=[0, 2]` still expects a two-column output
block; the backend routes those columns to the requested hardware channels.

## Troubleshooting

If an example prints `error: sounddevice is required`, run `poetry install` from
the repository root and launch the script with `poetry run`.

On macOS, grant microphone permission to the terminal or IDE before running
input examples.
