# List Devices

List audio interfaces visible to the current backend.

```powershell
poetry run audio-io-list-devices
```

As a copied app template:

```powershell
poetry install
poetry run run-example
```

Or run `.\setup.ps1` on Windows PowerShell / `./setup.sh` on macOS or Linux.
The local `.vscode/tasks.json` includes clean, install, and run tasks for the
copied app.

Use the printed interface index or a name substring with the other examples.

Example output:

```text
 0: Built-in Audio in=2 out=2 default_sr=48000
 2: Focusrite USB in=2 out=2 default_sr=48000
```
