"""Events emitted by SpeechPipeline. Consumed by the presentation layer
(app.py's notifications/sound/logging) so the pipeline's business logic
never has to import anything UI-related directly.
"""

from __future__ import annotations

from enum import Enum, auto


class PipelineEvent(Enum):
    RECORDING_STARTED = auto()
    RECORDING_STOPPED = auto()
    RECORDING_DISCARDED = auto()
    TRANSCRIBING = auto()
    TYPING = auto()
    COMPLETED = auto()
    TYPING_FAILED_CLIPBOARD_FALLBACK = auto()
    NO_SPEECH_DETECTED = auto()
    ERROR = auto()
