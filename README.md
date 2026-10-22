# speech_typing

Push-to-talk offline dictation for Linux, backed by whisper.cpp. Hold a
hotkey, speak, release — the transcription is typed into whatever window has
focus. Works on Fedora KDE regardless of whether the session is X11 or
Wayland.

See `ROADMAP.md` for the longer-term plan (continuous dictation, GPU accel,
voice commands, local-LLM correction, GUI/tray) and the architectural
reasoning behind it.

## Current status (checkpoint 3)

**What works right now, verified on this machine:**
- Full pipeline architecture (recording → transcription → typing, with
  retry and clipboard fallback) — 51 automated tests passing.
- All error paths (missing model, missing whisper-cli, ydotool not
  installed, keyboard permission denied, invalid config) raise clear
  messages, checked at startup via `config.validate()`.
- `ydotool`/`ydotoold` installed and running.

**What's still blocking a full end-to-end run (mic → type):** your user
still needs to be in the `input` group and the `ydotoold` socket still needs
its permissions fixed — both one-time `sudo` steps. Run `./setup_and_run.sh`,
which checks for and fixes both with an explicit prompt before each.

**Workflow:**
```
hold hotkey → mic records → release hotkey → whisper.cpp transcribes
→ typed into whatever window has focus (or copied to clipboard if typing fails)
```

## Architecture

Each module has one job; `app.py` is the only one allowed to know about all
the others (composition root):

| Module | Responsibility |
|---|---|
| `config.py` | All settings + `validate()`, called once at startup |
| `exceptions.py` | Custom exception types |
| `logging_setup.py` | Console + rotating file logging |
| `environment.py` | Wayland vs X11 session detection |
| `hotkeys.py` | Raw evdev hotkey detection (single keys or chords), debounce |
| `speech.py` | `AudioRecorder` (mic capture) + stale temp-file cleanup |
| `transcribe.py` | Shells out to `whisper-cli`, returns clean text |
| `typing_backends.py` | `ydotool`/`xdotool`/`wtype` backends + auto-selection |
| `typing_service.py` | Retry policy + clipboard fallback around a backend |
| `clipboard.py` | `wl-copy`/`xclip`/`xsel` wrapper |
| `notifications.py` | `notify-send` wrapper (cosmetic, never fatal) |
| `sound.py` | Start/stop sound cues via `paplay`/`pw-play` (cosmetic, never fatal) |
| `events.py` | `PipelineEvent` enum — how the pipeline reports what happened |
| `pipeline.py` | **Business logic**: record → transcribe → type, worker thread, max-duration auto-stop. No knowledge of notifications/sound/logging — only emits events. |
| `app.py` | **Composition root**: wires everything above, owns signal handling and graceful shutdown |
| `main.py` | Thin entry point |

The pipeline/app split is the "separate business logic from UI" boundary:
`pipeline.py` would work identically wired up to a GUI instead of desktop
notifications, since it only ever calls the `on_event` callback it was
given.

## How it works

- **Hotkey detection** reads raw kernel input events from `/dev/input/eventN`
  via `evdev`, instead of an X11/Wayland-level hook — Wayland compositors
  don't let normal apps register global hotkeys, so this is the one approach
  that works under both session types with no compositor-specific support.
  A hotkey can be a single key or a chord (all keys held at once); it
  engages the instant every key is down and disengages the instant any one
  releases.
- **Typing** prefers `ydotool`, which injects keystrokes via `/dev/uinput`
  at the kernel level and so works under both X11 and Wayland — unlike
  `xdotool` (X11-only) or `wtype` (Wayland-only), which are used as
  automatic fallbacks only if `ydotool` isn't installed.
