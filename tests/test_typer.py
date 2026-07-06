import pytest

from speech_typing.typer import TextTyper
from speech_typing.utils import TypingBackendUnavailableError

# Note: none of these tests call type_text() -- that would actually inject
# keystrokes into whatever window currently has focus on the machine
# running the suite. Only construction/validation is covered here; exercise
# actual typing manually (see README).


def test_unsupported_backend_raises():
    with pytest.raises(TypingBackendUnavailableError):
        TextTyper(backend="xdotool")


def test_missing_binary_raises(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(TypingBackendUnavailableError):
        TextTyper()


def test_ydotool_found_constructs_ok():
    TextTyper()
