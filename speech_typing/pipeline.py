"""Core record -> transcribe -> type business logic."""

from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .events import PipelineEvent
from .exceptions import NoSpeechDetectedError
from .speech import AudioRecorder
from .streaming import StreamingSession
from .storage import DailyTranscriptStore, RecordingStore
from .transcribe import Transcriber
from .typing_service import TypingService

logger = logging.getLogger(__name__)
StoppedRecording = tuple[Optional[Path], Optional[StreamingSession], Optional[np.ndarray]]
EventCallback = Callable[[PipelineEvent, dict], None]
# temp wav path, streaming session (if any), full audio captured at stop
QueuedRecording = tuple[Path, Optional[StreamingSession], Optional[np.ndarray]]


class SpeechPipeline:
    """Owns recording, transcription, typing, and persistent history."""

    def __init__(
        self,
        recorder: AudioRecorder,
        transcriber: Transcriber,
        typing_service: TypingService,
        max_recording_duration_s: float,
        recording_store: RecordingStore,
        transcript_store: DailyTranscriptStore,
        on_event: Optional[EventCallback] = None,
        session_factory: Optional[Callable[[AudioRecorder, Callable[[str], None]], StreamingSession]] = None,
        type_while_recording: bool = False,
    ) -> None:
        self._recorder = recorder
        self._transcriber = transcriber
        self._typing_service = typing_service
        self._max_recording_duration_s = max_recording_duration_s
        self._recording_store = recording_store
        self._transcript_store = transcript_store
        self._on_event = on_event or (lambda event, data: None)
        self._session_factory = session_factory
        self._type_while_recording = type_while_recording
        self._session: Optional[StreamingSession] = None
        self._live_typed = False

        self._lock = threading.Lock()
        self._recording_hotkey: Optional[str] = None
        self._max_duration_timer: Optional[threading.Timer] = None

        self._queue: "queue.Queue[Optional[QueuedRecording]]" = queue.Queue()
        self._worker = threading.Thread(
            target=self._process_loop, name="speech-pipeline-worker", daemon=True
        )

    def start(self) -> None:
        self._worker.start()

    def shutdown(self, timeout_s: float = 5.0) -> None:
        with self._lock:
            hotkey_name = self._recording_hotkey
            stopped = self._stop_recording_locked() if hotkey_name is not None else None
        if stopped is not None:
            self._finish_recording(hotkey_name, stopped)
        self._queue.put(None)
        if self._worker.is_alive():
            self._worker.join(timeout=timeout_s)

    def handle_hotkey_down(self, hotkey_name: str) -> None:
        self._start_recording(hotkey_name)

    def handle_toggle(self, hotkey_name: str) -> None:
        logger.info("Toggle hotkey pressed (recording=%s)", self._recording_hotkey is not None)
        with self._lock:
            if self._recording_hotkey is None:
                should_start = True
            elif self._recording_hotkey == hotkey_name:
                should_start = False
                stopped = self._stop_recording_locked()
            else:
                return

        if should_start:
            self._start_recording(hotkey_name)
        else:
            self._finish_recording(hotkey_name, stopped)

    def handle_hotkey_up(self, hotkey_name: str) -> None:
        with self._lock:
            if self._recording_hotkey != hotkey_name:
                return
            stopped = self._stop_recording_locked()
        self._finish_recording(hotkey_name, stopped)

    def _start_recording(self, hotkey_name: str) -> None:
        with self._lock:
            if self._recording_hotkey is not None:
                return
            self._recording_hotkey = hotkey_name
            self._recorder.start()
            self._live_typed = False
            if self._session_factory is not None:
                self._session = self._session_factory(self._recorder, self._on_stream_text)
                self._session.start()
            if self._max_recording_duration_s > 0:
                timer = threading.Timer(
                    self._max_recording_duration_s, self._on_max_duration_reached
                )
                timer.daemon = True
                timer.start()
                self._max_duration_timer = timer
        self._on_event(PipelineEvent.RECORDING_STARTED, {"hotkey": hotkey_name})

    def _on_stream_text(self, text: str) -> None:
        # Runs on the stream worker thread as each chunk is recognised.
        if self._type_while_recording:
            self._live_typed = True
            self._typing_service.type_text(text + " ")

    def _finish_recording(
        self, hotkey_name: str, stopped: StoppedRecording, reason: Optional[str] = None
    ) -> None:
        audio_path, session, audio = stopped
        self._on_event(
            PipelineEvent.RECORDING_STOPPED, {"hotkey": hotkey_name, "reason": reason}
        )
        if audio_path is None:
            if session is not None:
                session.cancel()
            self._on_event(PipelineEvent.RECORDING_DISCARDED, {"hotkey": hotkey_name})
            return

        # Queue first so the tail starts transcribing immediately; archiving
        # happens on the worker thread afterwards.
        self._queue.put((audio_path, session, audio))

    def _on_max_duration_reached(self) -> None:
        with self._lock:
            hotkey_name = self._recording_hotkey
            if hotkey_name is None:
                return
            stopped = self._stop_recording_locked()
        logger.warning("Max recording duration reached, stopping automatically")
        self._finish_recording(hotkey_name, stopped, reason="max_duration")

    def _stop_recording_locked(self) -> StoppedRecording:
        if self._max_duration_timer is not None:
            self._max_duration_timer.cancel()
            self._max_duration_timer = None
        self._recording_hotkey = None
        session, self._session = self._session, None
        audio_path = self._recorder.stop()
        audio = getattr(self._recorder, "last_audio", None) if session is not None else None
        return audio_path, session, audio

    def _process_loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return

            audio_path, session, audio = item
            archived_path: Optional[Path] = None
            archived = False
            try:
                self._on_event(PipelineEvent.TRANSCRIBING, {})
                text = self._transcribe(audio_path, session, audio)
                archived_path = self._archive(audio_path)
                archived = True

                transcript_path = self._transcript_store.append(
                    text, audio_path=archived_path
                )
                self._on_event(
                    PipelineEvent.TYPING,
                    {"text": text, "transcript_path": transcript_path},
                )
                if self._live_typed:
                    typed_directly = True  # already typed chunk by chunk
                else:
                    typed_directly = self._typing_service.type_text(text)
                if typed_directly:
                    self._on_event(PipelineEvent.COMPLETED, {"text": text})
                else:
                    self._on_event(
                        PipelineEvent.TYPING_FAILED_CLIPBOARD_FALLBACK,
                        {"text": text},
                    )
            except NoSpeechDetectedError:
                self._on_event(PipelineEvent.NO_SPEECH_DETECTED, {})
            except Exception as exc:
                logger.exception("Failed to process recording")
                self._on_event(PipelineEvent.ERROR, {"error": str(exc)})
            finally:
                if not archived:
                    self._archive(audio_path)  # keep recordings even when nothing was typed
                audio_path.unlink(missing_ok=True)

    def _transcribe(
        self, audio_path: Path, session: Optional[StreamingSession], audio: Optional[np.ndarray]
    ) -> str:
        if session is None:
            return self._transcriber.transcribe(audio_path)
        try:
            return session.finish(audio)
        except NoSpeechDetectedError:
            raise
        except Exception:
            logger.exception("Streaming transcription failed, falling back to whole-file")
            return self._transcriber.transcribe(audio_path)

    def _archive(self, audio_path: Path) -> Optional[Path]:
        try:
            return self._recording_store.archive(audio_path)
        except Exception as exc:
            logger.exception("Failed to archive recording")
            self._on_event(PipelineEvent.ERROR, {"error": f"Could not save recording: {exc}"})
            return None
