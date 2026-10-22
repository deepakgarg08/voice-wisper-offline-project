"""Long-lived whisper.cpp server: model stays loaded between utterances.

Spawning ``whisper-cli`` per utterance reloads the model every time; a warm
``whisper-server`` removes that cost and lets chunks be transcribed while the
user is still speaking.
"""

from __future__ import annotations

import io
import logging
import os
import re
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from .exceptions import (
    ModelNotFoundError,
    NoSpeechDetectedError,
    WhisperExecutableNotFoundError,
)

logger = logging.getLogger(__name__)

# whisper emits these for silence/noise; they are never real dictation.
_NOISE_TAG = re.compile(r"[\[(][^\])]{0,40}[\])]")
_JUNK = {"you", "thank you.", "thanks for watching!", "."}


def clean_text(raw: str) -> str:
    """Strip bracketed non-speech tags ([BLANK_AUDIO], (music)) and whitespace."""
    return re.sub(r"\s+", " ", _NOISE_TAG.sub(" ", raw)).strip()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _die_with_parent() -> None:
    """Ask the kernel to kill the server if this process dies (Linux)."""
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG
    except Exception:
        pass


class WhisperServerTranscriber:
    """Starts whisper-server and transcribes in-memory audio over HTTP."""

    def __init__(
        self,
        server_bin: Path,
        model_path: Path,
        language: str,
        translate: bool,
        threads: int,
        sample_rate: int,
        audio_ctx: int = 0,
        startup_timeout_s: float = 30.0,
        request_timeout_s: float = 20.0,
    ) -> None:
        if not server_bin.is_file() or not os.access(server_bin, os.X_OK):
            raise WhisperExecutableNotFoundError(f"whisper-server not found at: {server_bin}")
        if not model_path.is_file():
            raise ModelNotFoundError(f"Model file not found: {model_path}")
        self._server_bin = server_bin
        self._model_path = model_path
        self._language = language
        self._translate = translate
        self._threads = threads
        self._sample_rate = sample_rate
        self._audio_ctx = audio_ctx
        self._startup_timeout_s = startup_timeout_s
        self._request_timeout_s = request_timeout_s
        self._proc: Optional[subprocess.Popen] = None
        self._port = 0

    def start(self) -> None:
        self._port = _free_port()
        command = [
            str(self._server_bin),
            "-m", str(self._model_path),
            "-l", self._language,
            "-t", str(self._threads),
            "--host", "127.0.0.1",
            "--port", str(self._port),
            "-nf",   # no temperature fallback: it turns a noisy chunk into a 15 s stall
            "-sns",  # suppress non-speech tokens
        ]
        if self._translate:
            command.append("-tr")
        if self._audio_ctx > 0:
            # Encoder cost scales with audio context; chunks are short, so
            # shrinking it from the 30 s default makes each one far cheaper.
            command += ["-ac", str(self._audio_ctx)]
        self._proc = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=_die_with_parent if os.name == "posix" else None,
        )
        self._wait_until_ready()
        self._warm_up()
        logger.info("whisper-server ready on port %d", self._port)

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + self._startup_timeout_s
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError(f"whisper-server exited early (code {self._proc.returncode})")
            try:
                with socket.create_connection(("127.0.0.1", self._port), timeout=0.5):
                    return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("Timed out waiting for whisper-server to start")

    def _warm_up(self) -> None:
        """Run one dummy inference so the first real chunk isn't slow."""
        try:
            self._post(np.zeros(self._sample_rate, dtype=np.int16), prompt="")
        except Exception:
            logger.debug("whisper-server warm-up failed", exc_info=True)

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def transcribe_audio(self, audio: np.ndarray, prompt: str = "") -> str:
        """Transcribe int16 mono audio; raises NoSpeechDetectedError if empty."""
        text = clean_text(self._post(audio, prompt))
        if not text or text.lower() in _JUNK:
            raise NoSpeechDetectedError("No speech was detected.")
        return text

    def _post(self, audio: np.ndarray, prompt: str) -> str:
        wav = io.BytesIO()
        sf.write(wav, audio, self._sample_rate, format="WAV", subtype="PCM_16")
        boundary = uuid.uuid4().hex
        fields = {"temperature": "0.0", "response_format": "text"}
        if prompt:
            fields["prompt"] = prompt
        body = b""
        for name, value in fields.items():
            body += (
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
            ).encode()
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="chunk.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode() + wav.getvalue() + f"\r\n--{boundary}--\r\n".encode()
        request = urllib.request.Request(
            f"http://127.0.0.1:{self._port}/inference",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._request_timeout_s) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"whisper-server request failed: {exc}") from exc
