"""Wraps the whisper.cpp CLI to produce clean transcribed text."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .exceptions import ModelNotFoundError, NoSpeechDetectedError, WhisperExecutableNotFoundError


class Transcriber:
    """Runs whisper.cpp's whisper-cli binary and extracts plain transcribed text."""

    def __init__(self, whisper_cli: Path, model_path: Path, language: str, mode: str = "original") -> None:
        if not whisper_cli.is_file() or not os.access(whisper_cli, os.X_OK):
            raise WhisperExecutableNotFoundError(
                f"whisper-cli executable not found or not executable at: {whisper_cli}"
            )
        if not model_path.is_file():
            raise ModelNotFoundError(f"Model file not found: {model_path}")

        self._whisper_cli = whisper_cli
        self._model_path = model_path
        if mode not in ("original", "translate_en"):
            raise ValueError("mode must be 'original' or 'translate_en'")
        self._language = language
        self._mode = mode

    def transcribe(self, audio_path: Path) -> str:
        """Run whisper.cpp on the given WAV file and return clean transcribed text.

        Uses -nt/-np so stdout contains nothing but the transcription (no
        timestamps, no progress/meta output, which whisper.cpp writes to
        stderr instead).
        """
        command = [
                str(self._whisper_cli),
                "-m", str(self._model_path),
                "-f", str(audio_path),
                "-l", self._language,
                "-nt",
                "-np",
            ]
        if self._mode == "translate_en":
            command.append("-tr")

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"whisper-cli failed (exit {result.returncode}): {result.stderr.strip()}"
            )

        text = result.stdout.strip()
        if not text:
            raise NoSpeechDetectedError("No speech was detected in the recording.")

        return text
