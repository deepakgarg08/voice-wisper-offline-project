# Roadmap: speech_typing → offline Wispr Flow alternative

This documents the phased plan and the architectural reasoning behind it,
written before implementing anything beyond Phase 1, per request. Each later
phase is a separate, independently-buildable slice — nothing here requires
rewriting Phase 1's core.

## What's already on this machine (checked, not assumed)

- **whisper.cpp**: built without GPU backends (`GGML_VULKAN=OFF`,
  `GGML_HIP=OFF` in `build/CMakeCache.txt`). The Vulkan backend source
  (`ggml/src/ggml-vulkan/`) is present in this checkout, just not compiled in.
  `vulkaninfo` is installed and `libvulkan_radeon.so` (RADV, Mesa's AMD
  driver) is on the system — the AMD 6750 XT eGPU should be usable via
  Vulkan once rebuilt.
- **VAD**: whisper.cpp already has `--vad`/`--vad-model` flags and a
  `models/download-vad-model.sh` script for a Silero VAD model — not yet
  downloaded, but no custom VAD implementation is needed.
- **llama.cpp**: a separate, already-built checkout exists at
  `/mnt/shared4/LLAMACPP/llama.cpp/build/bin/` (`llama-server`, `llama-cli`
  present), also CPU-only right now. A usable instruction-tuned model is
  already on disk: `/mnt/shared4/LLAMACPP/models/qwen3.5-9b/Qwen3.5-9B-UD-Q4_K_XL.gguf`.

These change the plan concretely: GPU accel and local-LLM correction aren't
"integrate a new tool" work, they're "rebuild/configure what's already here."

## Phase 1 — production-ready core (this session)

Everything from the "production-ready" refactor request: configurable
hotkeys (including an optional chord), notifications, sound cues, temp-file
cleanup, Wayland/X11 detection driving typing-backend auto-selection, retry
+ clipboard fallback on typing failure, max recording duration, debounce,
graceful shutdown, config validation, and a packaging skeleton. See the
module layout in `README.md` once committed.

## Phase 2 — continuous dictation + VAD + silence detection

> **Partially done (streaming ASR):** warm `whisper-server` and energy-based chunking during
> recording are implemented; see `docs/STREAMING.md`. Silero VAD and continuous (hands-free) mode remain.

**Decision: reuse whisper.cpp's own VAD rather than writing one.** It
already ships Silero VAD support (`--vad`, `--vad-model`,
`--vad-min-silence-duration-ms`, etc.). Continuous mode becomes: instead of
gating recording on hotkey-hold, gate it on VAD-detected silence — record
continuously into rolling segments, and each time VAD detects a silence gap,
close that segment and hand it to the existing `Transcriber`/`TypingService`
pipeline exactly as a push-to-talk utterance would be. This means Phase 2
adds a new *segmentation source* alongside the hotkey, without touching the
transcribe/type stages at all.

**Decision: keep the "spawn whisper-cli per utterance" model, don't move to
a persistent streaming process.** whisper.cpp has no long-running streaming
IPC mode we can shell out to; using it that way would mean writing C API
bindings (ctypes/pybind11) instead of subprocess calls, a much bigger and
riskier change. Utterance-level batching is simpler, easier to test, and
the latency cost is small for dictation-length utterances.

## Phase 3 — multi-language support

Mostly a config/UX change: `LANGUAGE = "auto"` already works today via
whisper.cpp's `-l auto`. This phase is really about exposing it (config GUI
field or a quick-switch hotkey), not new pipeline logic.

## Phase 4 — GPU acceleration (Vulkan, AMD 6750 XT eGPU)

Requires rebuilding whisper.cpp (and optionally llama.cpp for Phase 6) with
`-DGGML_VULKAN=1`, and confirming `vulkaninfo` actually lists the RADV
device (i.e. the eGPU enumerates correctly over Thunderbolt/USB4 — external
GPU detection can be flaky and needs verifying with the eGPU physically
attached). Once built, `whisper-cli` uses the GPU automatically unless
`--no-gpu` is passed — the Python layer's job is just a `USE_GPU` config
toggle mapped to that flag. **This needs your presence**: a real rebuild
(time + possible driver issues) and hardware verification, not something to
do unattended.

## Phase 5 — voice commands ("new line", "comma", "delete word", ...)

**Decision: a dedicated post-processing stage between Transcriber and
TypingService**, not baked into either. A `CommandInterpreter` takes raw
transcribed text and produces a sequence of typed-text and key-action
tokens (e.g. "comma" → literal `,`; "new line" → literal `\n`; "delete
word"/"undo"/"select all" → a `ydotool key` chord instead of typed text).
Keeping this as its own stage means it can be unit-tested against plain
strings with no audio/typing involved, and disabled via config without
touching the rest of the pipeline.

## Phase 6 — optional local LLM correction (punctuation/grammar/formatting)

**Decision: call `llama-server`'s OpenAI-compatible HTTP API as an optional
final stage**, using the Qwen3.5-9B model already on disk, rather than
linking llama.cpp into this process. Same rationale as whisper.cpp: shelling
out / HTTP keeps this process simple and the model swappable. A strict
system prompt constrains it to punctuation/grammar/formatting fixes only
(no commentary, preserve code keywords), with a short timeout that falls
back to the raw transcription if the LLM is slow or unavailable — this
stage must never be able to block or break dictation. Entirely optional and
off by default; nothing here calls out to the network at any point.

## Phase 7 — system tray icon + configuration GUI

**Decision: the GUI is a separate, optional process from the core daemon,**
talking to it over a local Unix socket (not the same Python process). This
keeps the core speech-to-text daemon headless and independently runnable as
a systemd user service — important for Phase 9 packaging, since a
background service and a GUI have very different packaging/permission
stories (especially under Flatpak portals). Toolkit choice (PyQt6/PySide6
fits the KDE/Qt ecosystem best) still to be confirmed with you.

## Phase 8 — autostart with KDE

A `.desktop` file in `~/.config/autostart/` launching the systemd user
service (or the tray app once Phase 7 exists).

## Phase 9 — RPM / Flatpak packaging polish

Builds on Phase 1's `pyproject.toml` skeleton: an RPM spec once the module
set stabilizes, and/or a Flatpak manifest once the GUI (Phase 7) exists —
Flatpak's sandboxing has real implications for `/dev/input`, `/dev/uinput`,
and D-Bus notification access that are easier to resolve once the feature
set is stable rather than up front.

## Cross-cutting decision: subprocess/HTTP over library bindings

Every external engine (whisper.cpp, ydotool, llama.cpp) is used via CLI
subprocess or local HTTP, never via ctypes/pybind bindings into this
process. This is the one decision that shapes everything else: it keeps
`speech_typing` a thin, pure-Python orchestration layer with no compiled
extension to build/package, at the cost of per-call process-spawn latency
that's negligible at utterance granularity.
