# Session summary 1

## What this project is

`voice-project/speech_typing` — offline push-to-talk dictation for Fedora
KDE Plasma. Hold a hotkey, speak, release; whisper.cpp transcribes; the
text is typed into whatever window has focus. Lives inside the whisper.cpp
checkout at `/mnt/shared4/LLAMACPP/models/wisperalternative/whisper.cpp/voice-project`.

## What was built, in order

1. **Initial implementation** (`config.py`, `main.py`, `speech.py`,
   `transcribe.py`, `typer.py`, `utils.py`): hold Right Ctrl → record via
   `sounddevice` → transcribe via `whisper-cli -nt -np` → type via
   `ydotool` (chosen because it injects via `/dev/uinput`, working under
   both X11 and Wayland, unlike `xdotool`/`wtype`). Hotkey detection uses
   raw `evdev` reads of `/dev/input/eventN` since Wayland compositors block
   normal global-hotkey hooks.
2. **checkpoint2**: found and fixed a real bug where `evdev.list_devices()`
   silently drops unreadable devices (would've misreported permission
   issues as "no keyboard found"). Found and fixed a socket-path mismatch:
   `ydotool` client's default socket path doesn't match where `ydotoold`
   actually listens (`/tmp/.ydotool_socket`), plus that socket defaults to
   `root:root 0600`. Added `README.md` status/workflow docs and
   `setup_and_run.sh` (creates venv, installs deps, fixes the two `sudo`
   prerequisites with explicit prompts, then runs the app).
3. **checkpoint3**: full production-ready refactor into 14 focused modules
   with a business-logic/UI split — `pipeline.py` (record→transcribe→type)
   only ever reports events via callback, never imports notifications/sound
   directly; `app.py` is the sole composition root. Added: configurable
   hotkeys with chord + debounce support (`hotkeys.py`), Wayland/X11
   detection driving typing-backend auto-selection (`environment.py`,
   `typing_backends.py`), retry + clipboard fallback (`typing_service.py`,
   `clipboard.py`), desktop notifications + sound cues (both non-fatal if
   the underlying tool is missing), unique per-recording temp files with
   stale-file cleanup, max recording duration, startup config validation
   (`config.validate()`, collects *every* problem, not just the first),
   rotating file logging, graceful SIGINT/SIGTERM shutdown, and a
   packaging skeleton (`pyproject.toml` with a `speech-typing`
   console-script entry point, `packaging/speech-typing.service` systemd
   template). Test suite grew from 13 → 51 passing tests.
4. **ROADMAP.md**: written *before* implementing any of it, per request.
   Phased plan for turning this into a full offline Wispr Flow alternative:
   continuous dictation via whisper.cpp's existing `--vad` support (no
   custom VAD needed), Vulkan GPU accel for the user's AMD 6750 XT eGPU
   (whisper.cpp built here has `GGML_VULKAN=OFF` but the backend source and
   RADV driver are both present — just needs a rebuild), voice commands
   ("new line", "comma", etc.) as a stage between Transcriber and
   TypingService, optional local-LLM punctuation/grammar correction via the
   already-built `llama.cpp` + Qwen3.5-9B model at
   `/mnt/shared4/LLAMACPP/`, a separate GUI/tray process talking to the core
   daemon over a local socket, KDE autostart, then RPM/Flatpak polish.

## Current status

- All code committed to the whisper.cpp git repo (3 commits: initial
  implementation, checkpoint2, checkpoint3), not pushed to origin.
- 51 automated tests pass. Transcription verified end-to-end against
  `samples/jfk.wav`. Every error path verified by actually triggering it.
- **Not yet tested**: the live hold-hotkey → record real speech →
  transcribe → type-into-focused-window flow. This needs the user present
  (can't simulate real keyboard/mic input or visually confirm typed output
  from the assistant's tool environment).
- **Two `sudo` steps still outstanding** (checked as of this summary):
  - User's `input` group membership is granted in `/etc/group` but not
    active in any currently-open shell (needs `newgrp input` or a fresh
    login).
  - `ydotoold`'s socket at `/tmp/.ydotool_socket` is still `root:root 0600`
    — the `systemctl edit ydotool.service` override to make it
    `root:input 0660` hasn't been applied yet.
  - Running `./setup_and_run.sh` handles both, prompting explicitly before
    each `sudo` action.

## Open question (unresolved when this summary was written)

User asked "how to test it via right click option" — ambiguous between (a)
a typo for "Right Ctrl" (testing the existing push-to-talk flow), or (b) an
actual desktop right-click context-menu entry to trigger dictation, which
would be new, unbuilt GUI/tray work (Phase 7 of ROADMAP.md). Was mid-way
through asking the user to clarify when this summary was requested instead.
