# Input Level Meter

Measure RMS level in dBFS from selected input channels.

```powershell
poetry run audio-io-input-meter --interface 0 --channels 0 --block-words 1024
```

With the default float format, `0 dBFS` is full scale and quieter signals are
negative values.

Useful options:

- `--interface`: interface index or name substring
- `--channels`: comma-separated zero-based input channels
- `--sample-rate`: sample rate in Hz
- `--block-words`: frames captured per callback block
- `--seconds`: run duration; omit to run until `Ctrl+C`
