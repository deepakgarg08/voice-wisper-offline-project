"""Low-volume desktop sound effects for speech typing."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class SoundPlayer:
    """Play short desktop sounds through Fedora's audio stack.

    Prefer PipeWire's pw-play on Fedora, with paplay as a PulseAudio-
    compatibility fallback. Volume is controlled per playback.
    """

    def __init__(self, enabled: bool = True, volume: float = 0.15) -> None:
        self._enabled = enabled
        self._volume = max(0.0, min(1.0, float(volume)))

        # Fedora KDE normally has PipeWire, so prefer pw-play.
        self._player = (
            shutil.which("pw-play")
            or shutil.which("paplay")
            or shutil.which("ffplay")
        )

        if self._enabled:
            if self._player:
                logger.info(
                    "Sound player: %s (volume %.0f%%)",
                    self._player,
                    self._volume * 100,
                )
            else:
                logger.warning(
                    "No supported sound player found "
                    "(tried pw-play, paplay, ffplay)."
                )

    def play(self, path: Path) -> None:
        if not self._enabled or self._player is None:
            return

        if self._volume <= 0.0:
            return

        if not path.is_file():
            logger.warning("Sound file does not exist: %s", path)
            return

        try:
            player_name = Path(self._player).name

            if player_name == "pw-play":
                # PipeWire volume: 0.0 .. 1.0
                command = [
                    self._player,
                    f"--volume={self._volume:.3f}",
                    str(path),
                ]

            elif player_name == "paplay":
                # PulseAudio/PipeWire compatibility volume: 0 .. 65536
                volume = round(self._volume * 65536)
                command = [
                    self._player,
                    f"--volume={volume}",
                    str(path),
                ]

            else:
                # ffplay volume is expressed in percent.
                volume = round(self._volume * 100)
                command = [
                    self._player,
                    "-nodisp",
                    "-autoexit",
                    "-loglevel",
                    "quiet",
                    "-volume",
                    str(volume),
                    str(path),
                ]

            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        except OSError:
            logger.exception("Could not play sound: %s", path)
