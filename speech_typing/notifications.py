"""Desktop notifications via notify-send. Purely cosmetic: never fatal, never
raises if notify-send is missing or fails -- dictation must work without it.
"""

from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, enabled: bool = True, app_name: str = "Speech Typing") -> None:
        self._app_name = app_name
        self._available = enabled and shutil.which("notify-send") is not None
        if enabled and not self._available:
            logger.info("notify-send not found; desktop notifications disabled")

    def is_available(self) -> bool:
        return self._available

    def notify(self, title: str, message: str = "", urgency: str = "normal") -> None:
        if not self._available:
            return
        try:
            subprocess.run(
                ["notify-send", "--app-name", self._app_name, "--urgency", urgency, title, message],
                check=True,
                capture_output=True,
                timeout=2,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            logger.debug("notify-send failed: %s", exc)
