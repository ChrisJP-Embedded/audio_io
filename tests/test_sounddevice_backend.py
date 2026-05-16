from __future__ import annotations

import numpy as np

from audio_io.backends import _duplex_callback, _input_callback, _output_callback
from audio_io.config import AudioIOConfig


def test_duplex_callback_presents_compact_selected_channels() -> None:
    config = AudioIOConfig(input_channels=(0, 2), output_channels=(1, 3), block_words=2)
    received = []

    def callback(indata, outdata, frames, time, status):
        received.append(indata.copy())
        outdata[:] = [[0.5, 0.75], [1.0, 1.25]]

    wrapped = _duplex_callback(config, callback)
    indata = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)
    outdata = np.empty((2, 4), dtype=np.float32)

    wrapped(indata, outdata, 2, None, None)

    assert received[0].tolist() == [[1.0, 3.0], [4.0, 6.0]]
    assert outdata.tolist() == [[0.0, 0.5, 0.0, 0.75], [0.0, 1.0, 0.0, 1.25]]


def test_input_callback_presents_compact_selected_channels() -> None:
    config = AudioIOConfig(input_channels=(1,), block_words=2)
    received = []

    wrapped = _input_callback(config, lambda indata, outdata, frames, time, status: received.append(indata.copy()))
    wrapped(np.array([[1, 2], [3, 4]], dtype=np.float32), 2, None, None)

    assert received[0].tolist() == [[2.0], [4.0]]


def test_output_callback_routes_compact_selected_channels() -> None:
    config = AudioIOConfig(output_channels=(1,), block_words=2)

    def callback(indata, outdata, frames, time, status):
        outdata[:] = [[0.25], [0.5]]

    outdata = np.empty((2, 2), dtype=np.float32)
    _output_callback(config, callback)(outdata, 2, None, None)

    assert outdata.tolist() == [[0.0, 0.25], [0.0, 0.5]]
