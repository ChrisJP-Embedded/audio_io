# Live Waveform Web

Show selected input channels as a live waveform in a local browser page.

```powershell
poetry run audio-io-live-waveform --interface 0 --channels 0
```

As a copied app template:

```powershell
poetry install
poetry run run-example --interface 0 --channels 0
```

Or run `.\setup.ps1` on Windows PowerShell / `./setup.sh` on macOS or Linux.
The local `.vscode/tasks.json` includes clean, install, and run tasks for the
copied app.

The example starts a local HTTP server at `http://127.0.0.1:8765/`, polls the
latest input block, and draws each selected channel on its own lane.

Useful options:

- `--interface`: interface index or name substring
- `--channels`: comma-separated zero-based input channels
- `--block-words`: frames captured per callback block
- `--host` and `--port`: local HTTP bind address
- `--no-browser`: print the URL without opening a browser
