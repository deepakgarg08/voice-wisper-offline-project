"""Silence-aware cut-point detection for streaming transcription.

Pure numpy logic: given the not-yet-cut tail of a recording, decide whether it
should be sent for transcription now. Cutting on pauses keeps words intact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

WINDOW_MS = 30


@dataclass(frozen=True)
class ChunkDecision:
    cut: int  # number of leading samples to consume
    has_speech: bool  # False -> drop them instead of transcribing


def window_rms(audio: np.ndarray, window: int) -> np.ndarray:
    """RMS of consecutive non-overlapping windows (int16 scale)."""
    n = len(audio) // window
    if n == 0:
        return np.zeros(0)
    frames = audio[: n * window].astype(np.float32).reshape(n, window)
    return np.sqrt((frames ** 2).mean(axis=1))


class SilenceChunker:
    def __init__(
        self,
        sample_rate: int,
        min_chunk_s: float,
        max_chunk_s: float,
        silence_ms: int,
        min_threshold: float = 40.0,
        max_threshold: float = 1500.0,
    ) -> None:
        self.sample_rate = sample_rate
        self._rate = sample_rate
        self._window = max(1, sample_rate * WINDOW_MS // 1000)
        self._min = int(min_chunk_s * sample_rate)
        self._max = int(max_chunk_s * sample_rate)
        self._silence_windows = max(1, silence_ms // WINDOW_MS)
        self._min_threshold = min_threshold
        self._max_threshold = max_threshold

    def threshold(self, rms: np.ndarray) -> float:
        if len(rms) == 0:
            return self._min_threshold
        floor = float(np.percentile(rms, 10))
        return min(self._max_threshold, max(self._min_threshold, floor * 1.6))

    def has_speech(self, audio: np.ndarray) -> bool:
        rms = window_rms(audio, self._window)
        return bool(len(rms)) and bool((rms > self.threshold(rms)).any())

    def decide(self, audio: np.ndarray, force_only: bool = False) -> Optional[ChunkDecision]:
        """Return a decision for the pending audio, or None to keep waiting.

        With force_only, pauses are ignored and only the max-length cut applies.
        """
        if len(audio) < self._min:
            return None
        rms = window_rms(audio, self._window)
        loud = rms > self.threshold(rms)

        if (
            not force_only
            and len(loud) >= self._silence_windows
            and not loud[-self._silence_windows:].any()
        ):
            return ChunkDecision(len(audio), bool(loud.any()))

        if len(audio) >= self._max:
            # Force a cut at the quietest window in the final third.
            start = len(rms) * 2 // 3
            cut_window = start + int(np.argmin(rms[start:]))
            cut = (cut_window + 1) * self._window
            return ChunkDecision(cut, bool(loud[:cut_window + 1].any()))
        return None
