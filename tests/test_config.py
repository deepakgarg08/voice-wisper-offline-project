from pathlib import Path

import pytest

from speech_typing import config
from speech_typing.exceptions import ConfigError
from speech_typing.hotkeys import HotkeySpec


def test_model_path_derivation():
    assert config.model_path("tiny") == config.MODELS_DIR / "ggml-tiny.bin"
    assert config.model_path("small") == config.MODELS_DIR / "ggml-small.bin"
    assert config.MODEL_PATH == config.model_path(config.MODEL)


def test_whisper_cli_and_current_model_exist():
    assert config.WHISPER_CLI.is_file()
    assert config.MODEL_PATH.is_file()


def test_validate_passes_with_current_settings():
    config.validate()  # should not raise


def test_validate_rejects_unknown_model(monkeypatch):
    monkeypatch.setattr(config, "MODEL", "gigantic")
    with pytest.raises(ConfigError, match="MODEL"):
        config.validate()


def test_validate_rejects_missing_model_file(monkeypatch):
    monkeypatch.setattr(config, "MODEL_PATH", Path("/nonexistent/model.bin"))
    with pytest.raises(ConfigError, match="Model file not found"):
        config.validate()


def test_validate_rejects_all_hotkeys_disabled(monkeypatch):
    monkeypatch.setattr(config, "HOTKEYS", [HotkeySpec(name="primary", keys=("KEY_RIGHTCTRL",), enabled=False)])
    with pytest.raises(ConfigError, match="HOTKEYS"):
        config.validate()


def test_validate_rejects_bad_typing_backend(monkeypatch):
    monkeypatch.setattr(config, "TYPING_BACKEND", "not-a-real-backend")
    with pytest.raises(ConfigError, match="TYPING_BACKEND"):
        config.validate()


def test_validate_rejects_min_duration_exceeding_max(monkeypatch):
    monkeypatch.setattr(config, "MIN_RECORDING_DURATION_MS", 999_999)
    with pytest.raises(ConfigError, match="MIN_RECORDING_DURATION_MS"):
        config.validate()


def test_validate_reports_multiple_problems_at_once(monkeypatch):
    monkeypatch.setattr(config, "MODEL", "gigantic")
    monkeypatch.setattr(config, "TYPING_MAX_RETRIES", 0)
    with pytest.raises(ConfigError) as exc_info:
        config.validate()
    message = str(exc_info.value)
    assert "MODEL" in message
    assert "TYPING_MAX_RETRIES" in message
