# PolyVoice Recovery Plan

This document tracks the migration from the older working `Voice-Agent` codebase into the cleaner public `PolyVoice` package. It is intentionally stateful: update it whenever the real state changes.

## Current Reality

### PolyVoice

`PolyVoice` is no longer only a public scaffold. It now has a working SDK-first runtime core with mock end-to-end flow, audio utilities, legacy config loading, and first real model smoke paths.

What exists:

- Public project docs: `README.md`, `VISION.md`, `CONTEXT.md`, `STRUCTURE.md`, `SPRINT_PLAN.md`, `BUILD_ORDER.md`, `AGENTS.md`, `SECURITY.md`, `CHANGELOG.md`.
- Package metadata and optional extras in `pyproject.toml`.
- Core abstractions:
  - `core/events.py`
  - `core/processor.py`
  - `core/session.py`
  - `core/exceptions.py`
  - `services/base.py`
  - `services/registry.py`
- Config:
  - Pydantic config models.
  - YAML/env loader.
  - Legacy `Voice-Agent/config.yaml` bridge.
  - Preserved ASR/LLM/TTS model recipes.
- Audio:
  - PCM16/float conversion.
  - WAV wrapping/unwrapping.
  - mu-law/A-law.
  - resampling.
  - AGC.
- Runtime:
  - FastAPI server.
  - health/config status.
  - WebSocket voice transport.
  - mock ASR -> LLM -> TTS pipeline.
- SDK-first services:
  - ASR SDK with model registry, VAD registry, `qwen3`, `nemotron`, `silero` lazy loaders.
  - LLM SDK with client registry, OpenAI-compatible client, response processor, turn coordinator, metrics, conversation manager.
  - TTS SDK with local-model provider, OpenAI-compatible provider, Kokoro loader.
- Examples and smokes:
  - mock runtime.
  - OpenAI-compatible LLM.
  - OpenAI-compatible TTS.
  - Kokoro local TTS.
  - Qwen3 ASR local/fake smoke.
- Tests:
  - unit coverage for core/config/audio/services/runtime.
  - mock integration pipeline.
  - SDK-backed integration pipeline.
  - latest known full suite: `79 passed`.

Validated real smoke:

- Kokoro CPU TTS wrote `C:\tmp\kokoro_smoke.wav`.
- WAV metadata: mono, 24 kHz, 2.325 seconds.

Validated fake smoke:

- Qwen3 fake ASR smoke exercises the actual SDK loader path and returns `hello from fake qwen3`.

Still missing:

- Real Qwen3 GPU smoke with `qwen-asr[vllm]`.
- Full old ASR streaming processor parity:
  - rolling buffer
  - sliding windows
  - onset gate
  - partial stability
  - SmartTurn endpointing
  - finalization rules
  - full Qwen3 hallucination guard behavior
- Orchestration layer:
  - barge-in
  - TTS pause/resume/cancel
  - interruption context
  - filler scheduling
  - tool execution
- Telephony adapters:
  - Twilio
  - FreeSWITCH
  - Asterisk
  - other CPaaS/SIP adapters
- Observability:
  - OpenTelemetry spans
  - audit log
  - metrics surfaces beyond SDK counters
- API/UI parity with `flow-ui`.
- Benchmark harness and docs site.

### Voice-Agent

`Voice-Agent` is the older working implementation. It remains the behavioral reference.

What to preserve from it:

- SDK-first model extension style.
- Tested Qwen3 GPU settings:
  - `device: cuda`
  - `gpu_memory_utilization: 0.08`
  - `max_model_len: 4096`
  - `max_inference_batch_size: 32`
  - `max_new_tokens: 256`
  - `chunk_size_sec: 0.032`
  - `final_padding_sec: 0.08`
  - `vad.backend: silero`
- ASR/VAD behavior:
  - Qwen3 and Nemotron wrappers.
  - Silero VAD.
  - SmartTurn.
  - AGC, punctuation, noise tracking, interruption and barge-in logic.
