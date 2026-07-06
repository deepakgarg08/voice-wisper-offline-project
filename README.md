# speech_typing

Hold Right Ctrl to record, release to transcribe with whisper.cpp and type the
result into whatever window has focus. Works on Fedora KDE regardless of
whether the session is X11 or Wayland.

## How it works

- **Hotkey detection** reads raw kernel input events from `/dev/input/eventN`
  via `evdev`, instead of an X11/Wayland-level hook. Wayland compositors
  don't let normal apps register global hotkeys, so this is the one approach
  that works under both session types with no special compositor support.
- **Typing** uses `ydotool`, which injects keystrokes via `/dev/uinput` at the
  kernel level. `xdotool` only works on X11 and `wtype` only works on
  Wayland; `ydotool` works on both, which matters here since the same box can
  run either session type.

## One-time system setup

1. Install ydotool and its daemon:
   ```
   sudo dnf install ydotool
   ```
2. Start `ydotoold` (the daemon that actually injects input) so it's running
   whenever you use this app:
   ```
   systemctl --user enable --now ydotool
   ```
   If that unit name doesn't exist on your install, check
   `systemctl list-unit-files | grep ydotool` or `man ydotoold` — some
   packagings require running `ydotoold &` manually instead.
3. Give your user permission to read keyboard events (`evdev` needs this to
   detect Right Ctrl):
   ```
   sudo usermod -aG input $USER
   ```
   Log out and back in for the group change to take effect.
4. Make sure your user can write to `/dev/uinput` (needed by `ydotool`).
   Check with `ls -l /dev/uinput`; if your user isn't in the owning group,
   add a udev rule, e.g. `/etc/udev/rules.d/99-uinput.rules`:
   ```
   KERNEL=="uinput", GROUP="input", MODE="0660"
   ```
   then `sudo udevadm control --reload-rules && sudo udevadm trigger`.

## Python setup

```
cd voice-project
python3 -m venv .venv        # optional, if you don't want to use system packages
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

All settings live in `speech_typing/config.py`. The one you'll change most:

```python
MODEL = "base"  # "tiny", "base", or "small"
```

The ggml model path is derived automatically from `WHISPER_DIR` — no need to
touch anything else when switching models, as long as the corresponding
`models/ggml-<name>.bin` file exists.

## Running

```
python3 run.py
```

Hold Right Ctrl, speak, release. The transcribed text is typed at the current
cursor position after a moment.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "No input audio device is available" | No microphone detected — check `pavucontrol` / PipeWire routing |
| "whisper-cli executable not found" | `WHISPER_DIR` in `config.py` doesn't point at a built whisper.cpp checkout |
| "Model file not found" | The `ggml-<MODEL>.bin` file for the selected `MODEL` isn't in `models/` |
| "No speech was detected" | Logged as a warning, not an error — nothing is typed, recording is discarded |
| "ydotool is not installed" / "Is the ydotoold daemon running?" | See system setup steps 1–2 above |
| "Found input devices but could not open any of them" | See system setup step 3 above |
