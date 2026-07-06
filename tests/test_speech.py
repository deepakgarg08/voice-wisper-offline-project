import pytest

from speech_typing import config
from speech_typing.speech import AudioRecorder
from speech_typing.utils import MicrophoneNotFoundError


@pytest.fixture
def recorder(tmp_path):
    try:
        return AudioRecorder(
            sample_rate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            output_path=tmp_path / "test.wav",
            min_duration_ms=config.MIN_RECORDING_DURATION_MS,
        )
    except MicrophoneNotFoundError:
        pytest.skip("no microphone available in this environment")


def test_immediate_stop_is_discarded_as_too_short(recorder):
    recorder.start()
    result = recorder.stop()
    assert result is None


def test_stop_without_start_is_noop(recorder):
    assert recorder.stop() is None
