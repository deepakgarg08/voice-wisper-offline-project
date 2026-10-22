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
from .storage import DailyTranscriptStore, RecordingStore
from .chunker import SilenceChunker
from .speech import AudioRecorder, cleanup_stale_temp_files
from .streaming import StreamingSession
from .whisper_server import WhisperServerTranscriber
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
        self._typing_backend_name = backend.name
        self._print_configuration()

        clipboard = ClipboardFallback(session_type) if config.CLIPBOARD_FALLBACK_ENABLED else None
        self._typing_service = TypingService(
            backend=backend,
            max_retries=config.TYPING_MAX_RETRIES,
            retry_delay_s=config.TYPING_RETRY_DELAY_S,
            clipboard_fallback=clipboard,
        )

        self._notifier = Notifier(enabled=config.NOTIFICATIONS_ENABLED)
        self._sound = SoundPlayer(
            enabled=config.SOUND_EFFECTS_ENABLED,
            volume=config.SOUND_VOLUME,
        )

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
            mode=config.TRANSCRIPTION_MODE,
        )
        self._server = self._start_streaming_server()
        session_factory = self._make_session_factory() if self._server else None
        recording_store = RecordingStore(config.AUDIO_DIR, enabled=config.SAVE_AUDIO)
        transcript_store = DailyTranscriptStore(
            config.TRANSCRIPT_DIR, enabled=config.SAVE_TRANSCRIPT
        )
        self._pipeline = SpeechPipeline(
            recorder=recorder,
            transcriber=transcriber,
            typing_service=self._typing_service,
            max_recording_duration_s=config.MAX_RECORDING_DURATION_S,
            recording_store=recording_store,
            transcript_store=transcript_store,
            on_event=self._handle_pipeline_event,
            session_factory=session_factory,
            type_while_recording=config.STREAM_TYPE_WHILE_RECORDING,
        )

        self._hotkeys = HotkeyListener(
            hotkeys=config.HOTKEYS,
            debounce_ms=config.HOTKEY_DEBOUNCE_MS,
            on_engage=self._pipeline.handle_hotkey_down,
            on_disengage=self._pipeline.handle_hotkey_up,
            on_toggle=self._pipeline.handle_toggle,
        )

    def _start_streaming_server(self) -> Optional[WhisperServerTranscriber]:
        if not config.STREAMING_ENABLED:
            return None
        try:
            server = WhisperServerTranscriber(
                server_bin=config.WHISPER_SERVER,
                model_path=config.MODEL_PATH,
                language=config.LANGUAGE,
                translate=config.TRANSCRIPTION_MODE == "translate_en",
                threads=config.WHISPER_THREADS,
                sample_rate=config.SAMPLE_RATE,
                audio_ctx=config.STREAM_AUDIO_CTX,
            )
            server.start()
            return server
        except Exception as exc:
            logger.warning("Streaming ASR unavailable, using whisper-cli per utterance: %s", exc)
            return None

    def _make_session_factory(self):
        server = self._server

        def factory(recorder: AudioRecorder, on_text) -> StreamingSession:
            chunker = SilenceChunker(
                sample_rate=config.SAMPLE_RATE,
                min_chunk_s=config.STREAM_MIN_CHUNK_S,
                max_chunk_s=config.STREAM_MAX_CHUNK_S,
                silence_ms=config.STREAM_SILENCE_MS,
            )
            return StreamingSession(
                transcriber=server,
                chunker=chunker,
                get_audio=recorder.get_audio,
                on_text=on_text,
                use_prompt=config.STREAM_USE_PROMPT,
            )

        return factory

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

    def _print_configuration(self) -> None:
        mode_text = (
            "TRANSLATE TO ENGLISH"
            if config.TRANSCRIPTION_MODE == "translate_en"
            else "ORIGINAL SPOKEN LANGUAGE"
        )
        print("\n" + "=" * 72)
        print("SPEECH TYPING CONFIGURATION")
        print("=" * 72)
        print(f"Whisper model       : {config.MODEL}")
        print(f"Model file          : {config.MODEL_PATH}")
        print(f"Whisper language    : {config.LANGUAGE}")
        print(f"Transcription mode  : {config.TRANSCRIPTION_MODE} ({mode_text})")
        print(f"Streaming ASR       : {'ON' if config.STREAMING_ENABLED else 'OFF'}")
        print(f"Max recording       : {config.MAX_RECORDING_DURATION_S} seconds")
        print(f"Save audio          : {config.SAVE_AUDIO}")
        print(f"Save transcripts    : {config.SAVE_TRANSCRIPT}")
        print(f"Recordings folder   : {config.AUDIO_DIR}")
        print(f"Transcript folder   : {config.TRANSCRIPT_DIR}")
        print(f"Typing backend cfg  : {config.TYPING_BACKEND}")
        print(f"Typing backend used : {getattr(self, '_typing_backend_name', 'not selected yet')}")
        print(f"Clipboard fallback  : {config.CLIPBOARD_FALLBACK_ENABLED}")
        print(f"Project root       : {config.PROJECT_ROOT}")
        print(f"Toggle hotkey       : {'ON' if config.TOGGLE_HOTKEY_ENABLED else 'OFF'} (Right Ctrl)")
        print(f"Push-to-talk        : {'ON' if config.PUSH_TO_TALK_HOTKEY_ENABLED else 'OFF'} (Left Ctrl + Left Super)")
        print("=" * 72 + "\n", flush=True)

    def _handle_signal(self, signum: int, frame: Optional[FrameType]) -> None:
        logger.info("Received signal %s, shutting down gracefully", signum)
        self._hotkeys.stop()

    def _shutdown(self) -> None:
        logger.info("Shutting down...")
        self._pipeline.shutdown()
        if self._server is not None:
            self._server.stop()
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
            self._notifier.notify("Speech Typing", "Transcribing...")
        elif event is PipelineEvent.TYPING:
            logger.info("Typing text: %s", data.get("text"))
        elif event is PipelineEvent.COMPLETED:
            text = data.get("text") or ""
            logger.info("Completed")
            if text:
                logger.info("TRANSCRIPTION RESULT: %s", text)
                logger.debug("Transcript saved and typing completed")
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
