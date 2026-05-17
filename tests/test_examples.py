from __future__ import annotations

import json
import tomllib
from pathlib import Path

import numpy as np
import pytest

import examples.input_level_meter.main as input_level_meter
import examples.live_waveform_web.main as live_waveform_web
import examples.loopback_sine_level_check.main as loopback_sine_level_check
import examples.sine_output.main as sine_output
from audio_io import InvalidChannelRequestError
from examples.input_level_meter.main import LevelMeterState, _decimate_for_display, _fft_dbfs, rms_dbfs
from examples.live_waveform_web.main import WaveformState
from examples.loopback_sine_level_check.main import dbfs_to_peak, estimate_sine_peak_dbfs, levels_within_tolerance
from examples.sine_output.main import SineGenerator, parse_channels


EXAMPLE_DIRS = [
    Path("examples/list_devices"),
    Path("examples/sine_output"),
    Path("examples/input_level_meter"),
    Path("examples/live_waveform_web"),
    Path("examples/loopback_sine_level_check"),
]


def test_parse_channels() -> None:
    assert parse_channels("0, 2,3") == (0, 2, 3)


@pytest.mark.parametrize("example_dir", EXAMPLE_DIRS)
def test_example_app_template_files_exist(example_dir: Path) -> None:
    assert (example_dir / "README.md").is_file()
    assert (example_dir / "pyproject.toml").is_file()
    assert (example_dir / "setup.ps1").is_file()
    assert (example_dir / "setup.sh").is_file()
    assert (example_dir / ".vscode" / "tasks.json").is_file()


@pytest.mark.parametrize("example_dir", EXAMPLE_DIRS)
def test_example_app_template_pyproject_is_valid(example_dir: Path) -> None:
    pyproject = tomllib.loads((example_dir / "pyproject.toml").read_text())

    assert pyproject["project"]["requires-python"].startswith(">=3.10")
    assert pyproject["project"]["dynamic"] == ["dependencies"]
    assert pyproject["tool"]["poetry"]["package-mode"] is False
    assert pyproject["tool"]["poetry"]["dependencies"]["audio-io"] == {
        "path": "../..",
        "develop": True,
    }
    assert pyproject["project"]["scripts"]["run-example"] == "main:main"


@pytest.mark.parametrize("example_dir", EXAMPLE_DIRS)
def test_example_vscode_tasks_include_clean_install_and_run(example_dir: Path) -> None:
    tasks = json.loads((example_dir / ".vscode" / "tasks.json").read_text())["tasks"]
    labels = {task["label"] for task in tasks}

    assert {"clean: python caches", "install: poetry env", "run: example app"} <= labels


def test_sine_generator_outputs_expected_shape_and_amplitude() -> None:
    generator = SineGenerator(frequency_hz=1000, sample_rate=48000, channels=2, amplitude=0.5)

    block = generator(frames=48, info=None)

    assert block.shape == (48, 2)
    assert block.dtype == np.float32
    assert np.max(np.abs(block)) <= 0.5
    assert block[:, 0].tolist() == block[:, 1].tolist()


def test_sine_generator_applies_initial_phase_shift() -> None:
    generator = SineGenerator(
        frequency_hz=1000,
        sample_rate=48000,
        channels=1,
        amplitude=0.5,
        phase_degrees=90,
    )

    block = generator(frames=1, info=None)

    assert block[0, 0] == np.float32(0.5)


def test_rms_dbfs_reports_full_scale_and_silence_floor() -> None:
    block = np.array([[1.0, 0.0], [-1.0, 0.0]], dtype=np.float32)

    levels = rms_dbfs(block)

    assert levels.tolist() == [0.0, -120.0]


def test_level_meter_state_snapshots_latest_levels() -> None:
    state = LevelMeterState(channels=(0, 1), sample_rate=48_000, history_seconds=1.0, fft_size=128)

    state.update(np.array([[1.0, 0.0], [-1.0, 0.0]], dtype=np.float32), info=None)
    snapshot = state.snapshot()

    assert snapshot["sequence"] == 1
    assert snapshot["sample_rate"] == 48_000
    assert snapshot["frames"] == 2
    assert snapshot["channels"] == [0, 1]
    assert snapshot["rms_dbfs"] == [0.0, -120.0]
    assert snapshot["waveform"]["x"]
    assert len(snapshot["waveform"]["channels"]) == 2
    assert snapshot["fft"]["bin_count"] > 0
    assert len(snapshot["fft"]["channels"]) == 2


