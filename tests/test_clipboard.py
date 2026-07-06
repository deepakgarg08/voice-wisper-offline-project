from unittest.mock import patch

from speech_typing.clipboard import ClipboardFallback
from speech_typing.environment import SessionType


def test_wayland_available_when_wl_copy_present():
    with patch("shutil.which", side_effect=lambda name: "/usr/bin/wl-copy" if name == "wl-copy" else None):
        assert ClipboardFallback(SessionType.WAYLAND).is_available()


def test_x11_available_when_xclip_present():
    with patch("shutil.which", side_effect=lambda name: "/usr/bin/xclip" if name == "xclip" else None):
        assert ClipboardFallback(SessionType.X11).is_available()


def test_unavailable_when_nothing_installed():
    with patch("shutil.which", return_value=None):
        assert not ClipboardFallback(SessionType.WAYLAND).is_available()
        assert not ClipboardFallback(SessionType.X11).is_available()


def test_copy_uses_wl_copy_on_wayland():
    with patch("shutil.which", side_effect=lambda name: "/usr/bin/wl-copy" if name == "wl-copy" else None):
        with patch("subprocess.run") as run:
            ClipboardFallback(SessionType.WAYLAND).copy("hello")
    run.assert_called_once()
    assert run.call_args.args[0] == ["wl-copy"]
    assert run.call_args.kwargs["input"] == "hello"
