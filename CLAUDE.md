# CLAUDE.md

Offline push-to-talk dictation for Linux (Fedora KDE, Wayland/X11): hold or toggle a hotkey, speak,
and the transcript is typed into the focused window. Transcription is done by whisper.cpp.
Full description: `docs/PROJECT.md`. Latency design: `docs/STREAMING.md`.

## Layout
- `run.py` – entry point (single-instance lock, then `speech_typing.main`).
- `speech_typing/` – package. `app.py` is the only composition root; `pipeline.py` holds business logic and
  reports via `PipelineEvent` callbacks (never imports UI). `user_config.py` = user-editable settings,
  `config.py` = derived runtime config + `validate()`.
- `tests/` – pytest (`.venv/bin/python -m pytest -q`).
- whisper.cpp binaries/models live in the parent dir (`../build/bin`, `../models`).

## Conventions
- Business logic stays free of notifications/sound/typing-UI imports; wire things in `app.py`.
- New settings go in `user_config.py`, are exposed in `config.py`, and checked in `config.validate()`.
- Every optional feature must degrade gracefully (e.g. streaming falls back to per-utterance `whisper-cli`).
- Keep modules small; add tests for pure logic (chunking, text cleanup) in `tests/`.

## Workflow
- Commit in small steps. Never commit `RECORDINGS-ASSETS/`, `.venv/`, or `*.wav`.
- Live hotkey/mic/typing flow can't be exercised without a user present; unit tests mock those.
- Known baseline: some older tests in `tests/` were stale before the streaming work (see git history).
