"""Display live input analysis views in a local web page."""

from __future__ import annotations

import argparse
import json
import threading
import time
import webbrowser
from collections.abc import Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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

from audio_io import AudioIOConfig, AudioIOConfigError, AudioIOSession, BlockInfo  # noqa: E402


def parse_channels(value: str) -> tuple[int, ...]:
    """Parse comma-separated zero-based channel indices from the CLI."""

    if not value.strip():
        return ()
    try:
        return tuple(int(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise ValueError(f"channels must be comma-separated integers, got {value!r}") from exc


def rms_dbfs(block: np.ndarray, *, floor_db: float = -120.0) -> np.ndarray:
    """Return per-channel RMS level in dBFS for a `(frames, channels)` block."""

    if block.ndim != 2:
        raise ValueError("block must be shaped as (frames, channels)")
    rms = np.sqrt(np.mean(np.square(block.astype(np.float32)), axis=0))
    with np.errstate(divide="ignore"):
        db = 20.0 * np.log10(rms)
    return np.maximum(db, floor_db)


def fft_dbfs(block: np.ndarray, *, bins: int = 48, floor_db: float = -120.0) -> np.ndarray:
    """Return coarse per-channel FFT magnitudes in dBFS."""

    if block.ndim != 2:
        raise ValueError("block must be shaped as (frames, channels)")
    if len(block) < 2:
        return np.full((block.shape[1], bins), floor_db, dtype=np.float32)

    window = np.hanning(len(block)).astype(np.float32)
    windowed = block.astype(np.float32) * window[:, np.newaxis]
    spectrum = np.abs(np.fft.rfft(windowed, axis=0))
    scale = max(float(window.sum()) / 2.0, 1.0)
    with np.errstate(divide="ignore"):
        db = 20.0 * np.log10(spectrum / scale)
    db = np.minimum(np.maximum(db, floor_db), 0.0)

    bands = np.array_split(db[1:], bins)
    values = [np.max(band, axis=0) if len(band) else np.full(block.shape[1], floor_db) for band in bands]
    return np.stack(values, axis=1).astype(np.float32)


HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>audio-io webview analysis</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: Inter, Segoe UI, system-ui, sans-serif;
      background: #141719;
      color: #f4f0e8;
    }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      overflow: hidden;
    }
    .app {
      width: min(150mm, calc(100vw - 1rem));
      height: min(100mm, calc(100vh - 1rem));
      display: grid;
      grid-template-rows: auto 1fr;
      border: 1px solid #30363a;
      background: #101315;
    }
    header {
      display: flex;
      gap: 0.6rem;
      align-items: center;
      justify-content: space-between;
      padding: 0.55rem 0.7rem;
      border-bottom: 1px solid #30363a;
      background: #1c2023;
    }
    h1 {
      margin: 0;
      font-size: 1rem;
      font-weight: 650;
      letter-spacing: 0;
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 0.45rem 0.65rem;
      align-items: center;
      justify-content: flex-end;
    }
    label {
      display: grid;
      gap: 0.2rem;
      color: #c9c0b4;
      font-size: 0.78rem;
    }
    input[type="range"] {
      width: 6.5rem;
      accent-color: #7bd88f;
    }
    .readout {
      color: #f4f0e8;
      font-variant-numeric: tabular-nums;
    }
    #stats {
      color: #c9c0b4;
      font-size: 0.78rem;
      text-align: right;
    }
    main {
      min-height: 0;
      padding: 0.6rem;
      display: grid;
      grid-template-rows: minmax(0, 1.5fr) minmax(0, 1fr);
      gap: 0.5rem;
    }
    canvas {
      width: 100%;
      height: 100%;
      min-height: 0;
      display: block;
      border: 1px solid #30363a;
      background: #0f1113;
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <h1>audio-io webview analysis</h1>
      <div class="controls">
        <label>
          Time <span class="readout" id="timeReadout">250 ms</span>
          <input id="timeScale" type="range" min="50" max="5000" value="250" step="50">
        </label>
        <label>
          Amplitude <span class="readout" id="ampReadout">1.0x</span>
          <input id="amplitudeScale" type="range" min="0.25" max="8" value="1" step="0.25">
        </label>
        <div id="stats">waiting for audio...</div>
      </div>
    </header>
    <main>
      <canvas id="waveform"></canvas>
      <canvas id="fft"></canvas>
    </main>
  </div>
  <script>
    const waveformCanvas = document.querySelector("#waveform");
    const waveformCtx = waveformCanvas.getContext("2d");
    const fftCanvas = document.querySelector("#fft");
    const fftCtx = fftCanvas.getContext("2d");
    const stats = document.querySelector("#stats");
    const timeScale = document.querySelector("#timeScale");
    const amplitudeScale = document.querySelector("#amplitudeScale");
    const timeReadout = document.querySelector("#timeReadout");
    const ampReadout = document.querySelector("#ampReadout");
    const colors = ["#7bd88f", "#f5b971", "#70b8ff", "#ef7d91", "#d9a8ff", "#f4e06d"];
    const history = [];
    let lastSequence = -1;
    let latestData = null;

    function resizeCanvas(targetCanvas, targetCtx) {
      const rect = targetCanvas.getBoundingClientRect();
      const scale = window.devicePixelRatio || 1;
      const width = Math.max(1, Math.floor(rect.width * scale));
      const height = Math.max(1, Math.floor(rect.height * scale));
      if (targetCanvas.width !== width || targetCanvas.height !== height) {
        targetCanvas.width = width;
        targetCanvas.height = height;
      }
      targetCtx.setTransform(scale, 0, 0, scale, 0, 0);
      return { width: rect.width, height: rect.height };
    }

    function visibleSeconds() {
      return Number(timeScale.value) / 1000;
    }

    function amplitudeGain() {
      return Number(amplitudeScale.value);
    }

    function updateReadouts() {
      const ms = Number(timeScale.value);
      timeReadout.textContent = ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(2)} s`;
      ampReadout.textContent = `${amplitudeGain().toFixed(2).replace(/\\.00$/, "")}x`;
    }

    function appendSamples(data) {
      if (!data.samples?.length || data.sequence === lastSequence) {
        return;
      }
      lastSequence = data.sequence;
      latestData = data;

      const sampleRate = data.display_sample_rate || data.sample_rate || 48000;
      const channelCount = data.samples.length;
      const sampleCount = data.samples[0].length;
      let nextTime = history.length ? history[history.length - 1].time + 1 / sampleRate : 0;
      for (let sampleIndex = 0; sampleIndex < sampleCount; sampleIndex += 1) {
        const values = [];
        for (let channel = 0; channel < channelCount; channel += 1) {
          values.push(data.samples[channel][sampleIndex] ?? 0);
        }
        history.push({ time: nextTime, values });
        nextTime += 1 / sampleRate;
      }

      const keepAfter = nextTime - 10;
      while (history.length && history[0].time < keepAfter) {
        history.shift();
      }
    }

    function drawGrid(width, height, lanes, seconds) {
      const ctx = waveformCtx;
      ctx.strokeStyle = "#252b2f";
      ctx.lineWidth = 1;
      for (let i = 1; i < lanes; i += 1) {
        const y = (height / lanes) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
      for (let i = 0; i <= 5; i += 1) {
        const x = (width / 5) * i;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      ctx.fillStyle = "#8f989e";
      ctx.font = "12px Segoe UI, system-ui, sans-serif";
      ctx.fillText(`-${seconds.toFixed(seconds < 1 ? 2 : 1)} s`, 12, height - 12);
      ctx.fillText("now", width - 36, height - 12);
    }

    function drawChart() {
      const { width, height } = resizeCanvas(waveformCanvas, waveformCtx);
      const ctx = waveformCtx;
      const channels = latestData?.channels || [];
      const rms = latestData?.rms_dbfs || [];
      const lanes = Math.max(1, channels.length);
      const seconds = visibleSeconds();
      const gain = amplitudeGain();
      ctx.clearRect(0, 0, width, height);
      drawGrid(width, height, lanes, seconds);

      if (!history.length || !channels.length) {
        ctx.fillStyle = "#8f989e";
        ctx.font = "14px Segoe UI, system-ui, sans-serif";
        ctx.fillText("waiting for input blocks", 18, 32);
        return;
      }

      const now = history[history.length - 1].time;
      const start = now - seconds;
      const visible = history.filter((sample) => sample.time >= start);

      channels.forEach((channelName, index) => {
        const laneTop = (height / lanes) * index;
        const laneHeight = height / lanes;
        const center = laneTop + laneHeight / 2;
        const yScale = laneHeight * 0.42;
        ctx.strokeStyle = colors[index % colors.length];
        ctx.lineWidth = 2;
        ctx.beginPath();
        visible.forEach((sample, sampleIndex) => {
          const x = ((sample.time - start) / seconds) * width;
          const scaled = Math.max(-1, Math.min(1, (sample.values[index] ?? 0) * gain));
          const y = center - scaled * yScale;
          if (sampleIndex === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        });
        ctx.stroke();

        ctx.fillStyle = "#c9c0b4";
        ctx.font = "13px Segoe UI, system-ui, sans-serif";
        const level = rms[index]?.toFixed(1) ?? "-inf";
        ctx.fillText(`ch ${channelName}  ${level} dBFS`, 12, laneTop + 24);
      });
    }

    function drawFftChart() {
      const { width, height } = resizeCanvas(fftCanvas, fftCtx);
      const ctx = fftCtx;
      const channels = latestData?.channels || [];
      const fft = latestData?.fft_dbfs || [];
      const binCount = fft[0]?.length || 0;
      ctx.clearRect(0, 0, width, height);

      ctx.strokeStyle = "#252b2f";
      ctx.lineWidth = 1;
      for (let i = 1; i <= 3; i += 1) {
        const y = (height / 4) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
      ctx.fillStyle = "#8f989e";
      ctx.font = "12px Segoe UI, system-ui, sans-serif";
      ctx.fillText("FFT", 10, 18);
      ctx.fillText("20 kHz", Math.max(10, width - 48), height - 10);

      if (!channels.length || !binCount) {
        ctx.fillText("waiting for spectrum", 48, 18);
        return;
      }

      const gap = 1.5;
      const groupWidth = width / binCount;
      const barWidth = Math.max(1, (groupWidth - gap) / channels.length);
      channels.forEach((channelName, channelIndex) => {
        const values = fft[channelIndex] || [];
        ctx.fillStyle = colors[channelIndex % colors.length];
        values.forEach((db, index) => {
          const normalized = Math.max(0, Math.min(1, (db + 90) / 90));
          const barHeight = normalized * (height - 28);
          const x = index * groupWidth + channelIndex * barWidth;
          const y = height - barHeight - 1;
          ctx.globalAlpha = 0.86;
          ctx.fillRect(x, y, Math.max(1, barWidth - gap), barHeight);
        });
      });
      ctx.globalAlpha = 1;
    }

    async function refresh() {
      try {
        const response = await fetch("/waveform.json", { cache: "no-store" });
        const data = await response.json();
        appendSamples(data);
        drawChart();
        drawFftChart();
        stats.textContent = `${data.frames} frames at ${data.sample_rate} Hz`;
      } catch (error) {
        stats.textContent = "server unavailable";
      }
    }

    function redraw() {
      updateReadouts();
      drawChart();
      drawFftChart();
    }

    window.addEventListener("resize", redraw);
    timeScale.addEventListener("input", redraw);
    amplitudeScale.addEventListener("input", redraw);
    updateReadouts();
    setInterval(refresh, 50);
    refresh();
  </script>
</body>
</html>
"""


class WaveformState:
    """Thread-safe handoff from the audio callback to the HTTP request thread."""

    def __init__(self, *, channels: tuple[int, ...], sample_rate: int, max_points: int) -> None:
        self.channels = channels
        self.sample_rate = sample_rate
        self.max_points = max_points
        self._lock = threading.Lock()
        self._block: np.ndarray | None = None
        self._sequence = 0

    def update(self, block: np.ndarray, info: BlockInfo) -> None:
        with self._lock:
            self._block = np.array(block, copy=True)
            self._sequence += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            block = None if self._block is None else np.array(self._block, copy=True)
            sequence = self._sequence

        if block is None:
            return {
                "sequence": sequence,
                "sample_rate": self.sample_rate,
                "display_sample_rate": self.sample_rate,
                "channels": list(self.channels),
                "frames": 0,
                "samples": [],
                "rms_dbfs": [],
                "fft_dbfs": [],
            }

        if len(block) > self.max_points:
            indices = np.linspace(0, len(block) - 1, self.max_points, dtype=np.int64)
            display_block = block[indices]
        else:
            display_block = block
        display_sample_rate = self.sample_rate * len(display_block) / len(block)

        return {
            "sequence": sequence,
            "sample_rate": self.sample_rate,
            "display_sample_rate": display_sample_rate,
            "channels": list(self.channels),
            "frames": int(len(block)),
            "samples": display_block.T.astype(float).tolist(),
            "rms_dbfs": rms_dbfs(block).astype(float).tolist(),
            "fft_dbfs": fft_dbfs(block).astype(float).tolist(),
        }


def build_handler(state: WaveformState) -> type[BaseHTTPRequestHandler]:
    class WaveformHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path in {"/", "/index.html"}:
                self._send(HTML_PAGE.encode("utf-8"), "text/html; charset=utf-8")
                return
            if self.path == "/waveform.json":
                payload = json.dumps(state.snapshot()).encode("utf-8")
                self._send(payload, "application/json")
                return
            self.send_error(404)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, body: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return WaveformHandler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show live input analysis in a compact webview.")
    parser.add_argument("--interface", default=None, help="Interface name substring or numeric device index.")
    parser.add_argument("--device", default=None, help="Deprecated alias for --interface.")
    parser.add_argument("--channels", default="0", help="Comma-separated zero-based input channels.")
    parser.add_argument("--sample-rate", type=int, default=48_000, help="Sample rate in Hz.")
    parser.add_argument("--block-words", type=int, default=1024, help="Frames per callback block.")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host for the analysis display.")
    parser.add_argument("--port", type=int, default=8765, help="HTTP port for the analysis display.")
    parser.add_argument("--max-points", type=int, default=1200, help="Maximum samples drawn per channel.")
    parser.add_argument("--seconds", type=float, default=None, help="Run duration. Omit to run until Ctrl+C.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the webview or browser automatically.")
    return parser


def wait_until_done(seconds: float | None, *, start: float) -> None:
    while seconds is None or time.monotonic() - start < seconds:
        time.sleep(0.25)


def open_display(url: str, *, seconds: float | None, start: float) -> None:
    try:
        import webview
    except ImportError:
        webbrowser.open(url)
        wait_until_done(seconds, start=start)
        return

    window = webview.create_window(
        "audio-io webview analysis",
        url=url,
        width=620,
        height=430,
        min_size=(620, 430),
        resizable=False,
    )
    if seconds is not None:
        threading.Timer(seconds, window.destroy).start()
    webview.start()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        input_channels = parse_channels(args.channels)
        interface_arg = args.interface if args.interface is not None else args.device
        if interface_arg is None:
            parser.error("--interface is required")
        interface = int(interface_arg) if interface_arg and interface_arg.isdigit() else interface_arg

        config = AudioIOConfig(
            interface=interface,
            input_channels=input_channels,
            sample_rate=args.sample_rate,
            block_words=args.block_words,
        )
        state = WaveformState(channels=input_channels, sample_rate=args.sample_rate, max_points=args.max_points)
    except ValueError as exc:
        return print_config_error(exc)
    print(config.timing_status.console_line())
    server: ThreadingHTTPServer | None = None

    try:
        start = time.monotonic()
        with AudioIOSession(config, input_callback=state.update):
            server = ThreadingHTTPServer((args.host, args.port), build_handler(state))
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            url = f"http://{args.host}:{server.server_port}/"
            server_thread.start()
            print(f"Serving webview analysis at {url}")
            if args.no_browser:
                wait_until_done(args.seconds, start=start)
            else:
                open_display(url, seconds=args.seconds, start=start)
    except AudioIOConfigError as exc:
        return print_config_error(exc)
    except OSError as exc:
        return print_config_error(exc)
    except RuntimeError as exc:
        return print_runtime_error(exc)
    except KeyboardInterrupt:
        print()
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
