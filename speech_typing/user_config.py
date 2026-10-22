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

# 0.0 = silent, 1.0 = normal system playback volume.
# 0.15 gives a quiet recording start/stop sound.
SOUND_VOLUME = 0.15

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

# ---------------------------------------------------------------------------
# Streaming ASR (low latency)
# ---------------------------------------------------------------------------

# Keep a warm whisper-server running and transcribe the recording in chunks
# *while you speak*, so only the last short chunk is left after release.
# Falls back to whisper-cli per utterance if the server cannot start.
STREAMING_ENABLED = True
WHISPER_THREADS = 6

# Chunks are cut at pauses: at least STREAM_MIN_CHUNK_S long, ending after
# STREAM_SILENCE_MS of quiet; forced cut at STREAM_MAX_CHUNK_S.
STREAM_MIN_CHUNK_S = 2.0
STREAM_MAX_CHUNK_S = 8.0
STREAM_SILENCE_MS = 400

# Feed the end of the previous chunk to whisper as context (better continuity).
STREAM_USE_PROMPT = True

# False: type everything at once on release (safe with held modifier keys).
# True: type each chunk as soon as it is recognised, while still recording.
STREAM_TYPE_WHILE_RECORDING = False
