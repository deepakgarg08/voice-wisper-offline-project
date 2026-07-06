"""Types recognized text into the currently focused application."""

from __future__ import annotations

import shutil
import subprocess

from .utils import TypingBackendUnavailableError


class TextTyper:
    """Sends text to the focused application via ydotool.

    ydotool injects input at the kernel (uinput) level, which works under
    both X11 and Wayland compositors — including KDE Plasma's Wayland
    session, where X11-only tools like xdotool don't function, and
    Wayland-only tools like wtype won't work if the user later switches
    back to X11. ydotool works either way with no code changes.
    """

    def __init__(self, backend: str = "ydotool", key_delay_ms: int = 0) -> None:
        if backend != "ydotool":
            raise TypingBackendUnavailableError(f"Unsupported typing backend: {backend}")

        if shutil.which("ydotool") is None:
            raise TypingBackendUnavailableError(
                "ydotool is not installed. Install it with: sudo dnf install ydotool"
            )

        self._key_delay_ms = key_delay_ms

    def type_text(self, text: str) -> None:
        """Type the given text at the current cursor/focus position."""
        command = ["ydotool", "type"]
        if self._key_delay_ms:
            command += ["--key-delay", str(self._key_delay_ms)]
        command += ["--", text]

        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            raise TypingBackendUnavailableError(
                "ydotool failed to type text. Is the ydotoold daemon running? "
                f"Details: {exc.stderr.strip()}"
            ) from exc
