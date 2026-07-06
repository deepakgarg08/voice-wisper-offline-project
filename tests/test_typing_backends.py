from unittest.mock import patch

import pytest

from speech_typing.environment import SessionType
from speech_typing.exceptions import TypingBackendUnavailableError
from speech_typing.typing_backends import (
    WtypeBackend,
    XdotoolBackend,
    YdotoolBackend,
    select_typing_backend,
)

# Note: none of these tests call type_text() -- that would actually inject
# keystrokes into whatever window currently has focus on the machine
# running the suite. Only construction/selection is covered here; exercise
# actual typing manually (see README).


def test_unknown_backend_name_raises():
    with pytest.raises(TypingBackendUnavailableError):
        select_typing_backend("made-up-backend", SessionType.X11)


def test_explicit_backend_raises_if_not_installed():
    with patch.object(XdotoolBackend, "is_available", return_value=False):
        with pytest.raises(TypingBackendUnavailableError):
            select_typing_backend("xdotool", SessionType.X11)


def test_auto_prefers_ydotool_when_available():
    with patch.object(YdotoolBackend, "is_available", return_value=True):
        backend = select_typing_backend("auto", SessionType.WAYLAND)
    assert backend.name == "ydotool"


def test_auto_falls_back_to_xdotool_on_x11_without_ydotool():
    with patch.object(YdotoolBackend, "is_available", return_value=False):
        with patch.object(XdotoolBackend, "is_available", return_value=True):
            backend = select_typing_backend("auto", SessionType.X11)
    assert backend.name == "xdotool"


def test_auto_falls_back_to_wtype_on_wayland_without_ydotool():
    with patch.object(YdotoolBackend, "is_available", return_value=False):
        with patch.object(WtypeBackend, "is_available", return_value=True):
            backend = select_typing_backend("auto", SessionType.WAYLAND)
    assert backend.name == "wtype"


def test_auto_raises_if_nothing_available():
    with patch.object(YdotoolBackend, "is_available", return_value=False):
        with patch.object(XdotoolBackend, "is_available", return_value=False):
            with patch.object(WtypeBackend, "is_available", return_value=False):
                with pytest.raises(TypingBackendUnavailableError):
                    select_typing_backend("auto", SessionType.X11)


def test_ydotool_is_actually_installed_here():
    # Verifies the real environment this suite runs in, not just mocks.
    assert YdotoolBackend.is_available()
