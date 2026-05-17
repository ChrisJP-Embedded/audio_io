# Sine Output

Play a continuous sine wave through selected output channels.

```powershell
poetry run audio-io-sine-output --interface 2 --frequency 1000 --channels 0,1 --amplitude 0.2 --phase-degrees 0
```

Useful options:

- `--interface`: interface index or name substring
- `--channels`: comma-separated zero-based output channels
- `--frequency`: sine frequency in Hz
- `--amplitude`: linear amplitude from `0.0` to `1.0`
- `--phase-degrees`: initial sine phase offset in degrees
- `--seconds`: run duration; omit to run until `Ctrl+C`
