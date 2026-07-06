# speech_typing

Hold Right Ctrl to record, release to transcribe with whisper.cpp and type the
result into whatever window has focus. Works on Fedora KDE regardless of
whether the session is X11 or Wayland.

## Current status (checkpoint 2)

**What works right now, verified on this machine:**
- Transcription pipeline (whisper.cpp `whisper-cli` → clean text) — tested
  end-to-end against `samples/jfk.wav`, passes automated tests.
- All error paths (missing model, missing whisper-cli, ydotool not installed,
  keyboard permission denied) raise clear, correct messages — verified by
  running the app and by the test suite.
- `ydotool`/`ydotoold` are installed and the daemon is running.

**What's still blocking a full end-to-end run (mic → type):**
- Your user is **not yet in the `input` group**, so `evdev` can't open
  `/dev/input/eventN` to detect Right Ctrl. Running `python3 run.py` fails
  immediately with a clear "permission denied, add yourself to input group"
  error — this is expected, not a bug.
- The `ydotoold` socket at `/tmp/.ydotool_socket` is still `root:root 0600`,
  so even once the hotkey works, typing would fail until its permissions are
  fixed.
- Both require a one-time `sudo` step — see **One-time system setup** below,
  or just run `./setup_and_run.sh`, which checks for and fixes both.

**Workflow once setup is complete:**
```
hold Right Ctrl → mic records → release Right Ctrl → whisper.cpp transcribes
→ ydotool types the result into whatever window has focus
```

**Quickest way to get running:** `./setup_and_run.sh` from this directory —
it creates the venv, installs Python deps, checks/fixes the two `sudo`
prerequisites above (asking for your password explicitly, only for those
two steps), and then runs the app.

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
   whenever you use this app. On Fedora it ships as a **system** unit named
   `ydotool.service` (not a `--user` unit):
   ```
   sudo systemctl enable --now ydotool.service
   ```
3. By default `ydotoold` creates its socket at `/tmp/.ydotool_socket` owned
   `root:root` with mode `0600` — unreadable by your user. Override it to be
   group-accessible by `input` (the same group used for hotkey detection
   below):
   ```
   sudo systemctl edit ydotool.service
   ```
   In the editor that opens, add:
   ```
   [Service]
   ExecStart=
   ExecStart=/usr/bin/ydotoold --socket-perm=0660 --socket-own=root:input
   ```
   Then:
   ```
   sudo systemctl daemon-reload
   sudo systemctl restart ydotool.service
   ```
   `speech_typing/config.py` already points at `/tmp/.ydotool_socket`
   explicitly (`YDOTOOL_SOCKET`), since the `ydotool` client's own built-in
   default path doesn't match where the daemon actually listens.
4. Give your user permission to read keyboard events (`evdev` needs this to
   detect Right Ctrl) and to use the `ydotool` socket above:
   ```
   sudo usermod -aG input $USER
   ```
   Log out and back in (or run `newgrp input` in the terminal you'll use)
   for the group change to take effect.

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

## Testing

**1. Automated tests** — cover config, transcription (real end-to-end run
against `samples/jfk.wav`), and error paths. They deliberately never call
`ydotool type`, since that would inject real keystrokes into whichever
window has focus on the machine running the suite:
```
cd voice-project
source .venv/bin/activate
pytest -v
```

**2. Manual smoke tests of each piece in isolation**, useful for narrowing
down which layer is broken:
```
# typing backend only — click into a text field first, then run:
export YDOTOOL_SOCKET=/tmp/.ydotool_socket
ydotool type -- "hello from ydotool"

# transcription only — no mic/hotkey involved:
./build/bin/whisper-cli -m models/ggml-base.bin -f samples/jfk.wav -nt -np -l en
```

**3. Full end-to-end test:**
```
python3 run.py
```
Click into a text editor (e.g. gedit, kate, or a terminal), hold Right Ctrl,
say a short sentence, release, and watch the logs: `Recording started` →
`Recording finished` → `Transcribing` → `Typing text: ...` → `Completed`.
Confirm the typed text lands in the focused window and matches what you said.
Also test releasing Right Ctrl almost immediately (under 300ms) — it should
log a "discarded" warning and type nothing.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "No input audio device is available" | No microphone detected — check `pavucontrol` / PipeWire routing |
| "whisper-cli executable not found" | `WHISPER_DIR` in `config.py` doesn't point at a built whisper.cpp checkout |
| "Model file not found" | The `ggml-<MODEL>.bin` file for the selected `MODEL` isn't in `models/` |
| "No speech was detected" | Logged as a warning, not an error — nothing is typed, recording is discarded |
| "ydotool is not installed" / "Is the ydotoold daemon running?" | See system setup steps 1–2 above |
| "Found input devices but could not open any of them" | See system setup step 3 above |
