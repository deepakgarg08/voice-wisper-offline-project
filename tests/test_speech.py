import pytest

from speech_typing import config
from speech_typing.exceptions import MicrophoneNotFoundError
from speech_typing.speech import AudioRecorder, cleanup_stale_temp_files


@pytest.fixture
def recorder(tmp_path):
    try:
        return AudioRecorder(
            sample_rate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            output_dir=tmp_path,
            filename_prefix="test_",
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


def test_cleanup_stale_temp_files_removes_matching_files(tmp_path):
    stale = tmp_path / "recording_abc123.wav"
    stale.write_bytes(b"not a real wav, just needs to exist")
    unrelated = tmp_path / "other_file.wav"
    unrelated.write_bytes(b"should not be touched")

    cleanup_stale_temp_files(tmp_path, "recording_")

    assert not stale.exists()
    assert unrelated.exists()


def test_cleanup_stale_temp_files_creates_missing_directory(tmp_path):
    target = tmp_path / "does" / "not" / "exist"
    cleanup_stale_temp_files(target, "recording_")
    assert target.is_dir()
