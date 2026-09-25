"""Runtime configuration derived from user_config.py and the host system."""

from __future__ import annotations

import os
import platform
import tempfile
from pathlib import Path
from typing import List

from . import user_config
from .exceptions import ConfigError
from .hotkeys import HotkeySpec

# Project root: .../voice-project
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOGGLE_HOTKEY_ENABLED = user_config.TOGGLE_HOTKEY_ENABLED
PUSH_TO_TALK_HOTKEY_ENABLED = user_config.PUSH_TO_TALK_HOTKEY_ENABLED

# --- whisper.cpp location ---
# Current layout:
#   whisper.cpp/
#     build/bin/whisper-cli
#     models/
#     voice-project/
#
# The environment variable allows a different layout on another machine.
_env_whisper_dir = os.environ.get("SPEECH_TYPING_WHISPER_DIR")
if _env_whisper_dir:
    WHISPER_DIR = Path(_env_whisper_dir).expanduser()
elif (PROJECT_ROOT / "whisper.cpp").is_dir():
    WHISPER_DIR = PROJECT_ROOT / "whisper.cpp"
else:
    WHISPER_DIR = PROJECT_ROOT.parent

WHISPER_CLI = WHISPER_DIR / "build" / "bin" / "whisper-cli"
MODELS_DIR = WHISPER_DIR / "models"

KNOWN_MODELS = {"tiny", "base", "small", "medium", "large"}
MODEL_FILE_NAMES = {
    "tiny": "ggml-tiny.bin",
    "base": "ggml-base.bin",
    "small": "ggml-small.bin",
    "medium": "ggml-medium.bin",
    "large": "ggml-large-v3.bin",
}

MODEL = user_config.MODEL


def model_path(model: str = MODEL) -> Path:
    try:
        filename = MODEL_FILE_NAMES[model]
    except KeyError as exc:
        raise ValueError(f"Unsupported model: {model}") from exc
    return MODELS_DIR / filename


MODEL_PATH = model_path(MODEL)

# --- audio recording ---
SAMPLE_RATE = 16000
CHANNELS = 1
MIN_RECORDING_DURATION_MS = 300
MAX_RECORDING_DURATION_S = user_config.MAX_RECORDING_DURATION_S

TEMP_AUDIO_DIR = Path(
    os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir())
) / "speech_typing"
TEMP_AUDIO_PREFIX = "recording_"

# --- permanent project data ---
_recordings_root = Path(user_config.RECORDINGS_ASSETS_DIR)
RECORDINGS_ASSETS_DIR = (
    _recordings_root if _recordings_root.is_absolute()
    else PROJECT_ROOT / _recordings_root
)
AUDIO_DIR = RECORDINGS_ASSETS_DIR / "RECORDINGS"
TRANSCRIPT_DIR = RECORDINGS_ASSETS_DIR / "TRANSCRIPTS"
SAVE_AUDIO = user_config.SAVE_AUDIO
SAVE_TRANSCRIPT = user_config.SAVE_TRANSCRIPT

# --- transcription ---
LANGUAGE = user_config.LANGUAGE
TRANSCRIPTION_MODE = user_config.TRANSCRIPTION_MODE

# --- hotkeys ---
HOTKEYS: List[HotkeySpec] = [
    HotkeySpec(
        name="toggle",
        keys=("KEY_SPACE", "KEY_RIGHTCTRL"),
        behavior="toggle",
        enabled=user_config.TOGGLE_HOTKEY_ENABLED,
    ),
    HotkeySpec(
        name="push_to_talk",
        keys=("KEY_LEFTCTRL", "KEY_LEFTMETA"),
        behavior="push_to_talk",
        enabled=user_config.PUSH_TO_TALK_HOTKEY_ENABLED,
    ),
]
HOTKEY_DEBOUNCE_MS = 75

# --- typing ---
TYPING_BACKEND = user_config.TYPING_BACKEND
TYPING_MAX_RETRIES = 3
TYPING_RETRY_DELAY_S = 0.3
CLIPBOARD_FALLBACK_ENABLED = user_config.CLIPBOARD_FALLBACK_ENABLED

