from unittest.mock import MagicMock, patch

import pytest
from evdev import ecodes

from speech_typing.utils import KeyboardAccessError, find_hotkey_capable_devices


def test_permission_denied_raises_keyboard_access_error():
    with patch("speech_typing.utils.glob.glob", return_value=["/dev/input/event0"]):
        with patch("speech_typing.utils.InputDevice", side_effect=PermissionError):
            with pytest.raises(KeyboardAccessError):
                find_hotkey_capable_devices("KEY_RIGHTCTRL")


def test_no_devices_at_all_raises_runtime_error():
    with patch("speech_typing.utils.glob.glob", return_value=[]):
        with pytest.raises(RuntimeError):
            find_hotkey_capable_devices("KEY_RIGHTCTRL")


def test_matching_device_is_returned():
    fake_device = MagicMock()
    fake_device.capabilities.return_value = {ecodes.EV_KEY: [ecodes.KEY_RIGHTCTRL]}

    with patch("speech_typing.utils.glob.glob", return_value=["/dev/input/event0"]):
        with patch("speech_typing.utils.InputDevice", return_value=fake_device):
            devices = find_hotkey_capable_devices("KEY_RIGHTCTRL")

    assert devices == [fake_device]
