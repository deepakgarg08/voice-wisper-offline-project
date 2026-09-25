# Speech Typing (voice-project) Setup and Run

Push-to-talk offline dictation for Linux, backed by whisper.cpp.
Hold a configured hotkey, speak, release — the transcription is typed into whatever window has focus.

## Current Status (checkpoint 3)

**What works right now, verified on this machine:**
- Full pipeline architecture (recording → transcription → typing, with retry and clipboard fallback) — 51 automated tests passing.
- All error paths (missing model, missing whisper-cli, ydotool not installed, keyboard permission denied, invalid config) raise clear messages, checked at startup via `config.validate()`.
- `ydotool`/`ydotoold` installed and running.

**What's still blocking a full end-to-end run (mic → type):**
- Your user still needs to be in the `input` group and the `ydotoold` socket still needs its permissions fixed — both one-time `sudo` steps.
- Run `./setup_and_run.sh`, which checks for and fixes both with an explicit prompt before each.

## Installation

### Prerequisites

- **Python 3.10+** (required by speech-typing package)
- **ydotool** (global hotkey injection) — install with `sudo dnf install ydotool`
- **ydotoold** (keystroke capture) — usually included with ydotool
- **A trained whisper.cpp model** (e.g., `base.en`) — download with:
  ```bash
  sh ./models/download-ggml-model.sh base.en
  ```

### Step-by-Step Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/ggml-org/whisper.cpp.git
   cd whisper.cpp
   ```

2. **Navigate to the voice-project subdirectory**
   ```bash
   cd whisper.cpp/voice-project
   ```

3. **Create and activate a virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. **Install Python dependencies**
   ```bash
   pip install --quiet -r requirements.txt
   ```

5. **Set up ydotoold (if needed)**
   ```bash
   ./setup_and_run.sh
   ```
   This script will:
   - Check if `ydotool` and `ydotoold` are installed
   - Configure `ydotoold` service if needed (requires sudo)
   - Add your user to the `input` group if needed (requires sudo)
   - Run the setup and restart the service

6. **Run the speech-typing application**
   ```bash
   python3 run.py
   ```

## Configuration

The application is configured via `config.py` with the following key parameters:

- **HOTKEYS** – List of hotkeys (e.g., `["primary": "KEY_RIGHTCTRL", "secondary": "KEY_LEFTCTRL KEY_LEFTALT KEY_SPACE"]`)
- **TYPING_BACKEND** – Choose between `"auto"`, `"ydotool"`, `"xdotool"`, or `"wtype"`
- **MAX_RECORDING_DURATION_S** – Auto-stop duration (default: 60 seconds)
- **TYPING_MAX_RETRIES** – Number of retry attempts (default: 3)
- **CLIPBOARD_FALLBACK_ENABLED** – Enable fallback to clipboard if typing fails

Edit `config.py` to adjust these settings before running.

## Running Tests

To run the automated test suite:

```bash
cd voice-project
pytest -v
```

This runs 51 tests covering config validation, hotkey logic, typing backends, retry/clipboard fallback, and end-to-end transcription.

## Manual Smoke Tests

### Typing Backend Only
```bash
export YDOTOOL_SOCKET=/tmp/.ydotool_socket
ydotool type -- "hello from ydotool"
```

### Transcription Only (no mic/hotkey)
```bash
./build/bin/whisper-cli -m models/ggml-base.bin -f samples/jfk.wav -nt -np -l en
```

### Full End-to-End Test
```bash
python3 run.py
```
Click into a text editor, hold the primary hotkey (Right Ctrl), say a short sentence, release, and watch the logs for the full pipeline flow.

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Invalid configuration" | Missing model or misconfigured path | Run `./setup_and_run.sh` to fix model path and ensure whisper-cli is in PATH |
| "No input audio device" | Microphone not accessible | Check `pavucontrol` / PipeWire routing; ensure mic is enabled |
| "whisper-cli executable not found" | WHISPER_DIR not pointing to built model | Set `SPEECH_TYPING_WHISPER_DIR` env var to point at your ggml model |
| "No speech detected" | Mic not active or ydotoold not running | Run `./setup_and_run.sh` to configure ydotoold and input group |
| "Type failure" | Clipboard fallback disabled | Edit `config.py` to enable `CLIPBOARD_FALLBACK_ENABLED = True` |

## Architecture Overview

- **`config.py`** – All settings + `validate()` (called at startup)
- **`exceptions.py`** – Custom exception types
- **`logging_setup.py`** – Console + rotating file logging
- **`environment.py`** – Wayland vs X11 session detection
- **`hotkeys.py`** – Raw evdev hotkey detection (single keys or chords), debounce
- **`speech.py`** – `AudioRecorder` (mic capture) + stale temp-file cleanup
- **`transcribe.py`** – Shells out to `whisper-cli`, returns clean text
- **`typing_backends.py`** – `ydotool`/`xdotool`/`wtype` backends + auto-selection
- **`typing_service.py`** – Retry policy + clipboard fallback around a backend
- **`clipboard.py`** – `wl-copy`/`xclip`/`xsel` wrapper
- **`notifications.py`** – `notify-send` wrapper (cosmetic, never fatal)
- **`sound.py`** – Start/stop sound cues via `paplay`/`pw-play` (cosmetic, never fatal)
- **`events.py`** – `PipelineEvent` enum — how the pipeline reports what happened
- **`pipeline.py`** – Business logic: record → transcribe → type, worker thread, max-duration auto-stop
- **`app.py`** – Composition root: wires everything above, owns signal handling and graceful shutdown
- **`main.py`** – Thin entry point

## Running from Scratch (Summary)

1. **Install Python 3.10+** and dependencies
2. **Download a whisper.cpp model** (e.g., `base.en`)
3. **Run `./setup_and_run.sh`** – handles ydotoold setup and input group membership
4. **Execute `python3 run.py`** – starts the speech-typing application

## License

MIT

---

*Last updated: 2026-09-25*