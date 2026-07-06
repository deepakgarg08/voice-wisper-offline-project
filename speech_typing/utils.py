"""Shared exceptions, logging setup, and keyboard-device discovery."""

from __future__ import annotations

import glob
import logging
import sys
from typing import List

from evdev import InputDevice, ecodes


class MicrophoneNotFoundError(RuntimeError):
    """No usable input (microphone) audio device is available."""


class WhisperExecutableNotFoundError(RuntimeError):
    """The configured whisper.cpp CLI binary can't be found or executed."""


class ModelNotFoundError(RuntimeError):
    """The configured ggml model file does not exist."""


class NoSpeechDetectedError(RuntimeError):
    """whisper.cpp produced no transcribed text for a recording."""


class TypingBackendUnavailableError(RuntimeError):
    """The configured typing backend can't be used."""


class KeyboardAccessError(RuntimeError):
    """The keyboard input devices exist but can't be opened (permissions)."""


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure and return the application-wide logger."""
    logger = logging.getLogger("speech_typing")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def find_hotkey_capable_devices(key_name: str) -> List[InputDevice]:
    """Return all input devices that report the given evdev key capability.

    Globs /dev/input directly rather than using evdev.list_devices(), which
    silently drops devices the process can't read — that would otherwise be
    misreported as "no keyboard found" instead of a permissions problem.
    """
    key_code = getattr(ecodes, key_name)
    matches: List[InputDevice] = []
    permission_errors = 0

    for path in glob.glob("/dev/input/event*"):
        try:
            device = InputDevice(path)
        except (PermissionError, OSError):
            permission_errors += 1
            continue

        if key_code in device.capabilities().get(ecodes.EV_KEY, []):
            matches.append(device)
        else:
            device.close()

    if not matches:
        if permission_errors:
            raise KeyboardAccessError(
                "Found input devices but could not open any of them "
                f"({permission_errors} permission denied). Add your user to the "
                "'input' group with: sudo usermod -aG input $USER, then log out "
                "and back in."
            )
        raise RuntimeError(f"No input device reports the '{key_name}' key.")

    return matches
