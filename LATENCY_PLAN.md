# Plan: reduce latency of the voice pipeline (revised)

## Context
- **Dictation already exists elsewhere.** The `svoice` alias stops `speech-typing.service` (user systemd unit). That unit runs `/mnt/shared4/LLAMACPP/models/wisperalternative/whisper.cpp/voice-project/run.py`: push-to-talk, hold a hotkey, speak, release, whisper.cpp transcribes, and the text is typed into the focused window. It is a separate project, not this repo. The `svoice` command stops it; it does not start or touch this project.
- **This repo** (`QWEN-AUDIO-OPENSOURCE`) is a voice-chat and TTS/cloning toolkit: Whisper, Qwen, and Coqui TTS. It is not running right now (no `voice_use_cases.py` or `qwen_audio_server.py` process; port 8000 belongs to an unrelated `app.main:app` server from `/srv`).
- **Hardware:** Intel i7-1265U, 12 threads, 62 GB RAM, integrated Intel Iris Xe GPU only. No NVIDIA/CUDA. The eGPU mentioned in the ROADMAP is not attached.
- **Why the QWEN repo is slow:** the CLI reloads all models on each run, stages run serially with no streaming, and the models are plain transformers in fp32 on CPU.
- **Realistic target:** "microseconds" is not achievable for any speech model. A CPU-only target is roughly a few hundred milliseconds from end of speech to text, and about one second from question to first spoken reply. These are estimates; measure before and after.

## Recommended changes

### 1. Dictation: improve `speech-typing` in place
Its ROADMAP already names the next steps:
- Switch to a faster model or enable its built-in VAD (`--vad`, `--vad-model`).
- Keep the whisper.cpp process warm instead of spawning `whisper-cli` per utterance (the ROADMAP currently defers this).
- Enable Vulkan GPU support only if the eGPU is attached. The iGPU is not expected to help much.

### 2. Voice chat (QWEN repo): keep models resident
- Preload ASR, LLM and TTS in a FastAPI `lifespan` hook and run a warm-up inference. Right now `lru_cache` loads on the first request.
- Run `qwen_audio_server.py` once and use the `server-*` clients.

### 3. Voice chat (QWEN repo): stream and pipeline
- Stream LLM tokens and split them at sentence boundaries. Send each sentence to TTS as soon as it is ready, so first audio plays after one sentence rather than after the full answer.
- Serve the chat LLM with **llama.cpp** (Qwen2.5-1.5B or 0.5B, Q4 GGUF). The ROADMAP's Qwen3.5-9B GGUF is too heavy for CPU latency. Test a smaller model first.
- Replace the default TTS for plain replies with a lighter CPU model, such as **Piper**. Kokoro-82M is an option, but unbenchmarked on this CPU. Keep XTTS v2 only for `clone-speak`, since Piper and Kokoro cannot clone voices.

### 4. Cloud fallback (optional)
Groq `whisper-large-v3-turbo` has a free tier (confirm the current limits), but it adds network latency and sends audio off-machine. Only add it behind a flag if local latency is still too high.

### 5. Dependencies (QWEN repo)
- `requirements.txt` is trimmed to what the code imports: `coqui-tts`, `transformers`, `soundfile`, `numpy`, `fastapi`, `uvicorn`, `requests`, `python-dotenv`.
- `accelerate`, `sentencepiece` and `safetensors` were removed; the code does not import them.
- `transformers` is kept only while the Whisper and Qwen code still uses it. If the ASR and LLM move to faster-whisper or llama.cpp, `transformers` can be removed too. `torch` comes in through `coqui-tts`.

## Critical files
- QWEN repo: `voice_use_cases.py` (`build_asr_model`, `build_chat_model`, `answer_question`, `build_tts`, `speak_text`), `qwen_audio_server.py` (startup preload, streaming endpoint), `config.py` and `.env.example` (new backend settings).
- speech-typing repo: `pipeline.py` and `transcribe.py` (per-utterance `whisper-cli` spawn), `config.py` (model and VAD settings).

## Verification
- QWEN repo: time each stage (ASR, LLM first token, TTS first audio) with `time.perf_counter()` on `my_voice.wav`, before and after. Run `python3.10 qwen_audio_server.py`, then `server-stt` and `server-voice-chat`, and compare the first request with later ones.
- speech-typing: measure end-to-end latency (hotkey release to text typed) from its log file, not from this repo.

## Open questions
1. Is the `speech-typing` dictation path enough, or do you want dictation inside the QWEN repo too?
2. Do you need Hindi? That decides between English-only `base.en` or distil models and multilingual `small` or `large-v3-turbo`.
3. Is a cloud fallback acceptable?
