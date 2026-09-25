"""User-editable settings for the speech typing project.

Normally you only change values in this file. Paths are project-relative by
default so the project can be moved between Linux, Windows, and macOS.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Whisper
# ---------------------------------------------------------------------------

MODEL = "base"  # tiny, base, small, medium, large
LANGUAGE = "auto"  # auto, en, de, hi, etc.
TRANSCRIPTION_MODE = "translate_en"  # original or translate_en

# ---------------------------------------------------------------------------
# Recording / storage
# ---------------------------------------------------------------------------

MAX_RECORDING_DURATION_S = 300  # 5 minutes
RECORDINGS_ASSETS_DIR = "RECORDINGS-ASSETS"
SAVE_AUDIO = True
SAVE_TRANSCRIPT = True

# ---------------------------------------------------------------------------
# Hotkeys
# ---------------------------------------------------------------------------

TOGGLE_HOTKEY_ENABLED = True
PUSH_TO_TALK_HOTKEY_ENABLED = True

# ---------------------------------------------------------------------------
# Desktop feedback
# ---------------------------------------------------------------------------

NOTIFICATIONS_ENABLED = True
SOUND_EFFECTS_ENABLED = True

# ---------------------------------------------------------------------------
# Typing
# ---------------------------------------------------------------------------

# auto = prefer the Python clipboard+paste backend; use ydotool/xdotool/wtype
# only as platform/session fallbacks.
#
# Available:
#   auto
#   python_clipboard
#   ydotool
#   xdotool
#   wtype
TYPING_BACKEND = "auto"

# If every typing backend fails, keep the old safe fallback of copying the
# result to the clipboard.
CLIPBOARD_FALLBACK_ENABLED = True