- LLM behavior:
  - streaming SDK.
  - response processor.
  - turn coordinator.
  - conversation manager.
  - backpressure manager.
- TTS behavior:
  - streaming SDK.
  - provider/model-loader separation.
  - Kokoro, Soprano, Chatterbox, Maya-style loaders.

Risks:

- Old implementation has large mixed-concern files.
- Some runtime behavior is coupled to local demos.
- Some docs/output have encoding artifacts.
- Some pieces are valuable behavior but not clean public API.

### flow-ui

`flow-ui` is still pointed at the old backend shape.

What exists:

- Auth pages.
- Agents CRUD screens.
- Tool creation/list screens.
- Knowledge base/forum/document screens.
- Settings page for ASR/TTS/LLM hot-swap.
- Voice test page with real mic capture, WebSocket streaming, transcript state, and TTS playback.

What remains:

- Route parity from PolyVoice.
- Event compatibility for the voice test page.
- Placeholder call history/detail/tool edit pages.

## Strategy

Use `Voice-Agent` for working behavior and `PolyVoice` for clean shape.

Rules:

1. Do not copy `Voice-Agent` wholesale.
2. Preserve the SDK-first model extension style.
3. New model support must go through loader/client registries.
4. Heavy model dependencies stay optional and lazy.
5. Every model/provider path gets:
   - loader/client
   - recipe/config
   - fake contract test
   - real smoke when practical

## Active Migration Slices

### Slice 1: Mock Runtime

Status: mostly shipped.

Shipped:

- Config models and loader.
- Mock services.
- Runtime bootstrap/server/health.
- WebSocket voice transport.
- Mock ASR -> LLM -> TTS integration tests.

Remaining:

- Confirm full `flow-ui` event compatibility.
- Add richer `/config/status` detail for selected recipes.

### Slice 2: Audio Foundation

Status: shipped enough for current runtime.

Shipped:

- codecs
- resample
- AGC
- frames
- unit tests

Remaining:

- Telephony-specific codec negotiation when adapters land.

### Slice 3: SDK-First Services

Status: active, with extension architecture locked in.

Shipped:

- ASR SDK registry.
- LLM SDK registry.
- TTS SDK registry.
- Model-extension docs.
- Model scaffold script.
- Golden ASR/VAD/LLM/TTS extension contract tests.
- OpenAI-compatible LLM/TTS.
- Kokoro real TTS loader.
- Qwen3/Nemotron/Silero lazy ASR/VAD loaders.
- Legacy recipe activation into SDK configs.

Remaining:

- Real Qwen3 GPU smoke.
- Silero real VAD smoke.
- More LLM clients using the same registry pattern.

### Slice 4: Old FLOW Intelligence

Status: next major implementation slice.

Port from old FLOW:

- ASR streaming processor.
- VAD state machine.
- onset gate.
- finalization logic.
- Qwen3 hallucination suppression.
- SmartTurn endpointing.
- barge-in classifier.
- LLM backpressure/adaptive chunking.

Definition of done:

- Tests cover partials, stable finals, low-confidence suppression, endpointing, and interruption.

### Slice 5: Runtime/UI Parity

Status: not started.

Build:

- route parity for `flow-ui`
- richer config APIs
- hot-swap with mutex
- readiness around loaded models
- one-command local demo

### Slice 6: Telephony

Status: deferred until internal voice loop is trustworthy.

Build:

- telephony base
- Twilio
- FreeSWITCH
- Asterisk
- codec normalization at adapter edge

## Immediate Next Targets

1. Attempt real Qwen3 GPU smoke using preserved old config.
2. Port old ASR streaming processor behavior in small tested modules.
3. Build full local demo config:
   - Qwen3 ASR
   - mock or OpenAI-compatible LLM
   - Kokoro TTS
4. Start `flow-ui` voice-test route parity.

## Non-Goals For This Recovery Phase

- Do not start benchmarks before a real local demo works.
- Do not build telephony before the SDK voice loop is stable.
- Do not copy monolithic old files directly.
- Do not add providers by editing runtime/bootstrap every time.
