from speech_typing.environment import SessionType, detect_session_type


def test_xdg_session_type_wayland(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    assert detect_session_type() is SessionType.WAYLAND


def test_xdg_session_type_x11(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    assert detect_session_type() is SessionType.X11


def test_falls_back_to_wayland_display(monkeypatch):
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.delenv("DISPLAY", raising=False)
    assert detect_session_type() is SessionType.WAYLAND


def test_falls_back_to_display(monkeypatch):
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    assert detect_session_type() is SessionType.X11


def test_unknown_when_nothing_set(monkeypatch):
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    assert detect_session_type() is SessionType.UNKNOWN
