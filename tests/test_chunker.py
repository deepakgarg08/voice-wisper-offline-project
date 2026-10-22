import numpy as np

from speech_typing.chunker import SilenceChunker

RATE = 16000


def _tone(seconds, amp=4000):
    t = np.arange(int(seconds * RATE)) / RATE
    return (amp * np.sin(2 * np.pi * 220 * t)).astype(np.int16)


def _quiet(seconds):
    return (np.random.default_rng(0).normal(0, 20, int(seconds * RATE))).astype(np.int16)


def _chunker():
    return SilenceChunker(RATE, min_chunk_s=2.0, max_chunk_s=8.0, silence_ms=400)


def test_waits_below_min_length():
    assert _chunker().decide(np.concatenate([_tone(1.0), _quiet(0.8)])) is None


def test_cuts_after_trailing_silence():
    audio = np.concatenate([_tone(2.5), _quiet(0.6)])
    decision = _chunker().decide(audio)
    assert decision is not None and decision.has_speech
    assert decision.cut == len(audio)


def test_keeps_waiting_during_continuous_speech():
    assert _chunker().decide(_tone(5.0)) is None


def test_force_only_ignores_pauses():
    audio = np.concatenate([_tone(2.5), _quiet(0.6)])
    assert _chunker().decide(audio, force_only=True) is None


def test_forced_cut_at_max_length_lands_in_quiet_spot():
    audio = np.concatenate([_tone(6.0), _quiet(0.1), _tone(2.5)])
    decision = _chunker().decide(audio)
    assert decision is not None and decision.has_speech
    assert 6.0 * RATE <= decision.cut <= 6.2 * RATE


def test_silent_chunk_is_flagged_as_no_speech():
    decision = _chunker().decide(_quiet(3.0))
    assert decision is not None and not decision.has_speech
