from pathlib import Path

import pytest

from speech_typing import config
from speech_typing.transcribe import Transcriber
from speech_typing.exceptions import ModelNotFoundError, WhisperExecutableNotFoundError

SAMPLE_WAV = config.WHISPER_DIR / "samples" / "jfk.wav"


def test_transcribe_returns_clean_text():
    transcriber = Transcriber(config.WHISPER_CLI, config.MODEL_PATH, "en")
    text = transcriber.transcribe(SAMPLE_WAV)
    assert text
    assert "\n" not in text
    assert "-->" not in text  # no timestamp markers leaked through
    assert "fellow Americans" in text


def test_missing_model_raises():
    with pytest.raises(ModelNotFoundError):
        Transcriber(config.WHISPER_CLI, Path("/nonexistent/model.bin"), "en")


def test_missing_whisper_cli_raises():
    with pytest.raises(WhisperExecutableNotFoundError):
        Transcriber(Path("/nonexistent/whisper-cli"), config.MODEL_PATH, "en")
