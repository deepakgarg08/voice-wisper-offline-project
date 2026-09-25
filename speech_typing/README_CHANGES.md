# Voice Project — v4 changes

## Three changes in this revision

### 1. Project-relative storage

Recordings and transcripts no longer depend on `/mnt/shared4/...`.

Default:

```text
voice-project/
└── RECORDINGS-ASSETS/
    ├── RECORDINGS/
    │   └── YYYY-MM-DD/
    └── TRANSCRIPTS/
        └── YYYY-MM-DD.txt
```

The path is derived from the project root.

### 2. Cross-platform Python typing backend

The default `TYPING_BACKEND = "auto"` now prefers:

```text
pyperclip + pynput
```

Flow:

```text
Whisper result
    ↓
pyperclip.copy(text)
    ↓
pynput sends Ctrl+V / Cmd+V
    ↓
text is pasted into the focused application
```

`ydotool`, `xdotool`, and `wtype` remain optional fallbacks.

You can force the Python backend:

```python
TYPING_BACKEND = "python_clipboard"
```

### 3. Effective backend is printed at startup

Startup now shows both:

```text
Typing backend cfg  : auto
Typing backend used : python_clipboard
```

This is important because `auto` describes the policy while `used` tells you what actually handled the paste.

## Install the new Python dependencies

```bash
python3 -m pip install pyperclip pynput
```

On Fedora/Linux, the Python clipboard package may also need an available desktop clipboard provider. On X11, `xclip` is a common choice:

```bash
sudo dnf install xclip
```

The project does not require ydotool when `python_clipboard` works.

## Whisper path

The default Whisper location is now inferred from the project layout:

```text
whisper.cpp/
├── build/bin/whisper-cli
├── models/
└── voice-project/
```

You can override it with:

```bash
export SPEECH_TYPING_WHISPER_DIR=/path/to/whisper.cpp
```

This is preferable to hardcoding `/mnt/shared4`.

## Existing-file transcription

```bash
python3 -m speech_typing.transcribe_file file.wav     --language auto     --mode original
```

English translation:

```bash
python3 -m speech_typing.transcribe_file file.wav     --language auto     --mode translate_en
```

## Important limitation

Whisper's built-in translation mode is translation to English. Arbitrary targets such as Hindi → German require a separate translation layer.
