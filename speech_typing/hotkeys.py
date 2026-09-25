"""Global hotkey detection via raw kernel input events (evdev).

Wayland compositors don't let normal applications register global hotkeys,
so this reads /dev/input/eventN directly instead -- the one approach that
works under both X11 and Wayland with no compositor-specific support.
"""

from __future__ import annotations

import glob
import logging
import selectors
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, FrozenSet, List, Sequence, Set

from evdev import InputDevice, ecodes

from .exceptions import KeyboardAccessError

logger = logging.getLogger(__name__)

HotkeyCallback = Callable[[str], None]


@dataclass(frozen=True)
class HotkeySpec:
    """A named hotkey: one key, or a chord of keys held simultaneously."""

    name: str
    keys: Sequence[str]  # evdev key names, e.g. ("KEY_LEFTCTRL", "KEY_LEFTALT", "KEY_SPACE")
    behavior: str = "push_to_talk"  # "push_to_talk" or "toggle"
    enabled: bool = True


def find_keyboard_devices(required_key_codes: Set[int]) -> List[InputDevice]:
    """Return all input devices that report at least one of the given key codes.

    Globs /dev/input directly rather than using evdev.list_devices(), which
    silently drops devices the process can't read -- that would otherwise be
    misreported as "no keyboard found" instead of a permissions problem.
    """
    matches: List[InputDevice] = []
    permission_errors = 0

    for path in glob.glob("/dev/input/event*"):
        try:
            device = InputDevice(path)
        except (PermissionError, OSError):
            permission_errors += 1
            continue

        capabilities = set(device.capabilities().get(ecodes.EV_KEY, []))
        if capabilities & required_key_codes:
            matches.append(device)
        else:
            device.close()

    if not matches:
        if permission_errors:
            raise KeyboardAccessError(
                "Found input devices but could not open any of them "
                f"({permission_errors} permission denied). Add your user to the "
                "'input' group with: sudo usermod -aG input $USER, then log out "
                "and back in (or run 'newgrp input' in this shell)."
            )
        raise RuntimeError("No input device reports any of the configured hotkey keys.")

    return matches


class HotkeyListener:
    """Tracks configured hotkeys (single keys or chords) across all keyboards.

    A hotkey "engages" the instant every one of its keys is pressed, and
    "disengages" the instant any one of them is released -- standard
    push-to-talk chord semantics. A debounce window ignores an engage that
    follows too soon after that same hotkey's last disengage, to absorb
    switch bounce / accidental double-taps.
    """

    def __init__(
        self,
        hotkeys: Sequence[HotkeySpec],
        debounce_ms: int,
        on_engage: HotkeyCallback,
        on_disengage: HotkeyCallback,
        on_toggle: HotkeyCallback,
    ) -> None:
        enabled = [h for h in hotkeys if h.enabled]
        if not enabled:
            raise ValueError("At least one HotkeySpec must be enabled.")

        self._chords: Dict[str, FrozenSet[int]] = {
            h.name: frozenset(getattr(ecodes, key) for key in h.keys) for h in enabled
        }
        self._all_codes: Set[int] = set().union(*self._chords.values())
        self._debounce_ms = debounce_ms
        self._on_engage = on_engage
        self._on_disengage = on_disengage
        self._on_toggle = on_toggle
        self._behaviors: Dict[str, str] = {h.name: h.behavior for h in enabled}
        invalid = {h.behavior for h in enabled} - {"push_to_talk", "toggle"}
        if invalid:
            raise ValueError(f"Unsupported hotkey behavior(s): {sorted(invalid)}")

        self._pressed: Set[int] = set()
        self._engaged: Set[str] = set()
        self._last_disengage_at: Dict[str, float] = {}
        self._stop_requested = threading.Event()

        self._devices = find_keyboard_devices(self._all_codes)

    def listen_forever(self) -> None:
        """Block, dispatching on_engage/on_disengage until stop() is called."""
        selector = selectors.DefaultSelector()
        for device in self._devices:
            selector.register(device, selectors.EVENT_READ)

        try:
            while not self._stop_requested.is_set():
                for key, _ in selector.select(timeout=0.5):
                    device: InputDevice = key.fileobj  # type: ignore[assignment]
                    for event in device.read():
                        self._handle_event(event)
        finally:
            selector.close()
            for device in self._devices:
                device.close()

    def stop(self) -> None:
        self._stop_requested.set()

    def _handle_event(self, event) -> None:
        if event.type != ecodes.EV_KEY or event.code not in self._all_codes:
            return
        if event.value == 1:
            self._pressed.add(event.code)
        elif event.value == 0:
            self._pressed.discard(event.code)
        else:
            return  # ignore autorepeat (value == 2)

        now = time.monotonic()
        for name, required_codes in self._chords.items():
            fully_pressed = required_codes.issubset(self._pressed)
            if fully_pressed and name not in self._engaged:
                last_disengage = self._last_disengage_at.get(name)
                if last_disengage is not None and (now - last_disengage) * 1000 < self._debounce_ms:
                    logger.debug("Ignoring bounced re-engage of hotkey %r", name)
                    continue
                self._engaged.add(name)
                if self._behaviors[name] == "toggle":
                    self._on_toggle(name)
                else:
                    self._on_engage(name)
            elif not fully_pressed and name in self._engaged:
                self._engaged.discard(name)
                self._last_disengage_at[name] = now
                if self._behaviors[name] == "push_to_talk":
                    self._on_disengage(name)
