"""Clipboard fallback used when typing directly fails after all retries."""

from __future__ import annotations

import shutil
import subprocess

from .environment import SessionType


class ClipboardFallback:
    """Copies text to the system clipboard via wl-copy (Wayland) or xclip/xsel (X11)."""

    def __init__(self, session_type: SessionType) -> None:
        self._session_type = session_type

    def is_available(self) -> bool:
        if self._session_type is SessionType.WAYLAND:
            return shutil.which("wl-copy") is not None
        return shutil.which("xclip") is not None or shutil.which("xsel") is not None

    def copy(self, text: str) -> None:
        if self._session_type is SessionType.WAYLAND and shutil.which("wl-copy"):
            subprocess.run(["wl-copy"], input=text, text=True, check=True)
            return
        if shutil.which("xclip"):
            subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True, check=True)
            return
        if shutil.which("xsel"):
            subprocess.run(["xsel", "--clipboard", "--input"], input=text, text=True, check=True)
            return
        raise RuntimeError("No clipboard tool available (wl-copy/xclip/xsel).")
