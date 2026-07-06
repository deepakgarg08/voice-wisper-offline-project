from speech_typing import config


def test_model_path_derivation():
    assert config.model_path("tiny") == config.MODELS_DIR / "ggml-tiny.bin"
    assert config.model_path("small") == config.MODELS_DIR / "ggml-small.bin"
    assert config.MODEL_PATH == config.model_path(config.MODEL)


def test_whisper_cli_and_current_model_exist():
    assert config.WHISPER_CLI.is_file()
    assert config.MODEL_PATH.is_file()
