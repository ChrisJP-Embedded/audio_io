from __future__ import annotations

import numpy as np

from examples.input_level_meter import rms_dbfs
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
