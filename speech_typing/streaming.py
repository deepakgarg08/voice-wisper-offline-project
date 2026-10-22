"""Transcribe chunks of a recording in the background while the user speaks.

A feeder thread watches the growing recording, cuts it at pauses (see
``chunker``) and hands chunks to a single worker that calls the warm
transcriber in order. When recording stops only the short unsent tail is left,
so the user waits for roughly one small chunk instead of the whole utterance.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, List, Optional

import numpy as np

from .chunker import SilenceChunker
from .exceptions import NoSpeechDetectedError

logger = logging.getLogger(__name__)
PROMPT_CHARS = 200
POLL_S = 0.15


class StreamingSession:
    """One recording's worth of streaming transcription."""

    def __init__(
        self,
        transcriber,
        chunker: SilenceChunker,
        get_audio: Callable[[int], np.ndarray],
        on_text: Callable[[str], None],
        use_prompt: bool = True,
    ) -> None:
        self._transcriber = transcriber
        self._chunker = chunker
        self._get_audio = get_audio  # get_audio(start) -> samples from `start` on
        self._on_text = on_text
        self._use_prompt = use_prompt

        self._cursor = 0
        self._outstanding = 0  # chunks queued or being transcribed
        self._count_lock = threading.Lock()
        self._texts: List[str] = []
        self._error: Optional[Exception] = None
        self._stop = threading.Event()
        self._jobs: "queue.Queue[Optional[np.ndarray]]" = queue.Queue()
        self._feeder = threading.Thread(target=self._feed, name="stream-feeder", daemon=True)
        self._worker = threading.Thread(target=self._work, name="stream-worker", daemon=True)

    def start(self) -> None:
        self._feeder.start()
        self._worker.start()

    def _feed(self) -> None:
        while not self._stop.wait(POLL_S):
            pending = self._get_audio(self._cursor)
            # While the worker is busy keep growing the pending chunk (more
            # context, no backlog) unless it hits the forced max length.
            decision = self._chunker.decide(pending, force_only=self._outstanding > 0)
            if decision is None:
                continue
            chunk = pending[: decision.cut]
            self._cursor += decision.cut
            if decision.has_speech:
                self._submit(chunk)

    def _submit(self, chunk: np.ndarray) -> None:
        with self._count_lock:
            self._outstanding += 1
        self._jobs.put(chunk)

    def _work(self) -> None:
        while True:
            chunk = self._jobs.get()
            if chunk is None:
                return
            try:
                self._process(chunk)
            finally:
                with self._count_lock:
                    self._outstanding -= 1

    def _process(self, chunk: np.ndarray) -> None:
        if self._error is not None:
            return
        prompt = ""
        if self._use_prompt and self._texts:
            prompt = " ".join(self._texts)[-PROMPT_CHARS:]
        started = time.perf_counter()
        try:
            text = self._transcriber.transcribe_audio(chunk, prompt)
        except NoSpeechDetectedError:
            return
        except Exception as exc:
            logger.exception("Chunk transcription failed")
            self._error = exc
            return
        logger.info(
            "Chunk %.1fs transcribed in %.2fs", len(chunk) / self._chunker.sample_rate, time.perf_counter() - started
        )
        self._texts.append(text)
        self._on_text(text)

    def finish(self, all_audio: Optional[np.ndarray]) -> str:
        """Stop feeding, transcribe the unsent tail, return the full text.

        Raises NoSpeechDetectedError if nothing was recognised, or the first
        transcription error encountered.
        """
        self._stop.set()
        self._feeder.join()
        if all_audio is not None:
            tail = all_audio[self._cursor:]
            if len(tail) and self._chunker.has_speech(tail):
                self._submit(tail)
        self._jobs.put(None)
        self._worker.join()
        if self._error is not None:
            raise self._error
        if not self._texts:
            raise NoSpeechDetectedError("No speech was detected in the recording.")
        return " ".join(self._texts)

    def cancel(self) -> None:
        self._stop.set()
        self._feeder.join()
        self._jobs.put(None)
        self._worker.join()