# Optional legacy Linux backends. These are not required when
# python_clipboard works.
YDOTOOL_KEY_DELAY_MS = 0
YDOTOOL_SOCKET = Path(
    os.environ.get(
        "YDOTOOL_SOCKET",
        str(Path("/run/user") / str(os.getuid()) / ".ydotool_socket")
        if hasattr(os, "getuid")
        else "",
    )
) if platform.system() != "Windows" else None

# --- desktop feedback ---
NOTIFICATIONS_ENABLED = user_config.NOTIFICATIONS_ENABLED
SOUND_EFFECTS_ENABLED = user_config.SOUND_EFFECTS_ENABLED
SOUND_VOLUME = user_config.SOUND_VOLUME
_SOUND_THEME_DIR = Path("/usr/share/sounds/freedesktop/stereo")
SOUND_RECORDING_START = _SOUND_THEME_DIR / "message-new-instant.oga"
SOUND_RECORDING_STOP = _SOUND_THEME_DIR / "complete.oga"

# --- logging ---
LOG_LEVEL = "INFO"
if platform.system() == "Windows":
    _state_base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
else:
    _state_base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
LOG_DIR = _state_base / "speech_typing"
LOG_FILE = LOG_DIR / "speech_typing.log"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3


def validate() -> None:
    problems: List[str] = []

    if MODEL not in KNOWN_MODELS:
        problems.append(f"MODEL must be one of {sorted(KNOWN_MODELS)}, got {MODEL!r}")
    if not WHISPER_CLI.is_file():
        problems.append(f"whisper-cli executable not found at: {WHISPER_CLI}")
    elif platform.system() != "Windows" and not os.access(WHISPER_CLI, os.X_OK):
        problems.append(f"whisper-cli at {WHISPER_CLI} is not executable")
    if not MODEL_PATH.is_file():
        problems.append(f"Model file not found: {MODEL_PATH}")

    if SAMPLE_RATE <= 0:
        problems.append(f"SAMPLE_RATE must be positive, got {SAMPLE_RATE}")
    if CHANNELS <= 0:
        problems.append(f"CHANNELS must be positive, got {CHANNELS}")
    if MIN_RECORDING_DURATION_MS < 0:
        problems.append("MIN_RECORDING_DURATION_MS must not be negative")
    if MAX_RECORDING_DURATION_S <= 0:
        problems.append("MAX_RECORDING_DURATION_S must be positive")
    if MIN_RECORDING_DURATION_MS >= MAX_RECORDING_DURATION_S * 1000:
        problems.append("MIN_RECORDING_DURATION_MS must be less than MAX_RECORDING_DURATION_S")

    if not LANGUAGE:
        problems.append("LANGUAGE must not be empty")
    if TRANSCRIPTION_MODE not in ("original", "translate_en"):
        problems.append("TRANSCRIPTION_MODE must be 'original' or 'translate_en'")

    if not any(h.enabled for h in HOTKEYS):
        problems.append("At least one hotkey must be enabled")
    if HOTKEY_DEBOUNCE_MS < 0:
        problems.append("HOTKEY_DEBOUNCE_MS must not be negative")

    if TYPING_BACKEND not in (
        "auto", "python_clipboard", "ydotool", "xdotool", "wtype"
    ):
        problems.append(
            "TYPING_BACKEND must be 'auto', 'python_clipboard', 'ydotool', "
            "'xdotool', or 'wtype'"
        )
    if TYPING_MAX_RETRIES < 1:
        problems.append("TYPING_MAX_RETRIES must be at least 1")
    if TYPING_RETRY_DELAY_S < 0:
        problems.append("TYPING_RETRY_DELAY_S must not be negative")

    try:
        TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        if SAVE_AUDIO:
            AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        if SAVE_TRANSCRIPT:
            TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        problems.append(f"Unable to create application data directories: {exc}")

    if problems:
        raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(problems))
