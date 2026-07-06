"""Entry point: listens for the hold-to-talk hotkey and orchestrates the
record -> transcribe -> type pipeline.
"""

from __future__ import annotations

import queue
import selectors
import threading
from pathlib import Path

from evdev import InputDevice, ecodes

from . import config
from .speech import AudioRecorder
from .transcribe import Transcriber
from .typer import TextTyper
from .utils import KeyboardAccessError, NoSpeechDetectedError, find_hotkey_capable_devices, setup_logging

logger = setup_logging(config.LOG_LEVEL)


class SpeechTypingApp:
    """Wires together hotkey detection, recording, transcription, and typing."""

    def __init__(self) -> None:
        self._recorder = AudioRecorder(
            sample_rate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            output_path=config.TEMP_AUDIO_FILE,
            min_duration_ms=config.MIN_RECORDING_DURATION_MS,
        )
        self._transcriber = Transcriber(
            whisper_cli=config.WHISPER_CLI,
            model_path=config.MODEL_PATH,
            language=config.LANGUAGE,
        )
        self._typer = TextTyper(
            backend=config.TYPING_BACKEND,
            key_delay_ms=config.YDOTOOL_KEY_DELAY_MS,
            socket_path=config.YDOTOOL_SOCKET,
        )

        self._devices = find_hotkey_capable_devices(config.HOTKEY)
        self._hotkey_code = getattr(ecodes, config.HOTKEY)

        self._work_queue: "queue.Queue[Path]" = queue.Queue()
        self._worker = threading.Thread(target=self._process_loop, daemon=True)

    def run(self) -> None:
        """Start the background worker and block, listening for the hotkey."""
        device_names = ", ".join(d.name for d in self._devices)
        logger.info("Listening for %s on: %s", config.HOTKEY, device_names)
        self._worker.start()

        selector = selectors.DefaultSelector()
        for device in self._devices:
            selector.register(device, selectors.EVENT_READ)

        try:
            while True:
                for key, _ in selector.select():
                    device: InputDevice = key.fileobj  # type: ignore[assignment]
                    for event in device.read():
                        self._handle_event(event)
        except KeyboardInterrupt:
            logger.info("Shutting down.")
        finally:
            for device in self._devices:
                device.close()

    def _handle_event(self, event) -> None:
        if event.type != ecodes.EV_KEY or event.code != self._hotkey_code:
            return

        if event.value == 1:  # key down
            self._recorder.start()
            logger.info("Recording started")
        elif event.value == 0:  # key up
            audio_path = self._recorder.stop()
            logger.info("Recording finished")
            if audio_path is None:
                logger.warning(
                    "Recording discarded (shorter than %d ms)",
                    config.MIN_RECORDING_DURATION_MS,
                )
                return
            self._work_queue.put(audio_path)

    def _process_loop(self) -> None:
        """Runs in a background thread so hotkey handling is never blocked."""
        while True:
            audio_path = self._work_queue.get()
            try:
                logger.info("Transcribing")
                text = self._transcriber.transcribe(audio_path)
                logger.info("Typing text: %s", text)
                self._typer.type_text(text)
                logger.info("Completed")
            except NoSpeechDetectedError:
                logger.warning("No speech detected, nothing to type")
            except Exception:
                logger.exception("Failed to process recording")
            finally:
                audio_path.unlink(missing_ok=True)


def main() -> None:
    try:
        app = SpeechTypingApp()
    except KeyboardAccessError as exc:
        logger.error(str(exc))
        return
    except Exception as exc:
        logger.error("Startup failed: %s", exc)
        return

    app.run()


if __name__ == "__main__":
    main()
