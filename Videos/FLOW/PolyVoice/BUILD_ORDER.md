# PolyVoice Build Order

This is the dependency-ordered queue for the current recovery sprint. It supersedes the old Twilio-first queue.

Build rule: new model support must be loader/client based, not runtime hardcoded.

## Phase 0: Already Shipped Foundation

These exist and should be maintained, not rebuilt:

1. `src/polyvoice/core/exceptions.py`
2. `src/polyvoice/core/events.py`
3. `src/polyvoice/core/processor.py`
4. `src/polyvoice/core/session.py`
5. `src/polyvoice/config/models.py`
6. `src/polyvoice/config/loader.py`
7. `src/polyvoice/config/legacy.py`
8. `src/polyvoice/config/recipes.py`
9. `src/polyvoice/audio/frames.py`
10. `src/polyvoice/audio/codecs.py`
11. `src/polyvoice/audio/resample.py`
12. `src/polyvoice/audio/agc.py`
13. `src/polyvoice/services/base.py`
14. `src/polyvoice/services/registry.py`
15. `src/polyvoice/services/mocks.py`
16. `src/polyvoice/runtime/bootstrap.py`
17. `src/polyvoice/runtime/server.py`
18. `src/polyvoice/runtime/health.py`
19. `src/polyvoice/runtime/pipeline.py`
20. `src/polyvoice/transport/ws_voice.py`
21. `src/polyvoice/cli.py`

Verification:

```bash
python -m pytest tests/unit tests/integration/test_pipeline_mocks.py
```

## Phase 1: SDK Extension Architecture

Goal: make adding a new ASR/LLM/TTS model as predictable as adding a Transformers model class.

Shipped:

1. `docs/adding-models.md`
   - ASR model loader contract.
   - VAD provider contract.
   - LLM client contract.
   - TTS model loader contract.
   - optional dependencies.
   - fake tests.
   - real smokes.
2. `scripts/scaffold_model_loader.py`
   - `--kind asr`
   - `--kind vad`
   - `--kind llm`
   - `--kind tts`
3. `tests/unit/services/test_extension_contracts.py`
   - confirms fake registered models/clients/providers require no runtime edits.
4. `tests/unit/test_scaffold_model_loader.py`
   - confirms the scaffold writer creates source/test files and protects existing files.

Definition of done:

- Scaffold generator and golden contract tests pass.
- No changes to `runtime/bootstrap.py` are needed for ASR/VAD/LLM/TTS fake extensions.

## Phase 2: Real Local Model Bring-Up

Already shipped:

1. `src/polyvoice/services/tts_sdk/model_loaders/kokoro.py`
2. `examples/kokoro-local/config.yaml`
3. `scripts/kokoro_smoke.py`
4. `scripts/qwen3_asr_smoke.py`
5. `examples/qwen3-asr-local/config.yaml`

Validated:

- Kokoro real CPU smoke wrote `C:\tmp\kokoro_smoke.wav`.
- Qwen3 fake smoke works through the actual SDK loader path.

Build next:

1. Real Qwen3 GPU smoke.
2. Real Silero VAD smoke.
3. Full local demo config:
   - Qwen3 ASR
   - mock or OpenAI-compatible LLM
   - Kokoro TTS

Definition of done:

- One WAV input produces transcript and TTS WAV output.
- If GPU dependencies block, record exact install/runtime failure and keep fake smoke green.

## Phase 3: ASR Streaming Processor Parity

Port old FLOW behavior module-by-module.

Build:

1. `src/polyvoice/services/asr_sdk/processing/vad_state_machine.py`
2. `src/polyvoice/services/asr_sdk/processing/noise_tracker.py`
3. `src/polyvoice/services/asr_sdk/processing/onset_gate.py`
4. `src/polyvoice/services/asr_sdk/processing/rolling_buffer.py`
5. `src/polyvoice/services/asr_sdk/processing/finalization.py`
6. `src/polyvoice/services/asr_sdk/processing/punctuation.py`
7. `src/polyvoice/services/asr_sdk/processing/smart_turn.py`
8. Integrate these into `src/polyvoice/services/asr_sdk/processing/streaming.py`

Tests:

1. VAD state transitions.
2. onset gate blocks low-SNR noise.
3. rolling buffer produces expected windows.
4. Qwen3 low-energy hallucination suppression.
5. finalization after VAD/SmartTurn.

Definition of done:

- ASR SDK can emit stable partials and finals on chunked audio, not just one-shot chunks.

## Phase 4: LLM Streaming Intelligence

Already started:

- response processor
- thinking tag filter
- sentence detector
- turn coordinator
- conversation manager

Build next:

1. backpressure manager.
2. adaptive chunking from TTS feedback.
3. interruption/cancel path.
4. richer metrics report.
5. additional clients:
   - Ollama
   - Anthropic
   - native vLLM if needed

Definition of done:

- LLM SDK can stream, interrupt, adapt chunk size, and report metrics through stable public methods.

## Phase 5: Runtime/UI Parity

Build:

1. richer `/config/status`.
2. `/config/asr`, `/config/llm`, `/config/tts` update routes.
3. service hot-swap mutex.
4. route/event compatibility for `flow-ui`.
5. local demo README.

Definition of done:

- `flow-ui` voice test can point at PolyVoice for the voice loop.

## Phase 6: Telephony Foundation

Only start after Phase 5.

Build:

1. `src/polyvoice/telephony/base.py`
2. `src/polyvoice/telephony/twilio.py`
3. `src/polyvoice/telephony/freeswitch.py`
4. `src/polyvoice/telephony/asterisk.py`
5. adapter-level codec normalization.

Definition of done:

- Same pipeline runs behind at least one telephony mock adapter.

## How To Pick The Next Task

1. If GPU is available, run Phase 2 Qwen3 real smoke in parallel.
2. Then start Phase 3 ASR streaming processor parity.
3. Do not jump to telephony until the local SDK voice loop is demoable.
