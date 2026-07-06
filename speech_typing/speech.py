"""Microphone recording, gated by explicit start()/stop() calls.

Recording is driven by a hold-to-talk hotkey rather than a fixed duration,
so capture is exposed as start/stop rather than a single blocking call.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf

from .utils import MicrophoneNotFoundError


class AudioRecorder:
    """Captures microphone audio into memory while active, then saves it to disk."""

    def __init__(
        self,
        sample_rate: int,
        channels: int,
        output_path: Path,
        min_duration_ms: int,
    ) -> None:
        self._sample_rate = sample_rate
        self._channels = channels
        self._output_path = output_path
        self._min_duration_ms = min_duration_ms
        self._stream: Optional[sd.InputStream] = None
        self._frames: List[np.ndarray] = []
        self._recording = False

        self._verify_microphone()

    def _verify_microphone(self) -> None:
        """Raise MicrophoneNotFoundError early if no input device is available."""
        try:
            device_info = sd.query_devices(kind="input")
        except sd.PortAudioError as exc:
            raise MicrophoneNotFoundError("No input audio device is available.") from exc
        if not device_info:
            raise MicrophoneNotFoundError("No default input audio device is configured.")

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        self._frames.append(indata.copy())

    def start(self) -> None:
        """Begin capturing audio. No-op if already recording."""
        if self._recording:
            return
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()
        self._recording = True

    def stop(self) -> Optional[Path]:
        """Stop capturing and write the result to disk.

        Returns the path to the saved WAV file, or None if there was nothing
        to save or the recording was shorter than the configured minimum
        duration (in which case it's discarded, not written).
        """
        if not self._recording or self._stream is None:
            return None

        self._stream.stop()
        self._stream.close()
        self._stream = None
        self._recording = False

        if not self._frames:
            return None

        audio = np.concatenate(self._frames, axis=0)
        duration_ms = (len(audio) / self._sample_rate) * 1000
        if duration_ms < self._min_duration_ms:
            return None

        sf.write(str(self._output_path), audio, self._sample_rate, subtype="PCM_16")
        return self._output_path