- **Retry + clipboard fallback**: a failed typing attempt is retried a few
  times; if it still fails, the text is copied to the clipboard instead of
  being lost, and a notification says so.

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
   detect the hotkey) and to use the `ydotool` socket above:
   ```
   sudo usermod -aG input $USER
   ```
   Log out and back in (or run `newgrp input` in the terminal you'll use)
   for the group change to take effect.

**Or just run `./setup_and_run.sh`**, which checks all of the above and only
prompts for `sudo` on whatever's actually missing.

## Python setup

```
cd voice-project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`pyproject.toml` also exists (`pip install -e .`), providing the
`speech-typing` console-script entry point used once this is packaged as an
RPM/Flatpak (see `packaging/speech-typing.service` for a systemd user-service
template). `requirements.txt` remains the quickest path for local dev.

## Configuration

All settings live in `speech_typing/config.py`, validated at startup by
`config.validate()`. The one you'll change most:

```python
MODEL = "base"  # "tiny", "base", or "small"
```

The ggml model path is derived automatically from `WHISPER_DIR` (itself
overridable via the `SPEECH_TYPING_WHISPER_DIR` env var for packaging).

Other notable settings:

```python
HOTKEYS = [
    HotkeySpec(name="primary", keys=("KEY_RIGHTCTRL",), enabled=True),
    HotkeySpec(name="secondary", keys=("KEY_LEFTCTRL", "KEY_LEFTALT", "KEY_SPACE"), enabled=True),
]
HOTKEY_DEBOUNCE_MS = 75          # absorbs switch bounce / accidental double-taps
MAX_RECORDING_DURATION_S = 60    # auto-stops a recording held this long
TYPING_BACKEND = "auto"          # "auto" | "ydotool" | "xdotool" | "wtype"
TYPING_MAX_RETRIES = 3
CLIPBOARD_FALLBACK_ENABLED = True
NOTIFICATIONS_ENABLED = True
SOUND_EFFECTS_ENABLED = True
```

Add or disable a hotkey by editing the `HOTKEYS` list (any key names from
[`evdev.ecodes`](https://python-evdev.readthedocs.io/en/latest/apidoc.html#module-evdev.ecodes)
work, single key or chord).

## Running

```
python3 run.py
```

Hold a configured hotkey, speak, release. The transcribed text is typed at
the current cursor position after a moment (or copied to the clipboard if
typing fails after retrying).

## Testing

**1. Automated tests** — 51 tests covering config validation, hotkey
chord/debounce logic, typing-backend selection, retry/clipboard-fallback
policy, session detection, the pipeline's business logic (mocked
recorder/transcriber/typing), and a real end-to-end transcription run
against `samples/jfk.wav`. They deliberately never call `ydotool type` or
touch real input devices, since that would affect whatever window/keyboard
is active on the machine running the suite:
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
Click into a text editor, hold the primary hotkey (Right Ctrl), say a short
sentence, release, and watch the logs: `Recording started` → `Recording
finished` → `Transcribing` → `Typing text: ...` → `Completed`. Try the
secondary hotkey (Ctrl+Alt+Space) too. Also test releasing almost
immediately (under 300ms, should log "discarded") and holding past 60s
(should auto-stop and log "max_duration").

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Invalid configuration: ..." | `config.validate()` caught a problem — the message lists every issue found |
| "No input audio device is available" | No microphone detected — check `pavucontrol` / PipeWire routing |
| "whisper-cli executable not found" | `WHISPER_DIR` / `SPEECH_TYPING_WHISPER_DIR` doesn't point at a built whisper.cpp checkout |
| "Model file not found" | The `ggml-<MODEL>.bin` file for the selected `MODEL` isn't in `models/` |
| "No speech was detected" | Logged as a warning, not an error — nothing is typed, recording is discarded |
| "No usable typing backend found" | Install ydotool: `sudo dnf install ydotool` |
| "Is ydotoold running, and is its socket readable?" | See system setup steps 2–3 above |
| "Found input devices but could not open any of them" | See system setup step 4 above |
| Typing failed, copied to clipboard instead | All retries failed — paste manually; check `ydotoold` is actually running |

## Low-latency streaming

By default audio is transcribed in chunks while you speak, using a warm `whisper-server`; see
`docs/STREAMING.md`. Disable with `STREAMING_ENABLED = False` in `speech_typing/user_config.py`.
