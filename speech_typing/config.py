"""Central configuration for the speech_typing app.

To switch models, change MODEL below to "tiny", "base", or "small" — the
ggml model file path is derived automatically from WHISPER_DIR.
"""

from pathlib import Path

# --- whisper.cpp location ---
WHISPER_DIR = Path("/mnt/shared4/LLAMACPP/models/wisperalternative/whisper.cpp")
WHISPER_CLI = WHISPER_DIR / "build" / "bin" / "whisper-cli"
MODELS_DIR = WHISPER_DIR / "models"

# --- model selection ---
MODEL = "base"  # one of: "tiny", "base", "small"


def model_path(model: str = MODEL) -> Path:
    """Resolve the ggml model file path for the given model name."""
    return MODELS_DIR / f"ggml-{model}.bin"


MODEL_PATH = model_path(MODEL)

# --- audio recording ---
SAMPLE_RATE = 16000  # Hz, matches whisper.cpp's expected input format
CHANNELS = 1
TEMP_AUDIO_FILE = Path("/tmp/speech_typing_recording.wav")
MIN_RECORDING_DURATION_MS = 300

# --- transcription ---
LANGUAGE = "en"  # or "auto" to auto-detect the spoken language

# --- typing ---
TYPING_BACKEND = "ydotool"  # injects input via uinput; works on X11 and Wayland
YDOTOOL_KEY_DELAY_MS = 0  # per-keystroke delay in ms, 0 = ydotool's own default

# --- hotkey ---
HOTKEY = "KEY_RIGHTCTRL"  # evdev key name; hold to record, release to stop

# --- logging ---
LOG_LEVEL = "INFO"
