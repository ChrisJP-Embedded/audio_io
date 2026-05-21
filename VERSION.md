# Version

Current package version: `0.1.13`

The source of truth for the package version is `pyproject.toml`.

## 0.1.13

Parent project readiness release.

Included:

- GUI dependencies moved behind the `gui` optional dependency extra
- runtime validation for supported audio sample dtypes
- callback exceptions are contained, recorded on `AudioIOSession.last_error`,
  and can trigger bounded delayed stream restart attempts
- example CLIs now print one-line parse/config errors for invalid channel text
- per-example Python version ranges aligned with the root package
- root VS Code setup task now installs the GUI extra for example app workflows
- `AudioIOConfig.timing_status` reports `1/fs`, block duration, callback rate,
  and a callback-load status; examples print it before opening streams

## 0.1.12

VS Code task alignment release.

Included:

- root `setup: poetry env` task for installing the Poetry environment
- root webview analysis task now uses the current `audio-io-webview-analysis` script
- documentation updates for the Poetry setup task
- regression test to keep root VS Code task commands aligned with console scripts

## 0.1.11

Integrated waveform controls release.

Included:

- waveform X/Y controls moved into the chart panel
- waveform Y zoom now updates the chart axis range directly
- waveform readout now reports the visible full-scale amplitude range
- cleaner meter toolbar focused on level and refresh controls

## 0.1.10

Waveform scaling release.

Included:

- shorter waveform X-axis windows down to 5 ms
- waveform Y-axis zoom up to x128 for quieter signals
- waveform scale readouts in the GUI metadata
- documentation updates for scope-style waveform controls

## 0.1.9

uPlot input meter visualization release.

Included:

- vendored uPlot assets for the input meter GUI
- webview analysis chart with selectable time window
- display gain control for dB meters
- buffered FFT chart below the waveform
- batched binary waveform/FFT payloads from Python to JavaScript
- rolling input history with display decimation for responsive updates

## 0.1.8

GUI input meter release.

Included:

- input level meter now uses a native pywebview GUI
- lower-latency `256` frame default block size for meter updates
- callback-fed meter state shared with JavaScript UI
- `pywebview` dependency for the root app and input-meter template
- tests for the GUI meter state

## 0.1.7

Copyable example app template release.

Included:

- per-example `pyproject.toml` files
- per-example Windows PowerShell setup scripts
- per-example macOS/Linux setup scripts
- per-example VS Code tasks for cleaning, installing, and running
- per-example README workflow for copied app usage
- root Poetry project remains the repo-wide package and example entry point

## 0.1.6

Example packaging release.

Included:

- one directory per runnable example
- per-example `README.md` files
- root `pyproject.toml` console scripts for every example
- VS Code tasks now run examples through root Poetry scripts
- no per-example Poetry project files; the top-level Poetry project remains the only environment source

## 0.1.5

Documentation and example alignment release.

Included:

- `examples/webview_analysis/`
- `examples/README.md`
- VS Code task for the webview analysis example
- webview analysis startup order now opens audio before serving/opening the browser
- docs and tests aligned with the full current example set

## 0.1.4

Example error-handling release.

Included:

- examples catch `AudioIOConfigError` without printing tracebacks
- invalid interface/channel requests now produce one-line CLI errors
- tests covering example CLI config-error paths

## 0.1.3

Loopback level-check example release.

Included:

- `examples/loopback_sine_level_check/`
- known peak dBFS sine generation for loopback checks
- input sine peak estimation that is independent of signal phase
- pass/fail tolerance checks in dB
- VS Code task for loopback level checks
- docs and tests for the level-check math

## 0.1.2

Sine example refinement release.

Included:

- `--phase-degrees` option for the sine output example
- `SineGenerator` support for initial phase offset
- VS Code sine task prompt for phase offset
- docs and tests for phase-shifted sine generation

## 0.1.1

API refinement release.

Included:

- `AudioIOConfig.interface` as the primary interface selector
- list-style `input_channels` and `output_channels`
- startup validation for unknown interfaces
- startup validation for invalid input channel requests
- startup validation for invalid output channel requests
- `InterfaceNotFoundError` and `InvalidChannelRequestError`
- examples updated to prefer `--interface`
- docs updated for interface/channel validation behavior

## 0.1.0

Initial development release.

Included:

- block-based `AudioIOSession`
- `AudioIOConfig` for device, channel, sample-rate, dtype, and block-size setup
- callback-based input and output
- queue-based input and output
- Windows/macOS `sounddevice` backend
- compact logical channel selection for non-contiguous hardware channels
- fake backend tests that run without audio hardware
- example apps for listing devices, playing a 1000 Hz sine wave, and measuring
  input RMS level in dBFS
- VS Code tasks for examples, tests, and cache cleanup
- Poetry dependency and virtual-environment workflow

## Release Checklist

Before tagging a release:

1. Update `pyproject.toml`.
2. Update this file.
3. Update `README.md` and `USAGE.md` if behavior or examples changed.
4. Run `poetry run python -m pytest`.
5. Run the VS Code `clean: python caches` task or equivalent cache cleanup.
6. Commit changes.
7. Tag with `git tag vX.Y.Z`.
