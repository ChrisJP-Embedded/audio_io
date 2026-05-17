"""Measure input level in dBFS from an audio input device in a webview GUI."""

from __future__ import annotations

import argparse
import math
import threading
import time
from collections.abc import Sequence

import numpy as np

try:
    from _example_bootstrap import add_src_to_path, print_config_error, print_runtime_error
except ImportError:
    try:
        from examples._example_bootstrap import add_src_to_path, print_config_error, print_runtime_error
    except ImportError:
        import sys

        def add_src_to_path() -> None:
            return

        def print_config_error(exc: Exception) -> int:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        def print_runtime_error(exc: RuntimeError) -> int:
            print(f"error: {exc}", file=sys.stderr)
            return 1

add_src_to_path()

from audio_io import AudioIOConfig, AudioIOConfigError, AudioIOSession  # noqa: E402


HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>audio-io input meter</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: Inter, Segoe UI, system-ui, sans-serif;
      background: #111416;
      color: #f4f0e8;
    }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    header {
      padding: 1rem 1.25rem;
      border-bottom: 1px solid #2e363b;
      background: #1b2023;
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      align-items: center;
    }
    h1 {
      margin: 0;
      font-size: 1rem;
      font-weight: 650;
      letter-spacing: 0;
    }
    #meta {
      color: #aeb8bc;
      font-size: 0.85rem;
      text-align: right;
      font-variant-numeric: tabular-nums;
    }
    main {
      padding: 1rem;
      display: grid;
      align-content: start;
      gap: 0.75rem;
    }
    .channel {
      display: grid;
      grid-template-columns: 4.5rem 1fr 7rem;
      gap: 0.75rem;
      align-items: center;
      min-height: 3rem;
    }
    .label {
      color: #cbd2d6;
      font-size: 0.9rem;
    }
    .value {
      text-align: right;
      font-variant-numeric: tabular-nums;
      font-size: 1rem;
    }
    .bar {
      height: 1.2rem;
      background: #242b2f;
      border: 1px solid #323c42;
      position: relative;
      overflow: hidden;
    }
    .fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #59c378, #f4cf5d 72%, #ef6f72);
      transition: width 80ms linear;
    }
    .ticks {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      color: #7e8b91;
      font-size: 0.72rem;
      padding: 0 7.6rem 0 5.25rem;
      margin-top: -0.25rem;
    }
    .ticks span:not(:first-child) {
      text-align: center;
    }
    .ticks span:last-child {
      text-align: right;
    }
  </style>
</head>
<body>
  <header>
    <h1>audio-io input meter</h1>
    <div id="meta">waiting for audio...</div>
  </header>
  <main>
    <div id="meters"></div>
    <div class="ticks"><span>-60</span><span>-45</span><span>-30</span><span>-15</span><span>0 dBFS</span></div>
  </main>
  <script>
    const meters = document.querySelector("#meters");
    const meta = document.querySelector("#meta");
    const display = new Map();

    function percent(db) {
      return Math.max(0, Math.min(100, ((db + 60) / 60) * 100));
    }

    function ensureRows(channels) {
      const wanted = channels.map(String);
      for (const key of [...display.keys()]) {
        if (!wanted.includes(key)) {
          display.delete(key);
        }
      }
      meters.innerHTML = "";
      for (const channel of channels) {
        const key = String(channel);
        const level = display.get(key) ?? -120;
        display.set(key, level);
        const row = document.createElement("div");
        row.className = "channel";
        row.innerHTML = `
          <div class="label">ch ${channel}</div>
          <div class="bar"><div class="fill" data-fill="${key}"></div></div>
          <div class="value" data-value="${key}">-120.0 dBFS</div>
        `;
        meters.appendChild(row);
      }
    }

    function render(data) {
      ensureRows(data.channels || []);
      (data.channels || []).forEach((channel, index) => {
        const key = String(channel);
        const next = data.rms_dbfs?.[index] ?? -120;
        const previous = display.get(key) ?? next;
        const smoothed = previous * 0.72 + next * 0.28;
        display.set(key, smoothed);
        document.querySelector(`[data-fill="${key}"]`).style.width = `${percent(smoothed)}%`;
        document.querySelector(`[data-value="${key}"]`).textContent = `${smoothed.toFixed(1)} dBFS`;
      });
      meta.textContent = `${data.frames} frames at ${data.sample_rate} Hz`;
    }

    async function refresh() {
      try {
        const data = await window.pywebview.api.snapshot();
        render(data);
      } catch (error) {
        meta.textContent = "meter unavailable";
      }
    }

    setInterval(refresh, 50);
    refresh();
  </script>
