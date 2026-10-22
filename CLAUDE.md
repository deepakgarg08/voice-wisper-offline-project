# CLAUDE.md

Offline push-to-talk dictation for Linux (Fedora KDE, Wayland/X11): toggle or hold a hotkey, speak, and the
transcript is typed into the focused window. whisper.cpp does the ASR. Details: `docs/PROJECT.md`;
low-latency design: `docs/STREAMING.md`. Agent rules: `AGENTS.md`.

## Layout
- `run.py` – entry point (single-instance lock, then `speech_typing.main`).
- `speech_typing/` – package. `app.py` is the only composition root; `pipeline.py` is business logic that
  reports via `PipelineEvent` callbacks (never imports UI). `user_config.py` = user settings,
  `config.py` = derived config + `validate()`.
- Streaming ASR: `whisper_server.py` (warm server + HTTP), `chunker.py` (pause detection), `streaming.py`
  (background chunk worker). `transcribe.py` (`whisper-cli`) is the fallback path.
- `tests/` – pytest. whisper.cpp binaries/models live in the parent dir (`../build/bin`, `../models`).

## Hotkeys
Toggle: Space + Right Ctrl. Push-to-talk: hold Left Ctrl + Left Super. Text is typed once on release
(`STREAM_TYPE_WHILE_RECORDING = False`).

## Commands
- Tests: `.venv/bin/python -m pytest -q`
- Run/restart: `systemctl --user restart speech-typing.service`; logs: `journalctl --user -u speech-typing.service -f`
- Thread dump of the live service: `py-spy dump --pid $(systemctl --user show -p MainPID --value speech-typing.service)`

## Conventions
- Keep business logic free of notifications/sound/typing-UI imports; wire things in `app.py`.
- New settings: `user_config.py` -> `config.py` -> `config.validate()`.
- Optional features degrade gracefully (streaming -> per-utterance `whisper-cli`).
- Add tests for pure logic (chunking, text cleanup, pipeline routing).

## Gotchas learned
- Mics can be very quiet (peaks ~1000/32767); never use a high fixed silence threshold.
- whisper-server needs `-nf` and a request timeout, otherwise noisy chunks stall for 15 s+.
- `-ac` (audio context) is sized from `STREAM_MAX_CHUNK_S`; whole-file audio must not go to that server.
- Service logs go to the journal; `~/.local/state/speech_typing/speech_typing.log` can be stale.
- Live hotkey/mic/typing can't be tested without the user; ask them to retest and read the journal.
- ~14 older tests (hotkeys, typing_backends, config) were already stale before the streaming work.

## Workflow
Commit in small logical steps. Never commit `RECORDINGS-ASSETS/`, `.venv/`, or `*.wav`.
