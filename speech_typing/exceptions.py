"""Custom exceptions used throughout speech_typing."""

from __future__ import annotations


class ConfigError(RuntimeError):
    """One or more configuration values in config.py are invalid."""


class MicrophoneNotFoundError(RuntimeError):
    """No usable input (microphone) audio device is available."""


class WhisperExecutableNotFoundError(RuntimeError):
    """The configured whisper.cpp CLI binary can't be found or executed."""


class ModelNotFoundError(RuntimeError):
    """The configured ggml model file does not exist."""


class NoSpeechDetectedError(RuntimeError):
    """whisper.cpp produced no transcribed text for a recording."""


class TypingBackendUnavailableError(RuntimeError):
    """No typing backend can be used at all (nothing to retry)."""


class TypingAttemptFailedError(RuntimeError):
    """A single typing attempt failed; may be transient and worth retrying."""


class KeyboardAccessError(RuntimeError):
    """The keyboard input devices exist but can't be opened (permissions)."""
