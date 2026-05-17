# Input Level Meter

Measure RMS level in dBFS from selected input channels in a native pywebview GUI.

```powershell
poetry run audio-io-input-meter --interface 0 --channels 0
```

As a copied app template:

```powershell
poetry install
poetry run run-example --interface 0 --channels 0
```

Or run `.\setup.ps1` on Windows PowerShell / `./setup.sh` on macOS or Linux.
The local `.vscode/tasks.json` includes clean, install, and run tasks for the
copied app.

With the default float format, `0 dBFS` is full scale and quieter signals are
negative values. The default `--block-words 256` is chosen for responsive meter
updates without making the RMS display too noisy.

Useful options:

- `--interface`: interface index or name substring
- `--channels`: comma-separated zero-based input channels
- `--sample-rate`: sample rate in Hz
- `--block-words`: frames captured per callback block
- `--seconds`: run duration; omit to run until `Ctrl+C`
- `--debug`: enable pywebview debug mode
