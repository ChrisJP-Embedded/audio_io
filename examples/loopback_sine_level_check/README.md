# Loopback Sine Level Check

Generate a known-level sine wave and verify selected input channels receive it
within a dB tolerance.

```powershell
poetry run audio-io-loopback-check --interface 2 --output-channels 0,1 --input-channels 0 --sine-dbfs -12 --tolerance-db 1
```

As a copied app template:

```powershell
poetry install
poetry run run-example --interface 2 --output-channels 0,1 --input-channels 0 --sine-dbfs -12 --tolerance-db 1
```

Or run `.\setup.ps1` on Windows PowerShell / `./setup.sh` on macOS or Linux.
The local `.vscode/tasks.json` includes clean, install, and run tasks for the
copied app.

Patch the requested output channel back into the requested input channel before
running this example.

Useful options:

- `--interface`: full-duplex interface index or name substring
- `--output-channels`: comma-separated zero-based output channels to drive
- `--input-channels`: comma-separated zero-based input channels to verify
- `--sine-dbfs`: generated sine peak level in dBFS
- `--tolerance-db`: allowed input level error in dB
- `--frequency`: sine frequency in Hz
- `--measure-seconds`: capture duration used for the level estimate
