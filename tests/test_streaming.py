import time

import numpy as np
import pytest

from speech_typing.chunker import SilenceChunker
from speech_typing.exceptions import NoSpeechDetectedError
from speech_typing.streaming import StreamingSession
from speech_typing.whisper_server import clean_text

RATE = 16000


def _tone(seconds):
    t = np.arange(int(seconds * RATE)) / RATE
    return (4000 * np.sin(2 * np.pi * 220 * t)).astype(np.int16)


def _quiet(seconds):
    return np.zeros(int(seconds * RATE), dtype=np.int16)


class FakeTranscriber:
    def __init__(self):
        self.calls = []

    def transcribe_audio(self, audio, prompt=""):
        self.calls.append((len(audio), prompt))
        return f"part{len(self.calls)}"


def _session(audio, transcriber, texts):
    chunker = SilenceChunker(RATE, 2.0, 8.0, 400)
    return StreamingSession(
        transcriber, chunker, lambda start: audio[start:], texts.append
    )


def test_chunks_are_transcribed_in_order_and_tail_flushed():
    first = np.concatenate([_tone(2.5), _quiet(0.6)])
    audio = np.concatenate([first, _tone(1.0)])
    live = [first]  # what the recorder has captured so far
    fake, texts = FakeTranscriber(), []
    chunker = SilenceChunker(RATE, 2.0, 8.0, 400)
    session = StreamingSession(fake, chunker, lambda start: live[0][start:], texts.append)
    session.start()
    time.sleep(0.6)  # feeder cuts the first chunk at the pause
    live[0] = audio
    result = session.finish(audio)

    assert result == "part1 part2"
    assert texts == ["part1", "part2"]
    assert fake.calls[1][1] == "part1"  # previous text passed as prompt


def test_silent_recording_raises_no_speech():
    audio = _quiet(3.0)
    session = _session(audio, FakeTranscriber(), [])
    session.start()
    with pytest.raises(NoSpeechDetectedError):
        session.finish(audio)


def test_transcriber_error_propagates():
    class Broken:
        def transcribe_audio(self, audio, prompt=""):
            raise RuntimeError("boom")

    audio = _tone(2.5)
    session = _session(audio, Broken(), [])
    session.start()
    with pytest.raises(RuntimeError):
        session.finish(audio)


def test_clean_text_strips_non_speech_tags():
    assert clean_text(" [BLANK_AUDIO] hello  (music) world ") == "hello world"
    assert clean_text("[BLANK_AUDIO]") == ""
