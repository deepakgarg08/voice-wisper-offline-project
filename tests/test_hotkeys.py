from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from evdev import ecodes

from speech_typing.exceptions import KeyboardAccessError
from speech_typing.hotkeys import HotkeyListener, HotkeySpec, find_keyboard_devices


def _event(code, value):
    return SimpleNamespace(type=ecodes.EV_KEY, code=code, value=value)


def _make_listener(hotkeys, debounce_ms=0):
    engaged = []
    disengaged = []
    with patch("speech_typing.hotkeys.find_keyboard_devices", return_value=[]):
        listener = HotkeyListener(
            hotkeys=hotkeys,
            debounce_ms=debounce_ms,
            on_engage=engaged.append,
            on_disengage=disengaged.append,
        )
    return listener, engaged, disengaged


def test_single_key_hotkey_engages_and_disengages():
    listener, engaged, disengaged = _make_listener([HotkeySpec(name="primary", keys=("KEY_RIGHTCTRL",))])
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 1))
    assert engaged == ["primary"]
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 0))
    assert disengaged == ["primary"]


def test_chord_only_engages_once_all_keys_pressed():
    listener, engaged, disengaged = _make_listener(
        [HotkeySpec(name="secondary", keys=("KEY_LEFTCTRL", "KEY_LEFTALT", "KEY_SPACE"))]
    )
    listener._handle_event(_event(ecodes.KEY_LEFTCTRL, 1))
    listener._handle_event(_event(ecodes.KEY_LEFTALT, 1))
    assert engaged == []  # space not pressed yet
    listener._handle_event(_event(ecodes.KEY_SPACE, 1))
    assert engaged == ["secondary"]

    listener._handle_event(_event(ecodes.KEY_LEFTALT, 0))
    assert disengaged == ["secondary"]


def test_autorepeat_events_are_ignored():
    listener, engaged, disengaged = _make_listener([HotkeySpec(name="primary", keys=("KEY_RIGHTCTRL",))])
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 1))
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 2))  # autorepeat
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 2))
    assert engaged == ["primary"]
    assert disengaged == []


def test_debounce_ignores_rapid_reengage():
    listener, engaged, disengaged = _make_listener(
        [HotkeySpec(name="primary", keys=("KEY_RIGHTCTRL",))], debounce_ms=10_000
    )
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 1))
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 0))
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 1))  # bounce: re-engage immediately
    assert engaged == ["primary"]
    assert disengaged == ["primary"]


def test_disabled_hotkeys_are_excluded():
    listener, engaged, _ = _make_listener(
        [
            HotkeySpec(name="primary", keys=("KEY_RIGHTCTRL",)),
            HotkeySpec(name="secondary", keys=("KEY_LEFTALT",), enabled=False),
        ]
    )
    listener._handle_event(_event(ecodes.KEY_LEFTALT, 1))
    assert engaged == []


def test_all_hotkeys_disabled_raises():
    with pytest.raises(ValueError):
        with patch("speech_typing.hotkeys.find_keyboard_devices", return_value=[]):
            HotkeyListener(
                hotkeys=[HotkeySpec(name="primary", keys=("KEY_RIGHTCTRL",), enabled=False)],
                debounce_ms=0,
                on_engage=lambda name: None,
                on_disengage=lambda name: None,
            )


def test_permission_denied_raises_keyboard_access_error():
    with patch("speech_typing.hotkeys.glob.glob", return_value=["/dev/input/event0"]):
        with patch("speech_typing.hotkeys.InputDevice", side_effect=PermissionError):
            with pytest.raises(KeyboardAccessError):
                find_keyboard_devices({ecodes.KEY_RIGHTCTRL})


def test_no_devices_at_all_raises_runtime_error():
    with patch("speech_typing.hotkeys.glob.glob", return_value=[]):
        with pytest.raises(RuntimeError):
            find_keyboard_devices({ecodes.KEY_RIGHTCTRL})


def test_matching_device_is_returned():
    fake_device = MagicMock()
    fake_device.capabilities.return_value = {ecodes.EV_KEY: [ecodes.KEY_RIGHTCTRL]}

    with patch("speech_typing.hotkeys.glob.glob", return_value=["/dev/input/event0"]):
        with patch("speech_typing.hotkeys.InputDevice", return_value=fake_device):
            devices = find_keyboard_devices({ecodes.KEY_RIGHTCTRL})

    assert devices == [fake_device]
