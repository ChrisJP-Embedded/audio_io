from __future__ import annotations

import numpy as np

from examples.input_level_meter import rms_dbfs
from examples.loopback_sine_level_check import dbfs_to_peak, estimate_sine_peak_dbfs, levels_within_tolerance
from examples.sine_output import SineGenerator, parse_channels


def test_parse_channels() -> None:
    assert parse_channels("0, 2,3") == (0, 2, 3)


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
