"""Measure input level in dBFS from an audio input device in a webview GUI."""

from __future__ import annotations

import argparse
import base64
import math
import threading
import time
from collections.abc import Sequence
from pathlib import Path

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


ASSET_DIR = Path(__file__).resolve().parent / "assets"


def _asset_text(name: str) -> str:
    return (ASSET_DIR / name).read_text(encoding="utf-8")


def build_html_page() -> str:
    uplot_css = _asset_text("uPlot.min.css")
    uplot_js = _asset_text("uPlot.iife.min.js")
    page = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>audio-io input meter</title>
  <style>__UPLOT_CSS__</style>
  <script>__UPLOT_JS__</script>
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
      gap: 1rem;
    }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem 1rem;
      align-items: end;
      padding: 0.9rem;
      border: 1px solid #2e363b;
      background: #171c1f;
    }
    label {
      display: grid;
      gap: 0.25rem;
      color: #aeb8bc;
      font-size: 0.78rem;
    }
    select,
    input[type="range"] {
      accent-color: #78d18f;
    }
    select {
      background: #22292d;
      color: #f4f0e8;
      border: 1px solid #3a454b;
      padding: 0.35rem 0.45rem;
      min-width: 7rem;
    }
    input[type="range"] {
      width: 10rem;
    }
    .readout {
      color: #f4f0e8;
      font-variant-numeric: tabular-nums;
    }
    .panel {
      border: 1px solid #2e363b;
      background: #111416;
      min-width: 0;
    }
    .panel-title {
      padding: 0.55rem 0.75rem;
      border-bottom: 1px solid #2e363b;
      color: #cbd2d6;
      font-size: 0.82rem;
      display: flex;
      justify-content: space-between;
      gap: 1rem;
    }
    .panel-heading {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex-wrap: wrap;
    }
    .chart-controls {
      display: flex;
      align-items: end;
      gap: 0.75rem;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .chart-controls label {
      min-width: 6.5rem;
    }
    .chart-controls input[type="range"] {
      width: 7.5rem;
    }
    #waveformChart,
    #fftChart {
      height: 230px;
      min-width: 0;
    }
    #fftChart {
      height: 180px;
    }
    .uplot {
      background: #0d1012;
      color: #aeb8bc;
      font-family: Inter, Segoe UI, system-ui, sans-serif;
    }
    .u-axis,
    .u-legend {
      color: #aeb8bc;
    }
    .u-legend {
      font-size: 0.78rem;
      background: #111416;
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
    <div class="toolbar">
      <label>
        Meter gain <span class="readout" id="gainReadout">0 dB</span>
        <input id="meterGain" type="range" min="-24" max="24" value="0" step="1">
      </label>
      <label>
        Refresh <span class="readout" id="refreshReadout">30 Hz</span>
        <input id="refreshHz" type="range" min="10" max="40" value="30" step="5">
      </label>
    </div>
    <div id="meters"></div>
    <div class="ticks"><span>-60</span><span>-45</span><span>-30</span><span>-15</span><span>0 dBFS</span></div>
    <section class="panel">
      <div class="panel-title">
        <div class="panel-heading">
          <span>Waveform</span>
          <span id="waveformMeta">waiting...</span>
        </div>
        <div class="chart-controls">
          <label>
            X window
            <select id="timeWindow">
              <option value="0.005">5 ms</option>
              <option value="0.01">10 ms</option>
              <option value="0.02">20 ms</option>
              <option value="0.05">50 ms</option>
              <option value="0.1">100 ms</option>
              <option value="0.25" selected>250 ms</option>
              <option value="1">1 s</option>
              <option value="5">5 s</option>
            </select>
          </label>
          <label>
            Y scale <span class="readout" id="waveGainReadout">x1</span>
            <input id="waveGain" type="range" min="0" max="7" value="0" step="1">
          </label>
        </div>
      </div>
      <div id="waveformChart"></div>
    </section>
    <section class="panel">
      <div class="panel-title"><span>FFT</span><span id="fftMeta">waiting...</span></div>
      <div id="fftChart"></div>
    </section>
  </main>
  <script>
    const meters = document.querySelector("#meters");
    const meta = document.querySelector("#meta");
    const waveformMeta = document.querySelector("#waveformMeta");
    const fftMeta = document.querySelector("#fftMeta");
    const timeWindow = document.querySelector("#timeWindow");
    const waveGain = document.querySelector("#waveGain");
    const meterGain = document.querySelector("#meterGain");
    const refreshHz = document.querySelector("#refreshHz");
    const waveGainReadout = document.querySelector("#waveGainReadout");
    const gainReadout = document.querySelector("#gainReadout");
    const refreshReadout = document.querySelector("#refreshReadout");
    const display = new Map();
    const colors = ["#78d18f", "#f5b971", "#70b8ff", "#ef7d91", "#d9a8ff", "#f4e06d"];
    let waveformChart = null;
    let fftChart = null;
    let timerId = null;

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

    function chartSize(element, fallbackHeight) {
      const rect = element.getBoundingClientRect();
      return {
        width: Math.max(320, Math.floor(rect.width || 720)),
        height: Math.max(160, Math.floor(rect.height || fallbackHeight)),
      };
    }

    function ensureCharts(channels) {
      const waveformElement = document.querySelector("#waveformChart");
      const fftElement = document.querySelector("#fftChart");
      if (!waveformChart) {
        const size = chartSize(waveformElement, 230);
        waveformChart = new uPlot({
          width: size.width,
          height: size.height,
          cursor: { drag: { x: true, y: false } },
          scales: { x: { time: false }, y: { range: [-1, 1] } },
          axes: [
            { label: "ms", stroke: "#8f989e", grid: { stroke: "#263037", width: 1 } },
            { label: "FS", stroke: "#8f989e", grid: { stroke: "#263037", width: 1 } },
          ],
          series: [
            {},
            ...channels.map((channel, index) => ({
              label: `ch ${channel}`,
              stroke: colors[index % colors.length],
              width: 2,
            })),
          ],
        }, [[]], waveformElement);
      }
      if (!fftChart) {
        const size = chartSize(fftElement, 180);
        fftChart = new uPlot({
          width: size.width,
          height: size.height,
          cursor: { drag: { x: true, y: false } },
          scales: { x: { time: false }, y: { range: [-120, 0] } },
          axes: [
            { label: "Hz", stroke: "#8f989e", grid: { stroke: "#263037", width: 1 } },
            { label: "dBFS", stroke: "#8f989e", grid: { stroke: "#263037", width: 1 } },
          ],
          series: [
            {},
            ...channels.map((channel, index) => ({
              label: `ch ${channel}`,
              stroke: colors[index % colors.length],
              width: 1,
              fill: `${colors[index % colors.length]}33`,
            })),
          ],
        }, [[]], fftElement);
      }
    }

    function resizeCharts() {
      if (waveformChart) {
        waveformChart.setSize(chartSize(document.querySelector("#waveformChart"), 230));
      }
      if (fftChart) {
        fftChart.setSize(chartSize(document.querySelector("#fftChart"), 180));
      }
    }

    function decodeSeries(encoded) {
      if (!encoded) return [];
      const raw = atob(encoded);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
      return Array.from(new Float32Array(bytes.buffer));
    }

    function waveformScale() {
      return 2 ** Number(waveGain.value);
    }

    function waveformYRange() {
      return 1 / waveformScale();
    }

    function render(data) {
      ensureRows(data.channels || []);
      ensureCharts(data.channels || []);
      const gain = Number(meterGain.value);
      (data.channels || []).forEach((channel, index) => {
        const key = String(channel);
        const next = (data.rms_dbfs?.[index] ?? -120) + gain;
        const previous = display.get(key) ?? next;
        const smoothed = previous * 0.72 + next * 0.28;
        display.set(key, smoothed);
        document.querySelector(`[data-fill="${key}"]`).style.width = `${percent(smoothed)}%`;
        document.querySelector(`[data-value="${key}"]`).textContent = `${smoothed.toFixed(1)} dBFS`;
      });
      const waveformX = decodeSeries(data.waveform?.x);
      const scale = waveformScale();
      const yRange = waveformYRange();
      waveformChart.setScale("y", { min: -yRange, max: yRange });
      const waveformData = [waveformX, ...(data.waveform?.channels || []).map(decodeSeries)];
      waveformChart.setData(waveformData);

      const fftX = decodeSeries(data.fft?.x);
      const fftData = [fftX, ...(data.fft?.channels || []).map(decodeSeries)];
      fftChart.setData(fftData);

      meta.textContent = `${data.frames} frames at ${data.sample_rate} Hz`;
      waveformMeta.textContent = `${Number(timeWindow.value) * 1000} ms, y +/-${yRange.toPrecision(3)} FS, x${scale}`;
      fftMeta.textContent = `${data.fft?.bin_count || 0} bins`;
    }

    async function refresh() {
      try {
        const data = await window.pywebview.api.snapshot(
          Number(timeWindow.value),
          Math.max(300, Math.floor(document.querySelector("#waveformChart").clientWidth || 720)),
        );
        render(data);
      } catch (error) {
        meta.textContent = "meter unavailable";
      }
    }

    function updateControls() {
      const gain = Number(meterGain.value);
      waveGainReadout.textContent = `x${waveformScale()}`;
      gainReadout.textContent = `${gain >= 0 ? "+" : ""}${gain} dB`;
      refreshReadout.textContent = `${refreshHz.value} Hz`;
      if (timerId) clearInterval(timerId);
      timerId = setInterval(refresh, 1000 / Number(refreshHz.value));
      refresh();
    }

    window.addEventListener("resize", resizeCharts);
    waveGain.addEventListener("input", updateControls);
    meterGain.addEventListener("input", updateControls);
    refreshHz.addEventListener("input", updateControls);
    timeWindow.addEventListener("change", updateControls);
    updateControls();
    refresh();
  </script>
</body>
</html>
"""
    return page.replace("__UPLOT_CSS__", uplot_css).replace("__UPLOT_JS__", uplot_js)


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


def _encode_float32(values: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(values, dtype=np.float32)
    return base64.b64encode(contiguous.tobytes()).decode("ascii")


def _decimate_for_display(block: np.ndarray, max_points: int) -> np.ndarray:
    if len(block) <= max_points:
        return block
    indices = np.linspace(0, len(block) - 1, max_points, dtype=np.int64)
    return block[indices]


def _fft_dbfs(block: np.ndarray, *, sample_rate: int, max_bins: int, floor_db: float = -120.0) -> tuple[np.ndarray, np.ndarray]:
    if len(block) < 8:
        frequencies = np.linspace(0, sample_rate / 2, max_bins, dtype=np.float32)
        return frequencies, np.full((max_bins, block.shape[1]), floor_db, dtype=np.float32)

    window = np.hanning(len(block)).astype(np.float32)
    coherent_gain = max(float(np.mean(window)), 1e-12)
    spectrum = np.fft.rfft(block.astype(np.float32) * window[:, np.newaxis], axis=0)
    peak = (2.0 * np.abs(spectrum) / (len(block) * coherent_gain)).astype(np.float32)
    peak[0] *= 0.5
    with np.errstate(divide="ignore"):
        levels = 20.0 * np.log10(np.maximum(peak, 1e-12))
    frequencies = np.fft.rfftfreq(len(block), d=1.0 / sample_rate).astype(np.float32)

    if len(frequencies) > max_bins:
        edges = np.linspace(0, len(frequencies), max_bins + 1, dtype=np.int64)
        bucket_freqs = np.zeros(max_bins, dtype=np.float32)
        bucket_levels = np.full((max_bins, levels.shape[1]), floor_db, dtype=np.float32)
        for index in range(max_bins):
            start, stop = edges[index], edges[index + 1]
            if stop <= start:
                stop = min(start + 1, len(frequencies))
            bucket_freqs[index] = float(np.mean(frequencies[start:stop]))
            bucket_levels[index] = np.max(levels[start:stop], axis=0)
        frequencies = bucket_freqs
        levels = bucket_levels
    return frequencies.astype(np.float32), np.maximum(levels, floor_db).astype(np.float32)


class LevelMeterState:
    """Thread-safe handoff from audio callback blocks to the webview UI."""

    def __init__(self, *, channels: tuple[int, ...], sample_rate: int, history_seconds: float, fft_size: int) -> None:
        self.channels = channels
        self.sample_rate = sample_rate
        self.history_seconds = history_seconds
        self.fft_size = fft_size
        self._lock = threading.Lock()
        self._levels = np.full(len(channels), -120.0, dtype=np.float32)
        self._history = np.zeros((max(1, int(sample_rate * history_seconds)), len(channels)), dtype=np.float32)
        self._write_index = 0
        self._sample_count = 0
        self._frames = 0
        self._sequence = 0

    def update(self, block: np.ndarray, info: object) -> None:
        levels = rms_dbfs(block)
        input_block = block.astype(np.float32, copy=False)
        with self._lock:
            self._levels = levels.astype(np.float32)
            frames = min(len(input_block), len(self._history))
            if frames:
                tail = input_block[-frames:]
                first = min(frames, len(self._history) - self._write_index)
                self._history[self._write_index : self._write_index + first] = tail[:first]
                remaining = frames - first
                if remaining:
                    self._history[:remaining] = tail[first:]
                self._write_index = (self._write_index + frames) % len(self._history)
                self._sample_count = min(self._sample_count + frames, len(self._history))
            self._frames = int(len(block))
            self._sequence += 1

    def _history_snapshot(self) -> np.ndarray:
        if self._sample_count == 0:
            return np.zeros((0, len(self.channels)), dtype=np.float32)
        start = (self._write_index - self._sample_count) % len(self._history)
        if start + self._sample_count <= len(self._history):
            return np.array(self._history[start : start + self._sample_count], copy=True)
        return np.concatenate((self._history[start:], self._history[: (start + self._sample_count) % len(self._history)]))

    def snapshot(self, window_seconds: float = 0.25, display_points: int = 720) -> dict[str, object]:
        with self._lock:
            levels = self._levels.astype(float).tolist()
            frames = self._frames
            sequence = self._sequence
            history = self._history_snapshot()

        requested_frames = max(1, min(len(history), int(window_seconds * self.sample_rate)))
        visible = history[-requested_frames:] if requested_frames else history
        waveform = _decimate_for_display(visible, max(32, int(display_points)))
        if len(waveform):
            x_ms = np.linspace(-len(visible) / self.sample_rate * 1000.0, 0.0, len(waveform), dtype=np.float32)
        else:
            x_ms = np.zeros(0, dtype=np.float32)

        fft_source = history[-min(len(history), self.fft_size) :]
        frequencies, fft_levels = _fft_dbfs(
            fft_source if len(fft_source) else np.zeros((8, len(self.channels)), dtype=np.float32),
            sample_rate=self.sample_rate,
            max_bins=160,
        )
        return {
            "sequence": sequence,
            "sample_rate": self.sample_rate,
            "frames": frames,
            "channels": list(self.channels),
            "rms_dbfs": levels,
            "waveform": {
                "x": _encode_float32(x_ms),
                "channels": [_encode_float32(waveform[:, index] if len(waveform) else np.zeros(0)) for index in range(len(self.channels))],
            },
            "fft": {
                "x": _encode_float32(frequencies),
                "channels": [_encode_float32(fft_levels[:, index]) for index in range(len(self.channels))],
                "bin_count": int(len(frequencies)),
            },
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show input RMS level in dBFS.")
    parser.add_argument("--interface", default=None, help="Interface name substring or numeric device index.")
    parser.add_argument("--device", default=None, help="Deprecated alias for --interface.")
    parser.add_argument("--channels", default="0", help="Comma-separated zero-based input channels.")
    parser.add_argument("--sample-rate", type=int, default=48_000, help="Sample rate in Hz.")
    parser.add_argument("--block-words", type=int, default=256, help="Frames per callback block.")
    parser.add_argument("--history-seconds", type=float, default=5.0, help="Rolling waveform history in seconds.")
    parser.add_argument("--fft-size", type=int, default=4096, help="Samples used for each FFT snapshot.")
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

    state = LevelMeterState(
        channels=input_channels,
        sample_rate=args.sample_rate,
        history_seconds=args.history_seconds,
        fft_size=args.fft_size,
    )
    try:
        with AudioIOSession(config, input_callback=state.update):
            try:
                import webview
            except ImportError as exc:
                raise RuntimeError("pywebview is required for the GUI input meter. Run poetry install.") from exc

            window = webview.create_window(
                "audio-io input meter",
                html=build_html_page(),
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
