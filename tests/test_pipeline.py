import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

from speech_typing.events import PipelineEvent
from speech_typing.exceptions import NoSpeechDetectedError
from speech_typing.pipeline import SpeechPipeline


def _make_pipeline(max_recording_duration_s=60, **kwargs):
    recorder = MagicMock()
    transcriber = MagicMock()
    typing_service = MagicMock()
    events = []
    lock = threading.Lock()

    def on_event(event, data):
        with lock:
            events.append((event, data))

    pipeline = SpeechPipeline(
        recorder=recorder,
        transcriber=transcriber,
        typing_service=typing_service,
        max_recording_duration_s=max_recording_duration_s,
        recording_store=MagicMock(),
        transcript_store=MagicMock(),
        on_event=on_event,
        **kwargs,
    )
    pipeline.start()
    return pipeline, recorder, transcriber, typing_service, events, lock


def _wait_for(events, lock, target_event, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with lock:
            if any(e is target_event for e, _ in events):
                return
        time.sleep(0.01)
    raise AssertionError(f"Timed out waiting for {target_event}")


def test_full_success_path(tmp_path):
    pipeline, recorder, transcriber, typing_service, events, lock = _make_pipeline()
    audio_path = tmp_path / "fake_recording.wav"
    audio_path.touch()
    recorder.stop.return_value = audio_path
    transcriber.transcribe.return_value = "hello world"
    typing_service.type_text.return_value = True

    pipeline.handle_hotkey_down("primary")
    recorder.start.assert_called_once()

    pipeline.handle_hotkey_up("primary")
    _wait_for(events, lock, PipelineEvent.COMPLETED)
    pipeline.shutdown()

    event_types = [e for e, _ in events]
    assert PipelineEvent.RECORDING_STARTED in event_types
    assert PipelineEvent.RECORDING_STOPPED in event_types
    assert PipelineEvent.TRANSCRIBING in event_types
    assert PipelineEvent.TYPING in event_types
    assert PipelineEvent.COMPLETED in event_types
    assert not audio_path.exists()  # cleaned up after processing


def test_short_recording_is_discarded_without_queuing_work():
    pipeline, recorder, transcriber, typing_service, events, lock = _make_pipeline()
    recorder.stop.return_value = None

    pipeline.handle_hotkey_down("primary")
    pipeline.handle_hotkey_up("primary")
    time.sleep(0.05)
    pipeline.shutdown()

    event_types = [e for e, _ in events]
    assert PipelineEvent.RECORDING_DISCARDED in event_types
    transcriber.transcribe.assert_not_called()


def test_second_hotkey_engaging_while_recording_is_ignored():
    pipeline, recorder, transcriber, typing_service, events, lock = _make_pipeline()
    recorder.stop.return_value = None

    pipeline.handle_hotkey_down("primary")
    pipeline.handle_hotkey_down("secondary")  # already recording; must be ignored
    recorder.start.assert_called_once()

    pipeline.handle_hotkey_up("secondary")  # doesn't match the active hotkey
    recorder.stop.assert_not_called()

    pipeline.handle_hotkey_up("primary")
    recorder.stop.assert_called_once()
    pipeline.shutdown()


def test_no_speech_detected_emits_event_not_error(tmp_path):
    pipeline, recorder, transcriber, typing_service, events, lock = _make_pipeline()
    audio_path = tmp_path / "fake_recording_no_speech.wav"
    audio_path.touch()
    recorder.stop.return_value = audio_path
    transcriber.transcribe.side_effect = NoSpeechDetectedError("nothing")

    pipeline.handle_hotkey_down("primary")
    pipeline.handle_hotkey_up("primary")
    _wait_for(events, lock, PipelineEvent.NO_SPEECH_DETECTED)
    pipeline.shutdown()

    typing_service.type_text.assert_not_called()


def test_max_duration_auto_stops_recording():
    pipeline, recorder, transcriber, typing_service, events, lock = _make_pipeline(
        max_recording_duration_s=0.05
    )
    recorder.stop.return_value = None

    pipeline.handle_hotkey_down("primary")
    _wait_for(events, lock, PipelineEvent.RECORDING_STOPPED, timeout=1.0)
    pipeline.shutdown()

    stopped_events = [data for e, data in events if e == PipelineEvent.RECORDING_STOPPED]
    assert any(d.get("reason") == "max_duration" for d in stopped_events)


def test_streaming_session_text_is_typed_once_on_release(tmp_path):
    session = MagicMock()
    session.finish.return_value = "hello streaming world"
    pipeline, recorder, transcriber, typing_service, events, lock = _make_pipeline(
        session_factory=lambda rec, on_text: session
    )
    audio_path = tmp_path / "rec.wav"
    audio_path.touch()
    recorder.stop.return_value = audio_path
    typing_service.type_text.return_value = True

    pipeline.handle_hotkey_down("primary")
    session.start.assert_called_once()
    pipeline.handle_hotkey_up("primary")
    _wait_for(events, lock, PipelineEvent.COMPLETED)
    pipeline.shutdown()

    transcriber.transcribe.assert_not_called()
    typing_service.type_text.assert_called_once_with("hello streaming world")


def test_streaming_failure_falls_back_to_whole_file(tmp_path):
    session = MagicMock()
    session.finish.side_effect = RuntimeError("server died")
    pipeline, recorder, transcriber, typing_service, events, lock = _make_pipeline(
        session_factory=lambda rec, on_text: session
    )
    audio_path = tmp_path / "rec.wav"
    audio_path.touch()
    recorder.stop.return_value = audio_path
    transcriber.transcribe.return_value = "fallback text"
    typing_service.type_text.return_value = True

    pipeline.handle_hotkey_down("primary")
    pipeline.handle_hotkey_up("primary")
    _wait_for(events, lock, PipelineEvent.COMPLETED)
    pipeline.shutdown()

    typing_service.type_text.assert_called_once_with("fallback text")


def test_discarded_recording_cancels_session():
    session = MagicMock()
    pipeline, recorder, *_ = _make_pipeline(session_factory=lambda rec, on_text: session)
    recorder.stop.return_value = None

    pipeline.handle_hotkey_down("primary")
    pipeline.handle_hotkey_up("primary")
    pipeline.shutdown()

    session.cancel.assert_called_once()
