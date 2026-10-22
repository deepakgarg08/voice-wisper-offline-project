# AGENTS.md (voice-project)

Guidance for AI coding agents working in `voice-project/` (the `speech_typing` dictation app). This is a
private project; the upstream whisper.cpp `AGENTS.md` in the parent directory governs contributions to the
whisper.cpp repository itself, not this subproject. Start with `CLAUDE.md` for layout, commands and gotchas.

## Rules
- Read `docs/PROJECT.md` first; read `docs/STREAMING.md` before touching the recording/transcription path.
- Keep `pipeline.py` free of UI imports; only `app.py` wires components together.
- Any new setting goes through `user_config.py` -> `config.py` -> `validate()` and gets documented.
- Streaming must always have a fallback to whole-file `whisper-cli`; never make the app fail to start because
  `whisper-server` is unavailable.
- Run `.venv/bin/python -m pytest -q` before committing; new logic needs tests. Some older hotkey/backend/config
  tests are known-stale.
- Update the docs (`README.md`, `SETUP.md`, `docs/`, `CLAUDE.md`) whenever behavior, modules or settings change.
- Commit small, logical changes with clear messages; do not push without the owner's approval.
- Don't run or restart the `speech-typing.service` user service unless asked; it is the owner's live dictation tool.
- Never commit recordings, transcripts, `.venv/` or `*.wav` (see `.gitignore`).