</body>
</html>
"""


def parse_channels(value: str) -> tuple[int, ...]:
    """Parse comma-separated zero-based channel indices from the CLI."""

    if not value.strip():
        return ()
    return tuple(int(part.strip()) for part in value.split(","))


def rms_dbfs(block: np.ndarray, *, floor_db: float = -120.0) -> np.ndarray:
    """Return per-channel RMS level in dBFS for a `(frames, channels)` block."""

    if block.ndim != 2:
        raise ValueError("block must be shaped as (frames, channels)")
    rms = np.sqrt(np.mean(np.square(block.astype(np.float32)), axis=0))
    with np.errstate(divide="ignore"):
        db = 20.0 * np.log10(rms)
    return np.maximum(db, floor_db)


class LevelMeterState:
    """Thread-safe handoff from audio callback blocks to the webview UI."""

    def __init__(self, *, channels: tuple[int, ...], sample_rate: int) -> None:
        self.channels = channels
        self.sample_rate = sample_rate
        self._lock = threading.Lock()
        self._levels = np.full(len(channels), -120.0, dtype=np.float32)
        self._frames = 0
        self._sequence = 0

    def update(self, block: np.ndarray, info: object) -> None:
        levels = rms_dbfs(block)
        with self._lock:
            self._levels = levels.astype(np.float32)
            self._frames = int(len(block))
            self._sequence += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            levels = self._levels.astype(float).tolist()
            frames = self._frames
            sequence = self._sequence
        return {
            "sequence": sequence,
            "sample_rate": self.sample_rate,
            "frames": frames,
            "channels": list(self.channels),
            "rms_dbfs": levels,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show input RMS level in dBFS.")
    parser.add_argument("--interface", default=None, help="Interface name substring or numeric device index.")
    parser.add_argument("--device", default=None, help="Deprecated alias for --interface.")
    parser.add_argument("--channels", default="0", help="Comma-separated zero-based input channels.")
    parser.add_argument("--sample-rate", type=int, default=48_000, help="Sample rate in Hz.")
    parser.add_argument("--block-words", type=int, default=256, help="Frames per callback block.")
    parser.add_argument("--seconds", type=float, default=None, help="Run duration. Omit to run until Ctrl+C.")
    parser.add_argument("--debug", action="store_true", help="Enable pywebview debug mode.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_channels = parse_channels(args.channels)
    interface_arg = args.interface if args.interface is not None else args.device
    if interface_arg is None:
        build_parser().error("--interface is required")
    interface = int(interface_arg) if interface_arg and interface_arg.isdigit() else interface_arg
    config = AudioIOConfig(
        interface=interface,
        input_channels=input_channels,
        sample_rate=args.sample_rate,
        block_words=args.block_words,
    )

    state = LevelMeterState(channels=input_channels, sample_rate=args.sample_rate)
    try:
        with AudioIOSession(config, input_callback=state.update):
            try:
                import webview
            except ImportError as exc:
                raise RuntimeError("pywebview is required for the GUI input meter. Run poetry install.") from exc

            window = webview.create_window(
                "audio-io input meter",
                html=HTML_PAGE,
                js_api=state,
                width=560,
                height=420,
                min_size=(420, 280),
            )
            if args.seconds is not None:
                threading.Timer(args.seconds, window.destroy).start()
            webview.start(debug=args.debug)
    except AudioIOConfigError as exc:
        return print_config_error(exc)
    except RuntimeError as exc:
        return print_runtime_error(exc)
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
