# PolyVoice Sprint Plan

This plan replaces the old drip-by-drip migration list with shippable sprint lanes. The immediate goal is to turn the recovered FLOW SDK architecture into a demoable, extensible PolyVoice runtime where adding a model feels like adding a Transformers model class: one loader/client, one recipe, one fake contract test, one optional real smoke.

## Current Baseline

Already shipped:

- SDK-first runtime recovery for ASR, LLM, and TTS.
- Legacy `Voice-Agent/config.yaml` bridge with preserved model recipes.
- ASR SDK registry with `qwen3`, `nemotron`, `silero` lazy loaders.
- LLM SDK registry with OpenAI-compatible client, response processor, turn coordinator, metrics shell, conversation manager.
- TTS SDK registry with OpenAI-compatible and local model providers.
- Real Kokoro TTS loader and successful CPU WAV smoke.
- Qwen3 fake smoke path through the actual SDK loader contract.
- Qwen3 GPU-tested config fidelity preserved from old FLOW config.
- Full test suite currently green: `79 passed`.

Latest commits:

- `66b5d76 Preserve tested Qwen3 ASR GPU config`
- `3c005fa Add real TTS and ASR smoke paths`
- `31d0311 Add PolyVoice SDK-first runtime recovery`

## Sprint Rules

- No runtime rewrites for new model support.
- New model support must go through SDK loader/client registries.
- Heavy dependencies stay optional and lazy.
- Every model/provider gets:
  - one loader/client file
  - one recipe/config path
  - one fake no-heavy-dependency test
  - one real smoke path when practical
- Each sprint ends with a demo or a clear blocker log.
- Keep `main` green before every commit.

## Definition of Done

Before closing any sprint:

- `python -m pytest tests/unit tests/integration/test_pipeline_mocks.py tests/integration/test_pipeline_sdks.py` passes.
- New model/provider can be selected through config, not hardcoded in runtime.
- Optional dependency failure is typed and readable.
- Docs or examples show the command to run.
- Any real smoke artifact path is recorded in the sprint notes.

---

## Sprint 1: Extension Architecture Lock-In

Goal: make “add a model like Transformers” explicit and hard to regress.

Deliverables:

- [ ] `docs/adding-models.md`
  - ASR model loader contract.
  - ASR VAD contract.
  - LLM client contract.
  - TTS model loader contract.
  - Optional dependency pattern.
  - Fake test pattern.
  - Real smoke pattern.
- [ ] `scripts/scaffold_model_loader.py`
  - `--kind asr --name <model>`
  - `--kind vad --name <provider>`
  - `--kind llm --name <client>`
  - `--kind tts --name <model>`
  - Generates loader/client skeleton plus starter test.
- [ ] Golden extension tests:
  - ASR fake model works without runtime/bootstrap edits.
  - VAD fake provider works without runtime/bootstrap edits.
  - LLM fake client works without runtime/bootstrap edits.
  - TTS fake loader works without runtime/bootstrap edits.
- [ ] `RECOVERY_PLAN.md` updated with the registry-first rule.

Exit demo:

- Scaffold a dummy model, run its generated test, then delete or keep as a documented example.

---

## Sprint 2: Real Local Model Bring-Up

Goal: move from architecture recovery to real model proof.

Deliverables:

- [x] Kokoro CPU smoke path.
- [x] Kokoro real smoke succeeded: `C:\tmp\kokoro_smoke.wav`.
- [x] Qwen3 fake smoke path.
- [ ] Qwen3 real GPU smoke.
  - Install path: `polyvoice[qwen3-asr]`.
  - Uses old tested values:
    - `device: cuda`
    - `gpu_memory_utilization: 0.08`
    - `max_model_len: 4096`
    - `max_inference_batch_size: 32`
    - `max_new_tokens: 256`
    - `vad.provider: silero`
- [ ] Silero real VAD smoke.
- [ ] One real-ish local chain:
  - `Qwen3 ASR -> mock or OpenAI-compatible LLM SDK -> Kokoro TTS`.

Exit demo:

- A local WAV input produces transcript and Kokoro audio output, with the exact config file checked in.

Blockers to track:

- `qwen-asr[vllm]` install/platform support.
- CUDA availability and model download.
- HF cache/auth/rate-limit issues.

---

## Sprint 3: Old FLOW Intelligence Port

Goal: port the old runtime intelligence that made FLOW feel good in live voice.

Deliverables:

- [ ] ASR streaming processor parity:
  - rolling buffer
  - sliding windows
  - Qwen3 hallucination guard
  - onset gate
  - partial stability
  - finalization rules
- [ ] Silero VAD state handling:
  - session-safe state
  - watchdog reset
  - threshold/onset/offset/hangover config
- [ ] Turn endpointing:
  - SmartTurn hooks
  - semantic timeout
  - VAD fallback finalization
- [ ] Barge-in:
  - volume barge-in detector
  - command/interruption priority into LLM SDK
- [ ] LLM stream polish:
  - backpressure strategy
  - adaptive chunking
  - interruption handling
  - conversation summary API

Exit demo:

- A mock real-time audio stream produces partials, stable final, LLM response chunks, and TTS chunks with interruption path covered by tests.

---

## Sprint 4: End-to-End Runtime And UI Parity

Goal: make PolyVoice usable as the backend instead of the old `Voice-Agent`.

Deliverables:

- [ ] Runtime route parity for `flow-ui` voice test page.
- [ ] `/config/status` includes selected ASR/LLM/TTS recipes and provider names.
- [ ] Hot-swap ASR/LLM/TTS config route with a single registry/service mutex.
- [ ] WebSocket event compatibility with `flow-ui/src/hooks/use-voice-session.ts`.
- [ ] Health/readiness endpoints include model loaded/unloaded state.
- [ ] One command local demo:
  - start server
  - connect smoke client
  - send audio
  - receive transcript, LLM chunks, TTS audio

Exit demo:

- `flow-ui` can hit PolyVoice for the voice test path without old backend assumptions.

---

## Sprint 5: Telephony And Production Hardening

Goal: prepare real call paths after the core voice loop is trustworthy.

Deliverables:

- [ ] Telephony base adapter.
- [ ] Twilio Media Streams adapter.
- [ ] FreeSWITCH adapter.
- [ ] Asterisk AudioSocket adapter.
- [ ] Codec negotiation and normalization.
- [ ] Audit log.
- [ ] OpenTelemetry spans:
  - audio in
  - ASR partial/final
  - LLM first token/complete
  - TTS first audio/complete
- [ ] Production fixes:
  - CORS lock-down
  - graceful shutdown
  - backpressure policy
  - typed config errors

Exit demo:

- Same mock voice agent runs unchanged behind at least one telephony adapter.

---

## Immediate Next Work

Do these next, in order:

1. Sprint 1 docs and scaffold script.
2. Real Qwen3 GPU smoke attempt using old tested config.
3. Port ASR streaming processor parity from old FLOW.
4. Build one full local demo config:
   - `qwen3` ASR
   - OpenAI-compatible or mock LLM
   - Kokoro TTS
5. Wire `flow-ui` voice test path to PolyVoice.

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---:|---:|---|
| Qwen3/vLLM install fails on Windows | High | High | Keep fake smoke; document Linux/CUDA path; use WSL or cloud GPU for real smoke |
| Old ASR streaming processor is large | High | Medium | Port module-by-module with tests: VAD state, buffer, finalization, onset gate |
| Runtime becomes hardcoded again | Medium | High | Enforce registry-first tests and scaffold flow |
| Kokoro HF downloads flaky | Medium | Medium | Cache model/voice files; document HF token and cache path |
| UI route mismatch | Medium | Medium | Keep WebSocket event names compatible before adding new UI features |

## What We Are Not Doing Yet

- No benchmark harness until real end-to-end local demo works.
- No docs-site polish until `docs/adding-models.md` and model scaffolding exist.
- No telephony-first work until the SDK runtime path is demoable.
- No copying the old monolith wholesale.
