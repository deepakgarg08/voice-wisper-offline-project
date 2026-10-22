# speech_typing – project description

## Purpose
An offline alternative to Wispr Flow / SuperWhisper for Fedora KDE Plasma (Wayland and X11). The user
holds a hotkey (or toggles it), speaks, releases, and the recognised text is inserted into whichever window
has focus. Everything runs locally on CPU via whisper.cpp; no audio leaves the machine.

## Flow
1. `hotkeys.py` reads raw `/dev/input` events with `evdev` (Wayland blocks global hooks). Hotkeys: toggle
   (Space + Right Ctrl) and push-to-talk (Left Ctrl + Left Super).
2. `pipeline.py` starts `speech.AudioRecorder` (sounddevice, 16 kHz mono int16) and, on stop, queues the
   recording for transcription.
3. `transcribe.py` runs `whisper-cli` on the WAV (legacy path) – or, with streaming (`streaming.py`,
   `whisper_server.py`), audio chunks are transcribed by a warm `whisper-server` *while the user speaks*.
4. `typing_service.py` + `typing_backends.py` type the text (clipboard+paste, ydotool, xdotool, wtype),
   retrying, then falling back to the clipboard (`clipboard.py`).
5. `storage.py` archives each recording and appends transcripts to a per-day file under
   `RECORDINGS-ASSETS/`.
6. `notifications.py` / `sound.py` give desktop feedback; `app.py` maps `PipelineEvent`s to them.

## Modules
| Module | Role |
|---|---|
| `app.py` | composition root, lifecycle, signal handling |
| `pipeline.py` | record → transcribe → type, history |
| `speech.py` | microphone capture |
| `transcribe.py` | per-utterance `whisper-cli` wrapper |
| `whisper_server.py` | manages a long-lived `whisper-server` process + HTTP client |
| `chunker.py` | silence-aware cut-point detection (pure logic) |
| `streaming.py` | live chunk transcription during recording |
| `typing_backends.py`, `typing_service.py`, `clipboard.py` | output |
| `hotkeys.py`, `environment.py` | input / session detection |
| `config.py`, `user_config.py`, `exceptions.py`, `events.py`, `logging_setup.py` | support |

## Hardware / constraints
Intel i7-1265U (12 threads), 62 GB RAM, no usable GPU (iGPU only). Models: ggml tiny/base/small in
`../models`. CPU-only, so latency work focuses on avoiding repeated model loads and overlapping
transcription with speech.

## Further reading
`README.md`, `SETUP.md`, `ROADMAP.md`, `docs/summary1.md` (history), `LATENCY_PLAN.md` (an earlier,
partly unrelated latency plan), `docs/STREAMING.md` (streaming ASR design).
