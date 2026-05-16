# Version

Current package version: `0.1.0`

The source of truth for the package version is `pyproject.toml`.

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
- setuptools build backend to reduce packaging friction in local editable
  installs

## Release Checklist

Before tagging a release:

1. Update `pyproject.toml`.
2. Update this file.
3. Update `README.md` and `USAGE.md` if behavior or examples changed.
4. Run `python -m pytest`.
5. Run the VS Code `clean: python caches` task or equivalent cache cleanup.
6. Commit changes.
7. Tag with `git tag vX.Y.Z`.
