"""Detects whether the current desktop session is Wayland or X11.

Drives typing-backend auto-selection: ydotool works under either, but the
X11-only/Wayland-only fallback tools (xdotool/wtype) need to know which
session they'd actually be running under.
"""

from __future__ import annotations

import os
from enum import Enum


class SessionType(Enum):
    WAYLAND = "wayland"
    X11 = "x11"
    UNKNOWN = "unknown"


def detect_session_type() -> SessionType:
    """Best-effort detection of the running desktop session type."""
    xdg_session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if xdg_session_type == "wayland":
        return SessionType.WAYLAND
    if xdg_session_type == "x11":
        return SessionType.X11

    if os.environ.get("WAYLAND_DISPLAY"):
        return SessionType.WAYLAND
    if os.environ.get("DISPLAY"):
        return SessionType.X11

    return SessionType.UNKNOWN
