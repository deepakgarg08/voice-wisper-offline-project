"""Microphone recording, gated by explicit start()/stop() calls.

Recording is driven by a hold-to-talk hotkey rather than a fixed duration,
so capture is exposed as start/stop rather than a single blocking call.
"""

from __future__ import annotations

import glob
import os
import tempfile
from pathlib import Path
from typing import List, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf

from .exceptions import MicrophoneNotFoundError


def cleanup_stale_temp_files(directory: Path, filename_prefix: str) -> None:
    """Remove leftover recordings from a previous run that crashed before
    cleaning up after itself. Safe to call even if the directory is empty
    or doesn't exist yet.
    """
    directory.mkdir(parents=True, exist_ok=True)
    for path in glob.glob(str(directory / f"{filename_prefix}*.wav")):
        try:
            os.remove(path)
        except OSError:
            pass


class AudioRecorder:
    """Captures microphone audio into memory while active, then saves it to a
    uniquely-named file on disk -- avoids collisions if cleanup runs while a
    file is still being written, and makes stale-file cleanup unambiguous.
    """

    def __init__(
        self,
        sample_rate: int,
        channels: int,
        output_dir: Path,
        filename_prefix: str,
        min_duration_ms: int,
    ) -> None:
        self._sample_rate = sample_rate
        self._channels = channels
        self._output_dir = output_dir
        self._filename_prefix = filename_prefix
        self._min_duration_ms = min_duration_ms
        self._stream: Optional[sd.InputStream] = None
        self._frames: List[np.ndarray] = []
        self._recording = False
        self.last_audio: Optional[np.ndarray] = None  # full audio of the last stop()

        self._output_dir.mkdir(parents=True, exist_ok=True)
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

    def get_audio(self, start: int = 0) -> np.ndarray:
        """Mono int16 samples recorded so far, from sample index `start` on.

        Safe to call from another thread while recording.
        """
        frames = list(self._frames)
        if not frames:
            return np.zeros(0, dtype=np.int16)
        audio = np.concatenate(frames, axis=0).reshape(-1, self._channels)[:, 0]
        return audio[start:]

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
        """Stop capturing and write the result to a new uniquely-named file.

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
        self.last_audio = None

        if not self._frames:
            return None

        audio = np.concatenate(self._frames, axis=0)
        self.last_audio = audio.reshape(-1, self._channels)[:, 0]
        duration_ms = (len(audio) / self._sample_rate) * 1000
        if duration_ms < self._min_duration_ms:
            self.last_audio = None
            return None

        fd, path_str = tempfile.mkstemp(
            suffix=".wav", prefix=self._filename_prefix, dir=str(self._output_dir)
        )
        os.close(fd)
        output_path = Path(path_str)
        sf.write(str(output_path), audio, self._sample_rate, subtype="PCM_16")
        return output_path
