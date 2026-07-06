"""Central configuration for the speech_typing app.

To switch models, change MODEL below to "tiny", "base", or "small" — the
ggml model file path is derived automatically from WHISPER_DIR.

validate() is called once at startup (see app.py) and raises ConfigError
listing every problem found, rather than failing on the first one.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List

from .exceptions import ConfigError
from .hotkeys import HotkeySpec

# --- whisper.cpp location ---
# Overridable via env var so this can be packaged (RPM/Flatpak) without a
# hardcoded path baked into the source -- the default matches this dev setup.
WHISPER_DIR = Path(
    os.environ.get(
        "SPEECH_TYPING_WHISPER_DIR",
        "/mnt/shared4/LLAMACPP/models/wisperalternative/whisper.cpp",
    )
)
WHISPER_CLI = WHISPER_DIR / "build" / "bin" / "whisper-cli"
MODELS_DIR = WHISPER_DIR / "models"

# --- model selection ---
_KNOWN_MODELS = {"tiny", "base", "small"}
MODEL = "base"  # one of: "tiny", "base", "small"


def model_path(model: str = MODEL) -> Path:
    """Resolve the ggml model file path for the given model name."""
    return MODELS_DIR / f"ggml-{model}.bin"


MODEL_PATH = model_path(MODEL)

# --- audio recording ---
SAMPLE_RATE = 16000  # Hz, matches whisper.cpp's expected input format
CHANNELS = 1
MIN_RECORDING_DURATION_MS = 300  # shorter recordings are discarded (accidental taps)
MAX_RECORDING_DURATION_S = 60  # recording auto-stops if held this long

# Per-session scratch directory (cleared automatically by the OS/logind on
# logout, unlike a fixed path under /tmp) for the WAV file of each utterance.
TEMP_AUDIO_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir())) / "speech_typing"
TEMP_AUDIO_PREFIX = "recording_"

# --- transcription ---
LANGUAGE = "en"  # or "auto" to auto-detect the spoken language

# --- hotkeys ---
# A hotkey engages the instant every listed key is held, and disengages the
# instant any one of them is released -- so a chord like the secondary one
# below behaves as press-all-hold-release, same as the single-key primary.
HOTKEYS: List[HotkeySpec] = [
    HotkeySpec(name="primary", keys=("KEY_RIGHTCTRL",), enabled=True),
    HotkeySpec(name="secondary", keys=("KEY_LEFTCTRL", "KEY_LEFTALT", "KEY_SPACE"), enabled=True),
]
HOTKEY_DEBOUNCE_MS = 75  # ignore a hotkey re-engaging this soon after it last disengaged

# --- typing ---
TYPING_BACKEND = "auto"  # "auto", "ydotool", "xdotool", or "wtype"
YDOTOOL_KEY_DELAY_MS = 0  # per-keystroke delay in ms, 0 = ydotool's own default
# ydotoold's default socket path; the ydotool client's own compiled-in default
# (/run/user/<uid>/.ydotool_socket) doesn't match this, so it must be passed
# explicitly rather than relying on the client's guess.
YDOTOOL_SOCKET = Path("/tmp/.ydotool_socket")
TYPING_MAX_RETRIES = 3
TYPING_RETRY_DELAY_S = 0.3
CLIPBOARD_FALLBACK_ENABLED = True  # copy to clipboard if typing fails after all retries

# --- desktop feedback ---
NOTIFICATIONS_ENABLED = True
SOUND_EFFECTS_ENABLED = True
_SOUND_THEME_DIR = Path("/usr/share/sounds/freedesktop/stereo")
SOUND_RECORDING_START = _SOUND_THEME_DIR / "message-new-instant.oga"
SOUND_RECORDING_STOP = _SOUND_THEME_DIR / "complete.oga"

# --- logging ---
LOG_LEVEL = "INFO"
LOG_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "speech_typing"
LOG_FILE = LOG_DIR / "speech_typing.log"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3


def validate() -> None:
    """Validate configuration, raising ConfigError listing every problem found."""
    problems: List[str] = []

    if MODEL not in _KNOWN_MODELS:
        problems.append(f"MODEL must be one of {sorted(_KNOWN_MODELS)}, got {MODEL!r}")
    if not WHISPER_CLI.is_file():
        problems.append(f"whisper-cli executable not found at: {WHISPER_CLI}")
    elif not os.access(WHISPER_CLI, os.X_OK):
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

    if not any(h.enabled for h in HOTKEYS):
        problems.append("At least one entry in HOTKEYS must be enabled")
    if HOTKEY_DEBOUNCE_MS < 0:
        problems.append("HOTKEY_DEBOUNCE_MS must not be negative")

    if TYPING_BACKEND not in ("auto", "ydotool", "xdotool", "wtype"):
        problems.append(
            f"TYPING_BACKEND must be 'auto', 'ydotool', 'xdotool', or 'wtype', got {TYPING_BACKEND!r}"
        )
    if TYPING_MAX_RETRIES < 1:
        problems.append("TYPING_MAX_RETRIES must be at least 1")
    if TYPING_RETRY_DELAY_S < 0:
        problems.append("TYPING_RETRY_DELAY_S must not be negative")

    try:
        TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        problems.append(f"TEMP_AUDIO_DIR ({TEMP_AUDIO_DIR}) is not usable: {exc}")

    if problems:
        raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(problems))
