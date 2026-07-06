"""Start/stop sound cues via paplay (PipeWire's PulseAudio compat layer),
falling back to pw-play. Purely cosmetic: never fatal if unavailable.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SoundPlayer:
    def __init__(self, enabled: bool = True) -> None:
        self._player = shutil.which("paplay") or shutil.which("pw-play")
        self._available = enabled and self._player is not None
        if enabled and not self._available:
            logger.info("paplay/pw-play not found; sound cues disabled")

    def is_available(self) -> bool:
        return self._available

    def play(self, path: Optional[Path]) -> None:
        if not self._available or path is None or not path.is_file():
            return
        # Fire-and-forget: playback must never block the recording pipeline.
        try:
            subprocess.Popen(
                [self._player, str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            logger.debug("Failed to play sound cue %s: %s", path, exc)
