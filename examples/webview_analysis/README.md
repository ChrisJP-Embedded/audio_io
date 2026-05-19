# Webview Analysis

Show selected input channels as live analysis views in a compact webview.

```powershell
poetry run audio-io-webview-analysis --interface 0 --channels 0
```

As a copied app template:

```powershell
poetry install
poetry run run-example --interface 0 --channels 0
```

Or run `.\setup.ps1` on Windows PowerShell / `./setup.sh` on macOS or Linux.
The local `.vscode/tasks.json` includes clean, install, and run tasks for the
copied app.

The example starts a local HTTP server at `http://127.0.0.1:8765/`, opens a
compact fixed-size pywebview window, and draws a rolling waveform with live FFT
bars below it. If pywebview is unavailable, it falls back to opening the local
URL in your browser.

Useful options:

- `--interface`: interface index or name substring
- `--channels`: comma-separated zero-based input channels
- `--block-words`: frames captured per callback block
- `--host` and `--port`: local HTTP bind address
- `--max-points`: maximum samples sent to the display per channel
- `--no-browser`: print the URL without opening a webview or browser
