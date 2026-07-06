"""Composition root: wires config, session detection, backends, the
pipeline, and hotkeys together, and owns the process lifecycle (startup,
signal handling, graceful shutdown).

This is the one module allowed to depend on everything else -- individual
modules (pipeline, typing_backends, notifications, ...) don't know about
each other except through interfaces passed in here.
"""

from __future__ import annotations

import logging
import signal
from types import FrameType
from typing import Optional

from . import config
from .clipboard import ClipboardFallback
from .environment import detect_session_type
from .events import PipelineEvent
from .hotkeys import HotkeyListener
from .notifications import Notifier
from .pipeline import SpeechPipeline
from .sound import SoundPlayer
from .speech import AudioRecorder, cleanup_stale_temp_files
from .transcribe import Transcriber
from .typing_backends import select_typing_backend
from .typing_service import TypingService

logger = logging.getLogger(__name__)


class Application:
    """Owns the full process lifecycle: setup, run, graceful shutdown."""

    def __init__(self) -> None:
        config.validate()
        cleanup_stale_temp_files(config.TEMP_AUDIO_DIR, config.TEMP_AUDIO_PREFIX)

        session_type = detect_session_type()
        logger.info("Detected session type: %s", session_type.value)

        backend = select_typing_backend(
            preference=config.TYPING_BACKEND,
            session_type=session_type,
            socket_path=config.YDOTOOL_SOCKET,
            key_delay_ms=config.YDOTOOL_KEY_DELAY_MS,
        )
        logger.info("Using typing backend: %s", backend.name)

        clipboard = ClipboardFallback(session_type) if config.CLIPBOARD_FALLBACK_ENABLED else None
        self._typing_service = TypingService(
            backend=backend,
            max_retries=config.TYPING_MAX_RETRIES,
            retry_delay_s=config.TYPING_RETRY_DELAY_S,
            clipboard_fallback=clipboard,
        )

        self._notifier = Notifier(enabled=config.NOTIFICATIONS_ENABLED)
        self._sound = SoundPlayer(enabled=config.SOUND_EFFECTS_ENABLED)

        recorder = AudioRecorder(
            sample_rate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            output_dir=config.TEMP_AUDIO_DIR,
            filename_prefix=config.TEMP_AUDIO_PREFIX,
            min_duration_ms=config.MIN_RECORDING_DURATION_MS,
        )
        transcriber = Transcriber(
            whisper_cli=config.WHISPER_CLI,
            model_path=config.MODEL_PATH,
            language=config.LANGUAGE,
        )
        self._pipeline = SpeechPipeline(
            recorder=recorder,
            transcriber=transcriber,
            typing_service=self._typing_service,
            max_recording_duration_s=config.MAX_RECORDING_DURATION_S,
            on_event=self._handle_pipeline_event,
        )

        self._hotkeys = HotkeyListener(
            hotkeys=config.HOTKEYS,
            debounce_ms=config.HOTKEY_DEBOUNCE_MS,
            on_engage=self._pipeline.handle_hotkey_down,
            on_disengage=self._pipeline.handle_hotkey_up,
        )

    def run(self) -> None:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        self._pipeline.start()
        logger.info("speech_typing ready.")
        self._notifier.notify("Speech Typing", "Ready")

        try:
            self._hotkeys.listen_forever()
        finally:
            self._shutdown()

    def _handle_signal(self, signum: int, frame: Optional[FrameType]) -> None:
        logger.info("Received signal %s, shutting down gracefully", signum)
        self._hotkeys.stop()

    def _shutdown(self) -> None:
        logger.info("Shutting down...")
        self._pipeline.shutdown()
        logger.info("Shutdown complete.")

    def _handle_pipeline_event(self, event: PipelineEvent, data: dict) -> None:
        if event is PipelineEvent.RECORDING_STARTED:
            logger.info("Recording started (%s)", data.get("hotkey"))
            self._notifier.notify("Speech Typing", "Recording...")
            self._sound.play(config.SOUND_RECORDING_START)
        elif event is PipelineEvent.RECORDING_STOPPED:
            logger.info("Recording finished (%s)", data.get("hotkey"))
            self._sound.play(config.SOUND_RECORDING_STOP)
        elif event is PipelineEvent.RECORDING_DISCARDED:
            logger.warning(
                "Recording discarded (shorter than %d ms)", config.MIN_RECORDING_DURATION_MS
            )
        elif event is PipelineEvent.TRANSCRIBING:
            logger.info("Transcribing")
        elif event is PipelineEvent.TYPING:
            logger.info("Typing text: %s", data.get("text"))
        elif event is PipelineEvent.COMPLETED:
            logger.info("Completed")
        elif event is PipelineEvent.TYPING_FAILED_CLIPBOARD_FALLBACK:
            logger.warning("Typing failed, copied to clipboard instead")
            self._notifier.notify(
                "Speech Typing", "Typing failed - copied to clipboard instead", urgency="critical"
            )
        elif event is PipelineEvent.NO_SPEECH_DETECTED:
            logger.warning("No speech detected, nothing to type")
        elif event is PipelineEvent.ERROR:
            logger.error("Pipeline error: %s", data.get("error"))
            self._notifier.notify("Speech Typing", f"Error: {data.get('error')}", urgency="critical")
