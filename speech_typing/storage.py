"""Persistent storage for recordings and daily transcript history."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


class RecordingStore:
    """Copies completed recordings into a permanent, date-organized folder."""

    def __init__(self, root: Path, enabled: bool) -> None:
        self._root = root
        self._enabled = enabled

    def archive(self, audio_path: Path) -> Path | None:
        if not self._enabled:
            return None

        now = datetime.now().astimezone()
        day_dir = self._root / now.strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        destination = day_dir / f"{now.strftime('%H-%M-%S_%f')}_{audio_path.name}"
        shutil.copy2(audio_path, destination)
        return destination


class DailyTranscriptStore:
    """Appends each successful transcription to one UTF-8 file per day."""

    def __init__(self, root: Path, enabled: bool) -> None:
        self._root = root
        self._enabled = enabled

    def append(self, text: str, *, audio_path: Path | None = None) -> Path | None:
        if not self._enabled:
            return None

        now = datetime.now().astimezone()
        self._root.mkdir(parents=True, exist_ok=True)
        destination = self._root / f"{now.strftime('%Y-%m-%d')}.txt"

        timestamp = now.strftime("%Y-%m-%d %H:%M:%S %Z")
        lines = [f"[{timestamp}]\n"]
        if audio_path is not None:
            lines.append(f"Audio: {audio_path}\n")
        lines.extend([text.strip(), "\n", "\n"])

        with destination.open("a", encoding="utf-8") as handle:
            handle.writelines(lines)

        return destination
