from unittest.mock import MagicMock

import pytest

from speech_typing.exceptions import TypingAttemptFailedError, TypingBackendUnavailableError
from speech_typing.typing_service import TypingService


def test_succeeds_on_first_attempt():
    backend = MagicMock()
    service = TypingService(backend=backend, max_retries=3, retry_delay_s=0)

    assert service.type_text("hello") is True
    backend.type_text.assert_called_once_with("hello")


def test_retries_then_succeeds():
    backend = MagicMock()
    backend.type_text.side_effect = [TypingAttemptFailedError("nope"), None]
    service = TypingService(backend=backend, max_retries=3, retry_delay_s=0)

    assert service.type_text("hello") is True
    assert backend.type_text.call_count == 2


def test_falls_back_to_clipboard_after_exhausting_retries():
    backend = MagicMock()
    backend.type_text.side_effect = TypingAttemptFailedError("nope")
    clipboard = MagicMock()
    clipboard.is_available.return_value = True
    service = TypingService(backend=backend, max_retries=2, retry_delay_s=0, clipboard_fallback=clipboard)

    result = service.type_text("hello")

    assert result is False
    assert backend.type_text.call_count == 2
    clipboard.copy.assert_called_once_with("hello")


def test_raises_when_no_clipboard_fallback_available():
    backend = MagicMock()
    backend.type_text.side_effect = TypingAttemptFailedError("nope")
    service = TypingService(backend=backend, max_retries=2, retry_delay_s=0, clipboard_fallback=None)

    with pytest.raises(TypingBackendUnavailableError):
        service.type_text("hello")


def test_raises_when_clipboard_fallback_unavailable():
    backend = MagicMock()
    backend.type_text.side_effect = TypingAttemptFailedError("nope")
    clipboard = MagicMock()
    clipboard.is_available.return_value = False
    service = TypingService(backend=backend, max_retries=1, retry_delay_s=0, clipboard_fallback=clipboard)

    with pytest.raises(TypingBackendUnavailableError):
        service.type_text("hello")
    clipboard.copy.assert_not_called()