def test_input_meter_html_includes_waveform_scaling_controls() -> None:
    html = input_level_meter.build_html_page()

    assert 'id="timeWindow"' in html
    assert 'value="0.005"' in html
    assert 'id="waveGain"' in html
    assert "waveformScale()" in html


def test_decimate_for_display_limits_points() -> None:
    block = np.arange(100, dtype=np.float32).reshape(50, 2)

    decimated = _decimate_for_display(block, max_points=10)

    assert decimated.shape == (10, 2)
    assert decimated[0].tolist() == [0.0, 1.0]
    assert decimated[-1].tolist() == [98.0, 99.0]


def test_fft_dbfs_reports_frequency_bins() -> None:
    sample_rate = 48_000
    frames = np.arange(4096, dtype=np.float32)
    sine = np.sin(2 * np.pi * 1000 * frames / sample_rate).astype(np.float32)
    block = sine[:, np.newaxis]

    frequencies, levels = _fft_dbfs(block, sample_rate=sample_rate, max_bins=256)

    assert frequencies.shape == (256,)
    assert levels.shape == (256, 1)
    assert float(np.max(levels)) > -6.0


def test_dbfs_to_peak_converts_negative_dbfs() -> None:
    assert np.isclose(dbfs_to_peak(-6.0), 0.5011872336272722)


def test_dbfs_to_peak_rejects_positive_dbfs() -> None:
    try:
        dbfs_to_peak(1.0)
    except ValueError as exc:
        assert "less than or equal to 0" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_estimate_sine_peak_dbfs_recovers_known_level_with_phase_offset() -> None:
    sample_rate = 48_000
    frequency = 1000.0
    expected_dbfs = -12.0
    amplitude = dbfs_to_peak(expected_dbfs)
    frames = np.arange(sample_rate, dtype=np.float64)
    sine = amplitude * np.sin(2.0 * np.pi * frequency * frames / sample_rate + np.deg2rad(37.0))
    block = np.column_stack((sine, sine * dbfs_to_peak(-6.0))).astype(np.float32)

    measured = estimate_sine_peak_dbfs(block, frequency_hz=frequency, sample_rate=sample_rate)

    assert np.allclose(measured, [expected_dbfs, expected_dbfs - 6.0], atol=0.01)


def test_levels_within_tolerance() -> None:
    measured = np.array([-12.1, -13.5, -10.9])

    passed = levels_within_tolerance(measured, expected_dbfs=-12.0, tolerance_db=1.0)

    assert passed.tolist() == [True, False, False]


def test_waveform_state_snapshots_latest_block() -> None:
    state = WaveformState(channels=(0, 1), sample_rate=48_000, max_points=2)

    state.update(np.array([[0.0, 0.5], [1.0, -1.0], [0.0, 0.25]], dtype=np.float32), info=None)
    snapshot = state.snapshot()

    assert snapshot["sequence"] == 1
    assert snapshot["frames"] == 3
    assert snapshot["channels"] == [0, 1]
    assert snapshot["display_sample_rate"] == 32_000
    assert snapshot["samples"] == [[0.0, 0.0], [0.5, 0.25]]
    assert len(snapshot["rms_dbfs"]) == 2


class RaisingSession:
    def __init__(self, config, **kwargs):
        raise InvalidChannelRequestError(
            "input channel request invalid for input channel list [2]: "
            "interface 'Output Only' has 0 input channel(s); invalid channel(s): [2]"
        )


@pytest.mark.parametrize(
    ("module", "argv"),
    [
        (
            sine_output,
            ["--interface", "Output Only", "--channels", "2", "--seconds", "0"],
        ),
        (
            input_level_meter,
            ["--interface", "Output Only", "--channels", "2", "--seconds", "0"],
        ),
        (
            loopback_sine_level_check,
            [
                "--interface",
                "Output Only",
                "--input-channels",
                "2",
                "--output-channels",
                "0,1",
                "--measure-seconds",
                "0",
            ],
        ),
        (
            live_waveform_web,
            ["--interface", "Output Only", "--channels", "2", "--seconds", "0", "--no-browser"],
        ),
    ],
)
def test_examples_print_config_errors_without_traceback(monkeypatch, capsys, module, argv) -> None:
    monkeypatch.setattr(module, "AudioIOSession", RaisingSession)

    exit_code = module.main(argv)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "input channel request invalid for input channel list [2]" in captured.err
    assert "Traceback" not in captured.err
