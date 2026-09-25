"""Cross-platform typing backends.

The primary backend uses Python packages:
    pyperclip  -> clipboard
    pynput     -> Ctrl+V / Cmd+V

ydotool/xdotool/wtype remain optional fallbacks for environments where the
Python clipboard/paste path cannot operate.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Type

from .environment import SessionType
from .exceptions import TypingAttemptFailedError, TypingBackendUnavailableError


class TypingBackend(ABC):
    name: str

    @staticmethod
    def is_available() -> bool:
        raise NotImplementedError

    @abstractmethod
    def type_text(self, text: str) -> None:
        """Type/paste text at the current cursor position."""


class PythonClipboardBackend(TypingBackend):
    """Cross-platform clipboard + paste backend using Python packages."""

    name = "python_clipboard"

    @staticmethod
    def is_available() -> bool:
        try:
            import pyperclip  # noqa: F401
            from pynput import keyboard  # noqa: F401
        except Exception:
            return False
        return True

    def __init__(self) -> None:
        try:
            import pyperclip
            from pynput import keyboard
        except Exception as exc:
            raise TypingBackendUnavailableError(
                "python_clipboard requires the Python packages 'pyperclip' and 'pynput'. "
                "Install them with: python3 -m pip install pyperclip pynput"
            ) from exc

        self._pyperclip = pyperclip
        self._keyboard = keyboard
        self._controller = keyboard.Controller()
        self._paste_key = (
            keyboard.Key.cmd
            if os.name == "posix" and self._is_macos()
            else keyboard.Key.ctrl
        )

    @staticmethod
    def _is_macos() -> bool:
        import platform
        return platform.system() == "Darwin"

    def type_text(self, text: str) -> None:
        try:
            self._pyperclip.copy(text)

            # Give the clipboard owner a moment before injecting paste.
            time.sleep(0.05)

            # pynput.keyboard.Controller is NOT a context manager.
            # Use it directly to send Ctrl+V to the currently focused window.
            self._controller.press(self._paste_key)
            self._controller.press("v")
            self._controller.release("v")
            self._controller.release(self._paste_key)

            # Do not restore the previous clipboard: restoring it immediately
            # can race with the target application's paste operation.
            time.sleep(0.05)
        except Exception as exc:
            raise TypingAttemptFailedError(
                f"Python clipboard/paste backend failed: {exc}"
            ) from exc


class YdotoolBackend(TypingBackend):
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
                f"ydotool failed: {exc.stderr.strip()}"
            ) from exc


class XdotoolBackend(TypingBackend):
    name = "xdotool"

    @staticmethod
    def is_available() -> bool:
        return shutil.which("xdotool") is not None

    def type_text(self, text: str) -> None:
        try:
            subprocess.run(
                ["xdotool", "type", "--", text],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise TypingAttemptFailedError(
                f"xdotool failed: {exc.stderr.strip()}"
            ) from exc


class WtypeBackend(TypingBackend):
    name = "wtype"

    @staticmethod
    def is_available() -> bool:
        return shutil.which("wtype") is not None

    def type_text(self, text: str) -> None:
        try:
            subprocess.run(
                ["wtype", text],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise TypingAttemptFailedError(
                f"wtype failed: {exc.stderr.strip()}"
            ) from exc


_BACKENDS: Dict[str, Type[TypingBackend]] = {
    "python_clipboard": PythonClipboardBackend,
    "ydotool": YdotoolBackend,
    "xdotool": XdotoolBackend,
    "wtype": WtypeBackend,
}


def _build(
    backend_cls: Type[TypingBackend],
    socket_path: Optional[Path],
    key_delay_ms: int,
) -> TypingBackend:
    if backend_cls is YdotoolBackend:
        return YdotoolBackend(socket_path=socket_path, key_delay_ms=key_delay_ms)
    return backend_cls()


def _available_backend_names(session_type: SessionType) -> list[str]:
    names = []
    if PythonClipboardBackend.is_available():
        names.append("python_clipboard")
    if YdotoolBackend.is_available():
        names.append("ydotool")
    if session_type is SessionType.X11 and XdotoolBackend.is_available():
        names.append("xdotool")
    if session_type is SessionType.WAYLAND and WtypeBackend.is_available():
        names.append("wtype")
    return names


def select_typing_backend(
    preference: str,
    session_type: SessionType,
    socket_path: Optional[Path] = None,
    key_delay_ms: int = 0,
) -> TypingBackend:
    """Select a backend.

    'auto' prefers the Python clipboard+paste backend. If that cannot be
    constructed/used, the existing Linux command backends remain available.
    """

    if preference != "auto":
        backend_cls = _BACKENDS.get(preference)
        if backend_cls is None:
            raise TypingBackendUnavailableError(
                f"Unknown typing backend: {preference!r}"
            )
        if not backend_cls.is_available():
            raise TypingBackendUnavailableError(
                f"Typing backend {preference!r} is not installed/available."
            )
        return _build(backend_cls, socket_path, key_delay_ms)

    # Prefer the cross-platform Python implementation.
    if PythonClipboardBackend.is_available():
        return PythonClipboardBackend()

    # Linux fallbacks.
    if YdotoolBackend.is_available():
        return _build(YdotoolBackend, socket_path, key_delay_ms)
    if session_type is SessionType.X11 and XdotoolBackend.is_available():
        return XdotoolBackend()
    if session_type is SessionType.WAYLAND and WtypeBackend.is_available():
        return WtypeBackend()

    available = ", ".join(_available_backend_names(session_type)) or "none"
    raise TypingBackendUnavailableError(
        "No usable typing backend found. Install Python packages with "
        "'python3 -m pip install pyperclip pynput'. "
        f"Detected available backends: {available}"
    )
