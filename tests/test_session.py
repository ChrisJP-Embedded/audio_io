from __future__ import annotations

import numpy as np
import pytest

from audio_io import AudioIOConfig, AudioIOSession
from tests.fakes import FakeBackend


def test_callback_receives_copied_input_block() -> None:
    backend = FakeBackend()
    received = []
    config = AudioIOConfig(input_channels=(0,), output_channels=(), block_words=4)

    session = AudioIOSession(config, input_callback=lambda block, info: received.append((block, info)), backend=backend)
    session.start()

    indata = np.arange(4, dtype=np.float32).reshape(4, 1)
    backend.stream.process(indata)
    indata[:] = 0

    assert session.is_active
    assert received[0][0].tolist() == [[0.0], [1.0], [2.0], [3.0]]
    assert received[0][1].frame_count == 4


def test_queue_mode_reads_input_blocks() -> None:
    backend = FakeBackend()
    config = AudioIOConfig(input_channels=(0, 1), output_channels=(), block_words=2)
    session = AudioIOSession(config, backend=backend).start()

    backend.stream.process(np.ones((2, 2), dtype=np.float32))

    assert session.read_input_block(timeout=0.1).shape == (2, 2)


def test_output_callback_supplies_output_block() -> None:
    backend = FakeBackend()
    config = AudioIOConfig(input_channels=(), output_channels=(0, 1), block_words=3)

    def output_callback(frames, info):
        return np.ones((frames, 2), dtype=np.float32)

    AudioIOSession(config, output_callback=output_callback, backend=backend).start()
    outdata = backend.stream.process()

    assert outdata.tolist() == [[1.0, 1.0], [1.0, 1.0], [1.0, 1.0]]


def test_queue_mode_writes_output_blocks() -> None:
    backend = FakeBackend()
    config = AudioIOConfig(input_channels=(), output_channels=(0,), block_words=2)
    session = AudioIOSession(config, backend=backend).start()

    session.write_output_block([[0.25], [0.5]])
    outdata = backend.stream.process()

    assert outdata.tolist() == [[0.25], [0.5]]


def test_output_underrun_renders_silence() -> None:
    backend = FakeBackend()
    config = AudioIOConfig(input_channels=(), output_channels=(0,), block_words=2)
    AudioIOSession(config, backend=backend).start()

    outdata = backend.stream.process()

    assert outdata.tolist() == [[0.0], [0.0]]


def test_rejects_wrong_output_shape() -> None:
    config = AudioIOConfig(input_channels=(), output_channels=(0, 1), block_words=2)
    session = AudioIOSession(config, backend=FakeBackend())

    with pytest.raises(ValueError, match="output block must have shape"):
        session.write_output_block([[1.0], [1.0]])


def test_context_manager_closes_stream() -> None:
    backend = FakeBackend()
    config = AudioIOConfig(input_channels=(), output_channels=(0,), block_words=2)

    with AudioIOSession(config, backend=backend) as session:
        assert session.is_active

    assert backend.stream.closed
