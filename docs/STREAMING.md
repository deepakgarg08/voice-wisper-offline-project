# Streaming ASR (low-latency dictation)

## Problem
The original pipeline recorded the whole utterance, then spawned `whisper-cli` (reloading the model every
time) and waited for the full transcript. Latency after release = model load + transcription of *all* audio
(~4 s for 11 s of speech with `base`, growing with length).

## Design
```
mic ──► AudioRecorder (frames in memory)
          │ get_audio(start)            every 150 ms
          ▼
     StreamingSession.feeder ──► SilenceChunker.decide() ──► chunk queue
                                                               │ (ordered, 1 worker)
                                                               ▼
                                          WhisperServerTranscriber ──HTTP──► warm whisper-server
                                                               │ text per chunk
release ──► finish(): flush unsent tail, join worker ──► join chunk texts ──► TypingService
```
- **Warm server** (`whisper_server.py`): `whisper-server` is started once with the app (model loaded,
  one warm-up inference). It is killed with the app (`PR_SET_PDEATHSIG` guards against orphaning).
- **Chunking** (`chunker.py`): audio is cut when ≥ `STREAM_MIN_CHUNK_S` is pending and the last
  `STREAM_SILENCE_MS` is quiet, so words are not split. The silence threshold adapts to the noise floor.
  Hard cut at `STREAM_MAX_CHUNK_S` in the quietest spot of the last third. Silent chunks are dropped, which
  also avoids whisper's "you"/"[BLANK_AUDIO]" hallucinations (`clean_text`).
- **Backlog control** (`streaming.py`): while a chunk is still being transcribed, pause-cuts are
  deferred (only the forced max-length cut applies) so the queue never grows; the user waits for at most one
  in-flight chunk plus the tail.
- **Cheaper encoder**: whisper always encodes a 30 s window. The server runs with `-ac` sized to the max
  chunk (+1 s), cutting per-chunk time from ~1.7 s to ~0.7 s on this CPU (base model).
- **Context**: the end of the previous chunk is sent as `prompt` for continuity across cuts.
- **Fallback**: if the server cannot start, or a streaming transcription fails, the pipeline uses the saved
  WAV with the per-utterance `whisper-cli` path.

## Robustness decisions (from live testing)
- **Quiet microphones**: the silence threshold is `1.6 × noise floor` (10th-percentile window RMS), clamped to
  40–1500 (int16 scale). An earlier fixed minimum of 150 classified a quiet mic (speech peaks ~1000) as silence.
- **No stalls**: the server runs with `-nf` (no temperature fallback; noisy chunks used to take 15–18 s) and
  `-sns` (suppress non-speech tokens). Each HTTP request times out after 20 s, and the pipeline then falls
  back to whole-file `whisper-cli` on the saved recording.
- **Hallucination guard**: silent chunks are never sent; bracketed tags and one-word junk ("you") are dropped.
- **Debugging**: `journalctl --user -u speech-typing.service -f` shows the service log, including
  "Toggle hotkey pressed" lines. (The rotating file log under `~/.local/state/speech_typing/` may be stale
  when the service logs to the journal.)

## Output timing
Default `STREAM_TYPE_WHILE_RECORDING = False`: text is typed once on release (safe while modifier keys are
still held). Set to `True` to type each chunk as soon as it is recognised.

## Measured (simulated real-time feed of `samples/jfk.wav` ×2, base model, i7-1265U, loaded desktop)
| Path | Latency after release |
|---|---|
| `whisper-cli` per utterance (old), 11 s clip | ~4.2 s |
| Streaming, 23 s of speech | ~0.9 s |

Measure live latency from the log (`~/.local/state/speech_typing/speech_typing.log`): "Recording finished"
→ "Typing text". Per-chunk lines read `Chunk N.Ns transcribed in X.XXs`.

## Settings (`user_config.py`)
`STREAMING_ENABLED`, `WHISPER_THREADS`, `STREAM_MIN_CHUNK_S`, `STREAM_MAX_CHUNK_S`, `STREAM_SILENCE_MS`,
`STREAM_USE_PROMPT`, `STREAM_TYPE_WHILE_RECORDING`.

## Not yet done / ideas
- Live hotkey → mic → typed-output run was not exercised (needs a user at the machine); logic is covered by
  unit tests and a simulated real-time run.
- Silero VAD (`--vad`) instead of energy-based chunking; a smaller/quantised model (`tiny`, q5) for faster
  chunks; Vulkan if the eGPU is attached.
