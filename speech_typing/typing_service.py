"""Retry policy and clipboard-fallback wrapper around a TypingBackend.

Kept separate from the backends themselves: retry count/delay and the
decision to fall back to the clipboard are policy, not something any one
backend implementation should know about.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from .clipboard import ClipboardFallback
from .exceptions import TypingAttemptFailedError, TypingBackendUnavailableError
from .typing_backends import TypingBackend

logger = logging.getLogger(__name__)


class TypingService:
    """Types text via a backend, retrying transient failures before giving up."""

    def __init__(
        self,
        backend: TypingBackend,
        max_retries: int,
        retry_delay_s: float,
        clipboard_fallback: Optional[ClipboardFallback] = None,
    ) -> None:
        self._backend = backend
        self._max_retries = max_retries
        self._retry_delay_s = retry_delay_s
        self._clipboard_fallback = clipboard_fallback

    def type_text(self, text: str) -> bool:
        """Type text, retrying on failure. Returns False if it had to fall
        back to the clipboard instead of typing directly.
        """
        last_error: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                self._backend.type_text(text)
                return True
            except TypingAttemptFailedError as exc:
                last_error = exc
                logger.warning("Typing attempt %d/%d failed: %s", attempt, self._max_retries, exc)
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay_s)

        if self._clipboard_fallback is not None and self._clipboard_fallback.is_available():
            self._clipboard_fallback.copy(text)
            return False

        raise TypingBackendUnavailableError(
            f"Typing failed after {self._max_retries} attempts and no clipboard fallback is available."
        ) from last_error
