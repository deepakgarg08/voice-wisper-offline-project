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


def test_space_right_ctrl_toggle_starts_on_first_chord_and_stops_on_second():
    """Space + Right Ctrl is a toggle: releasing the keys does not stop recording."""
    listener, engaged, disengaged = _make_listener(
        [
            HotkeySpec(
                name="primary",
                keys=("KEY_SPACE", "KEY_RIGHTCTRL"),
                behavior="toggle",
            )
        ]
    )

    # First press of the complete chord -> start.
    listener._handle_event(_event(ecodes.KEY_SPACE, 1))
    assert engaged == []

    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 1))
    assert engaged == ["primary"]
    assert disengaged == []

    # Releasing the keys must NOT stop a toggle hotkey.
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 0))
    listener._handle_event(_event(ecodes.KEY_SPACE, 0))
    assert engaged == ["primary"]
    assert disengaged == []

    # Pressing the complete chord again -> stop.
    listener._handle_event(_event(ecodes.KEY_SPACE, 1))
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 1))
    assert engaged == ["primary"]
    assert disengaged == ["primary"]


def test_right_ctrl_alone_does_not_trigger_primary():
    listener, engaged, disengaged = _make_listener(
        [
            HotkeySpec(
                name="primary",
                keys=("KEY_SPACE", "KEY_RIGHTCTRL"),
                behavior="toggle",
            )
        ]
    )

    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 1))
    assert engaged == []
    assert disengaged == []

    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 0))
    assert engaged == []
    assert disengaged == []


def test_space_alone_does_not_trigger_primary():
    listener, engaged, disengaged = _make_listener(
        [
            HotkeySpec(
                name="primary",
                keys=("KEY_SPACE", "KEY_RIGHTCTRL"),
                behavior="toggle",
            )
        ]
    )

    listener._handle_event(_event(ecodes.KEY_SPACE, 1))
    assert engaged == []
    assert disengaged == []

    listener._handle_event(_event(ecodes.KEY_SPACE, 0))
    assert engaged == []
    assert disengaged == []


def test_chord_only_engages_once_all_keys_pressed_for_push_to_talk():
    listener, engaged, disengaged = _make_listener(
        [
            HotkeySpec(
                name="secondary",
                keys=("KEY_LEFTCTRL", "KEY_LEFTALT", "KEY_SPACE"),
                behavior="push_to_talk",
            )
        ]
    )

    listener._handle_event(_event(ecodes.KEY_LEFTCTRL, 1))
    listener._handle_event(_event(ecodes.KEY_LEFTALT, 1))
    assert engaged == []

    listener._handle_event(_event(ecodes.KEY_SPACE, 1))
    assert engaged == ["secondary"]

    listener._handle_event(_event(ecodes.KEY_LEFTALT, 0))
    assert disengaged == ["secondary"]


def test_autorepeat_events_are_ignored():
    listener, engaged, disengaged = _make_listener(
        [
            HotkeySpec(
                name="primary",
                keys=("KEY_SPACE", "KEY_RIGHTCTRL"),
                behavior="toggle",
            )
        ]
    )

    listener._handle_event(_event(ecodes.KEY_SPACE, 1))
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 1))
    assert engaged == ["primary"]

    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 2))
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 2))
    assert engaged == ["primary"]
    assert disengaged == []


def test_toggle_requires_release_before_second_activation():
    """Holding the chord must not toggle repeatedly from autorepeat events."""
    listener, engaged, disengaged = _make_listener(
        [
            HotkeySpec(
                name="primary",
                keys=("KEY_SPACE", "KEY_RIGHTCTRL"),
                behavior="toggle",
            )
        ]
    )

    listener._handle_event(_event(ecodes.KEY_SPACE, 1))
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 1))
    listener._handle_event(_event(ecodes.KEY_SPACE, 2))
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 2))

    assert engaged == ["primary"]
    assert disengaged == []

    listener._handle_event(_event(ecodes.KEY_SPACE, 0))
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 0))

    listener._handle_event(_event(ecodes.KEY_SPACE, 1))
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 1))

    assert engaged == ["primary"]
    assert disengaged == ["primary"]


def test_debounce_ignores_rapid_reengage():
    listener, engaged, disengaged = _make_listener(
        [
            HotkeySpec(
                name="primary",
                keys=("KEY_SPACE", "KEY_RIGHTCTRL"),
                behavior="toggle",
            )
        ],
        debounce_ms=10_000,
    )

    listener._handle_event(_event(ecodes.KEY_SPACE, 1))
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 1))
    assert engaged == ["primary"]

    listener._handle_event(_event(ecodes.KEY_SPACE, 0))
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 0))

    # Rapid second activation is ignored by debounce.
    listener._handle_event(_event(ecodes.KEY_SPACE, 1))
    listener._handle_event(_event(ecodes.KEY_RIGHTCTRL, 1))

    assert engaged == ["primary"]
    assert disengaged == []


def test_disabled_hotkeys_are_excluded():
    listener, engaged, _ = _make_listener(
        [
            HotkeySpec(
                name="primary",
                keys=("KEY_SPACE", "KEY_RIGHTCTRL"),
                behavior="toggle",
            ),
            HotkeySpec(
                name="secondary",
                keys=("KEY_LEFTALT",),
                behavior="push_to_talk",
                enabled=False,
            ),
        ]
    )

    listener._handle_event(_event(ecodes.KEY_LEFTALT, 1))
    assert engaged == []


def test_all_hotkeys_disabled_raises():
    with pytest.raises(ValueError):
        with patch("speech_typing.hotkeys.find_keyboard_devices", return_value=[]):
            HotkeyListener(
                hotkeys=[
                    HotkeySpec(
                        name="primary",
                        keys=("KEY_SPACE", "KEY_RIGHTCTRL"),
                        behavior="toggle",
                        enabled=False,
                    )
                ],
                debounce_ms=0,
                on_engage=lambda name: None,
                on_disengage=lambda name: None,
            )


def test_permission_denied_raises_keyboard_access_error():
    with patch("speech_typing.hotkeys.glob.glob", return_value=["/dev/input/event0"]):
        with patch("speech_typing.hotkeys.InputDevice", side_effect=PermissionError):
            with pytest.raises(KeyboardAccessError):
                find_keyboard_devices({ecodes.KEY_RIGHTCTRL, ecodes.KEY_SPACE})


def test_no_devices_at_all_raises_runtime_error():
    with patch("speech_typing.hotkeys.glob.glob", return_value=[]):
        with pytest.raises(RuntimeError):
            find_keyboard_devices({ecodes.KEY_RIGHTCTRL, ecodes.KEY_SPACE})


def test_matching_device_is_returned():
    fake_device = MagicMock()
    fake_device.capabilities.return_value = {
        ecodes.EV_KEY: [ecodes.KEY_RIGHTCTRL, ecodes.KEY_SPACE]
    }

    with patch("speech_typing.hotkeys.glob.glob", return_value=["/dev/input/event0"]):
        with patch("speech_typing.hotkeys.InputDevice", return_value=fake_device):
            devices = find_keyboard_devices(
                {ecodes.KEY_RIGHTCTRL, ecodes.KEY_SPACE}
            )

    assert devices == [fake_device]
