from __future__ import annotations

import time

import numpy as np
import pytest

from audio_io import AudioIOConfig, AudioIOSession, AudioTimingStatus, InterfaceNotFoundError, InvalidChannelRequestError
from tests.fakes import FakeBackend


def test_callback_receives_copied_input_block() -> None:
    backend = FakeBackend()
    received = []
    config = AudioIOConfig(interface="Fake", input_channels=(0,), output_channels=(), block_words=4)

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
    config = AudioIOConfig(interface="Fake", input_channels=(0, 1), output_channels=(), block_words=2)
    session = AudioIOSession(config, backend=backend).start()

    backend.stream.process(np.ones((2, 2), dtype=np.float32))

    assert session.read_input_block(timeout=0.1).shape == (2, 2)


def test_output_callback_supplies_output_block() -> None:
    backend = FakeBackend()
    config = AudioIOConfig(interface="Fake", input_channels=(), output_channels=(0, 1), block_words=3)

    def output_callback(frames, info):
        return np.ones((frames, 2), dtype=np.float32)

    AudioIOSession(config, output_callback=output_callback, backend=backend).start()
    outdata = backend.stream.process()

    assert outdata.tolist() == [[1.0, 1.0], [1.0, 1.0], [1.0, 1.0]]


def test_queue_mode_writes_output_blocks() -> None:
    backend = FakeBackend()
    config = AudioIOConfig(interface="Fake", input_channels=(), output_channels=(0,), block_words=2)
    session = AudioIOSession(config, backend=backend).start()

    session.write_output_block([[0.25], [0.5]])
    outdata = backend.stream.process()

    assert outdata.tolist() == [[0.25], [0.5]]


def test_output_underrun_renders_silence() -> None:
    backend = FakeBackend()
    config = AudioIOConfig(interface="Fake", input_channels=(), output_channels=(0,), block_words=2)
    AudioIOSession(config, backend=backend).start()

    outdata = backend.stream.process()

    assert outdata.tolist() == [[0.0], [0.0]]


def test_rejects_wrong_output_shape() -> None:
    config = AudioIOConfig(interface="Fake", input_channels=(), output_channels=(0, 1), block_words=2)
    session = AudioIOSession(config, backend=FakeBackend())

    with pytest.raises(ValueError, match="output block must have shape"):
        session.write_output_block([[1.0], [1.0]])


def test_rejects_unknown_dtype() -> None:
    with pytest.raises(ValueError, match="dtype must be one of"):
        AudioIOConfig(interface="Fake", input_channels=(0,), dtype="float64")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("sample_rate", "block_words", "expected_status"),
    [
        (48_000, 256, "good"),
        (192_000, 512, "caution"),
        (192_000, 256, "warning"),
        (384_000, 256, "high-risk"),
    ],
)
def test_timing_status_reports_callback_pressure(sample_rate: int, block_words: int, expected_status: str) -> None:
    config = AudioIOConfig(
        interface="Fake",
        output_channels=(0,),
        sample_rate=sample_rate,
        block_words=block_words,
    )

    timing = config.timing_status

    assert isinstance(timing, AudioTimingStatus)
    assert timing.status == expected_status
    assert timing.sample_period_seconds == 1.0 / sample_rate
    assert timing.block_duration_seconds == block_words / sample_rate


def test_timing_status_console_line_includes_sample_period_and_status() -> None:
    config = AudioIOConfig(interface="Fake", output_channels=(0,), sample_rate=192_000, block_words=256)

    line = config.timing_status.console_line()

    assert "fs=192000 Hz" in line
    assert "1/fs=5.208 us" in line
    assert "callbacks=750.0/s" in line
    assert "status=warning" in line


def test_input_callback_error_is_recorded_and_stream_restarts() -> None:
    backend = FakeBackend()
    config = AudioIOConfig(
        interface="Fake",
        input_channels=(0,),
        block_words=2,
        callback_restart_delay_seconds=0.01,
    )

    def input_callback(block, info):
        raise RuntimeError("boom")

    session = AudioIOSession(config, input_callback=input_callback, backend=backend)
    session.start()
    first_stream = backend.stream

    backend.stream.process(np.ones((2, 1), dtype=np.float32))

    deadline = time.monotonic() + 1.0
    while backend.stream is first_stream and time.monotonic() < deadline:
        time.sleep(0.01)

    assert isinstance(session.last_error, RuntimeError)
    assert session.restart_attempt_count == 1
    assert backend.stream is not first_stream
    assert backend.stream.active
    assert first_stream.closed
    session.stop()


def test_output_callback_error_renders_silence() -> None:
    backend = FakeBackend()
    config = AudioIOConfig(
        interface="Fake",
        output_channels=(0,),
        block_words=2,
        callback_restart_attempts=0,
    )

    def output_callback(frames, info):
        raise RuntimeError("boom")

    session = AudioIOSession(config, output_callback=output_callback, backend=backend).start()
    outdata = backend.stream.process()

    assert outdata.tolist() == [[0.0], [0.0]]
    assert isinstance(session.last_error, RuntimeError)


def test_context_manager_closes_stream() -> None:
    backend = FakeBackend()
    config = AudioIOConfig(interface="Fake", input_channels=(), output_channels=(0,), block_words=2)

    with AudioIOSession(config, backend=backend) as session:
        assert session.is_active

    assert backend.stream.closed


def test_accepts_interface_name_and_channel_lists() -> None:
    backend = FakeBackend()
    config = AudioIOConfig(interface="Fake", input_channels=[0], output_channels=[1], block_words=2)

    session = AudioIOSession(config, backend=backend).start()

    assert session.is_active
    assert config.input_channels == (0,)
    assert config.output_channels == (1,)


def test_rejects_unknown_interface_name() -> None:
    config = AudioIOConfig(interface="Missing", input_channels=[0], block_words=2)

    with pytest.raises(InterfaceNotFoundError, match="No audio interface matched 'Missing'"):
        AudioIOSession(config, backend=FakeBackend()).start()


def test_rejects_missing_interface_on_start() -> None:
    config = AudioIOConfig(input_channels=[0], block_words=2)

    with pytest.raises(InterfaceNotFoundError, match="audio interface must be named"):
        AudioIOSession(config, backend=FakeBackend()).start()


def test_rejects_invalid_input_channel_request() -> None:
    config = AudioIOConfig(interface="Fake", input_channels=[2], block_words=2)

    with pytest.raises(
        InvalidChannelRequestError,
        match=r"input channel request invalid for input channel list \[2\]",
    ):
        AudioIOSession(config, backend=FakeBackend()).start()


def test_rejects_invalid_output_channel_request() -> None:
    config = AudioIOConfig(interface="Fake", output_channels=[2], block_words=2)

    with pytest.raises(
        InvalidChannelRequestError,
        match=r"output channel request invalid for output channel list \[2\]",
    ):
        AudioIOSession(config, backend=FakeBackend()).start()
