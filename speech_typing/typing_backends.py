"""Typing backends: inject transcribed text into the currently focused window.

Named typing_backends.py rather than typer.py to avoid any ambiguity with
the unrelated third-party `typer` CLI-framework package.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Type

from .environment import SessionType
from .exceptions import TypingAttemptFailedError, TypingBackendUnavailableError


class TypingBackend(ABC):
    """A way to inject text into the currently focused application."""

    name: str

    @staticmethod
    def is_available() -> bool:
        raise NotImplementedError

    @abstractmethod
    def type_text(self, text: str) -> None:
        """Type text at the current cursor position.

        Raises TypingAttemptFailedError on a (possibly transient) failure.
        """


class YdotoolBackend(TypingBackend):
    """Injects keystrokes via /dev/uinput at the kernel level.

    Works under both X11 and Wayland (including KDE Plasma's Wayland
    session), unlike xdotool (X11-only) or wtype (Wayland-only) -- the
    reason this is preferred regardless of session type.
    """

    name = "ydotool"

    def __init__(self, socket_path: Optional[Path] = None, key_delay_ms: int = 0) -> None:
        self._socket_path = socket_path
        self._key_delay_ms = key_delay_ms

    @staticmethod
    def is_available() -> bool:
        return shutil.which("ydotool") is not None

    def type_text(self, text: str) -> None:
        command = ["ydotool", "type"]
        if self._key_delay_ms:
            command += ["--key-delay", str(self._key_delay_ms)]
        command += ["--", text]

        env = os.environ.copy()
        if self._socket_path is not None:
            env["YDOTOOL_SOCKET"] = str(self._socket_path)

        try:
            subprocess.run(command, check=True, capture_output=True, text=True, env=env)
        except subprocess.CalledProcessError as exc:
            raise TypingAttemptFailedError(
                f"ydotool failed: {exc.stderr.strip()}. Is ydotoold running, and is "
                f"its socket ({self._socket_path or 'default path'}) readable by your user?"
            ) from exc


class XdotoolBackend(TypingBackend):
    """X11-only fallback; not usable under a Wayland session."""

    name = "xdotool"

    @staticmethod
    def is_available() -> bool:
        return shutil.which("xdotool") is not None

    def type_text(self, text: str) -> None:
        try:
            subprocess.run(["xdotool", "type", "--", text], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            raise TypingAttemptFailedError(f"xdotool failed: {exc.stderr.strip()}") from exc


class WtypeBackend(TypingBackend):
    """Wayland-only fallback; not usable under an X11 session."""

    name = "wtype"

    @staticmethod
    def is_available() -> bool:
        return shutil.which("wtype") is not None

    def type_text(self, text: str) -> None:
        try:
            subprocess.run(["wtype", text], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            raise TypingAttemptFailedError(f"wtype failed: {exc.stderr.strip()}") from exc


_BACKENDS: Dict[str, Type[TypingBackend]] = {
    "ydotool": YdotoolBackend,
    "xdotool": XdotoolBackend,
    "wtype": WtypeBackend,
}


def _build(backend_cls: Type[TypingBackend], socket_path: Optional[Path], key_delay_ms: int) -> TypingBackend:
    if backend_cls is YdotoolBackend:
        return YdotoolBackend(socket_path=socket_path, key_delay_ms=key_delay_ms)
    return backend_cls()


def select_typing_backend(
    preference: str,
    session_type: SessionType,
    socket_path: Optional[Path] = None,
    key_delay_ms: int = 0,
) -> TypingBackend:
    """Pick a typing backend.

    "auto" tries ydotool first (works under any session type), then falls
    back to the session-appropriate X11/Wayland-only tool if ydotool isn't
    installed. An explicit preference is used as-is (error if unavailable).
    """
    if preference != "auto":
        backend_cls = _BACKENDS.get(preference)
        if backend_cls is None:
            raise TypingBackendUnavailableError(f"Unknown typing backend: {preference!r}")
        if not backend_cls.is_available():
            raise TypingBackendUnavailableError(
                f"Typing backend {preference!r} is not installed."
            )
        return _build(backend_cls, socket_path, key_delay_ms)

    if YdotoolBackend.is_available():
        return _build(YdotoolBackend, socket_path, key_delay_ms)
    if session_type is SessionType.X11 and XdotoolBackend.is_available():
        return _build(XdotoolBackend, socket_path, key_delay_ms)
    if session_type is SessionType.WAYLAND and WtypeBackend.is_available():
        return _build(WtypeBackend, socket_path, key_delay_ms)

    raise TypingBackendUnavailableError(
        "No usable typing backend found. Install ydotool (works on both X11 "
        "and Wayland): sudo dnf install ydotool"
    )
