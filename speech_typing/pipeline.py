"""Core record -> transcribe -> type business logic.

Deliberately has no knowledge of notifications, sounds, or logging output
choices -- it only reports what happened via an injected on_event callback.
That keeps this module UI-agnostic and testable with a plain callback stub.
"""

from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path
from typing import Callable, Optional

from .events import PipelineEvent
from .exceptions import NoSpeechDetectedError
from .speech import AudioRecorder
from .transcribe import Transcriber
from .typing_service import TypingService

logger = logging.getLogger(__name__)

EventCallback = Callable[[PipelineEvent, dict], None]


class SpeechPipeline:
    """Owns recording, transcription, and typing; does the work off the
    calling thread so hotkey handling is never blocked by transcription.
    """

    def __init__(
        self,
        recorder: AudioRecorder,
        transcriber: Transcriber,
        typing_service: TypingService,
        max_recording_duration_s: float,
        on_event: Optional[EventCallback] = None,
    ) -> None:
        self._recorder = recorder
        self._transcriber = transcriber
        self._typing_service = typing_service
        self._max_recording_duration_s = max_recording_duration_s
        self._on_event = on_event or (lambda event, data: None)

        self._lock = threading.Lock()
        self._recording_hotkey: Optional[str] = None
        self._max_duration_timer: Optional[threading.Timer] = None

        self._queue: "queue.Queue[Optional[Path]]" = queue.Queue()
        self._worker = threading.Thread(
            target=self._process_loop, name="speech-pipeline-worker", daemon=True
        )

    def start(self) -> None:
        self._worker.start()

    def shutdown(self, timeout_s: float = 5.0) -> None:
        """Stop any in-progress recording and wait for the current job to finish."""
        with self._lock:
            if self._recording_hotkey is not None:
                self._stop_recording_locked()
        self._queue.put(None)  # sentinel to unblock the worker
        self._worker.join(timeout=timeout_s)

    def handle_hotkey_down(self, hotkey_name: str) -> None:
        with self._lock:
            if self._recording_hotkey is not None:
                return  # already recording; ignore a second hotkey engaging
            self._recording_hotkey = hotkey_name
            self._recorder.start()
            if self._max_recording_duration_s > 0:
                timer = threading.Timer(self._max_recording_duration_s, self._on_max_duration_reached)
                timer.daemon = True
                timer.start()
                self._max_duration_timer = timer
        self._on_event(PipelineEvent.RECORDING_STARTED, {"hotkey": hotkey_name})

    def handle_hotkey_up(self, hotkey_name: str) -> None:
        with self._lock:
            if self._recording_hotkey != hotkey_name:
                return
            audio_path = self._stop_recording_locked()
        self._on_event(PipelineEvent.RECORDING_STOPPED, {"hotkey": hotkey_name})
        if audio_path is None:
            self._on_event(PipelineEvent.RECORDING_DISCARDED, {"hotkey": hotkey_name})
            return
        self._queue.put(audio_path)

    def _on_max_duration_reached(self) -> None:
        with self._lock:
            hotkey_name = self._recording_hotkey
            if hotkey_name is None:
                return
            audio_path = self._stop_recording_locked()
        logger.warning("Max recording duration reached, stopping automatically")
        self._on_event(
            PipelineEvent.RECORDING_STOPPED, {"hotkey": hotkey_name, "reason": "max_duration"}
        )
        if audio_path is not None:
            self._queue.put(audio_path)

    def _stop_recording_locked(self) -> Optional[Path]:
        """Caller must hold self._lock."""
        if self._max_duration_timer is not None:
            self._max_duration_timer.cancel()
            self._max_duration_timer = None
        self._recording_hotkey = None
        return self._recorder.stop()

    def _process_loop(self) -> None:
        while True:
            audio_path = self._queue.get()
            if audio_path is None:
                return  # shutdown sentinel
            try:
                self._on_event(PipelineEvent.TRANSCRIBING, {})
                text = self._transcriber.transcribe(audio_path)
                self._on_event(PipelineEvent.TYPING, {"text": text})
                typed_directly = self._typing_service.type_text(text)
                if typed_directly:
                    self._on_event(PipelineEvent.COMPLETED, {"text": text})
                else:
                    self._on_event(PipelineEvent.TYPING_FAILED_CLIPBOARD_FALLBACK, {"text": text})
            except NoSpeechDetectedError:
                self._on_event(PipelineEvent.NO_SPEECH_DETECTED, {})
            except Exception as exc:
                logger.exception("Failed to process recording")
                self._on_event(PipelineEvent.ERROR, {"error": str(exc)})
            finally:
                audio_path.unlink(missing_ok=True)
