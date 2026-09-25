# Running voice-project on another operating system

The project is designed so its application data is relative to the project:

```text
voice-project/
└── RECORDINGS-ASSETS/
```

Do not hardcode `/mnt/shared4` into `user_config.py`.

## Linux / Fedora

Install Python dependencies:

```bash
python3 -m pip install pyperclip pynput
```

For X11 clipboard support, if needed:

```bash
sudo dnf install xclip
```

Run:

```bash
python3 run.py
```

The existing evdev hotkey listener currently remains Linux-specific because it reads `/dev/input/event*`.

Therefore, the typing backend is cross-platform, but the current global-hotkey listener is not yet a Windows/macOS implementation.

## Windows

The Python typing backend is intended to work with:

```text
pyperclip + pynput
```

The global hotkey listener will need a Windows-specific implementation before the complete application is portable.

Whisper.cpp itself must be built/provided for Windows and its location can be supplied through:

```text
SPEECH_TYPING_WHISPER_DIR
```

## macOS

The Python typing backend uses:

```text
pyperclip + pynput
```

and sends Command+V for paste.

macOS accessibility/input permissions may need to be granted to the terminal or application.

The current evdev global-hotkey listener is Linux-specific and needs a platform-specific replacement for macOS.

## Key design boundary

The project now separates:

```text
Speech / Whisper
        ↓
text
        ↓
TypingBackend
        ↓
focused application
```

The `TypingBackend` interface is cross-platform. OS-specific input handling stays behind that interface.
