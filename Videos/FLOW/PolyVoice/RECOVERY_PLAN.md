# PolyVoice Recovery Plan

This document captures the current reality of the workspace and the practical path from the older working codebase to the newer public `PolyVoice` package.

## Current Reality

### PolyVoice

`PolyVoice` is currently a clean public scaffold, not yet the working product.

What exists:

- Public project docs: `README.md`, `VISION.md`, `CONTEXT.md`, `STRUCTURE.md`, `SPRINT_PLAN.md`, `BUILD_ORDER.md`, `AGENTS.md`, `SECURITY.md`, `CHANGELOG.md`.
- Package metadata in `pyproject.toml`.
- Minimal importable package under `src/polyvoice`.
- Basic core abstractions:
  - `core/events.py`
  - `core/processor.py`
  - `core/session.py`
  - `core/exceptions.py`
  - `services/base.py`
  - `services/registry.py`
- Small unit test set covering the current basics.

What is missing:

- Config models and config loader.
- Audio normalization utilities: codecs, resampling, frames, AGC.
- Telephony abstractions and adapters.
- Runtime server, lifecycle, health checks, WebSocket transport, and HTTP config routes.
- Real ASR, LLM, and TTS implementations.
- Orchestration: turn coordination, barge-in, TTS control, interruption handling.
- Agent/tool execution layer.
- Knowledge/RAG layer.
- Observability: audit log, metrics, tracing.
- CLI entry point.
- Examples, benchmark harness, and docs site.

### Voice-Agent

`Voice-Agent` is the older working implementation. It is messy but valuable.

What exists:

- End-to-end ASR -> LLM -> TTS voice pipeline.
- FastAPI/WebSocket backend.
- Runtime config switching.
- Browser-facing voice WebSocket protocol.
- ASR/VAD modules:
  - Nemotron/Qwen3 ASR wrappers.
  - Silero VAD.
  - SmartTurn.
  - AGC, punctuation, noise tracking, interruption and barge-in logic.
- LLM modules:
  - Streaming SDK.
  - OpenAI-compatible/Mistral/vLLM-style client support.
  - Conversation manager, response processor, turn coordinator, backpressure manager.
- TTS modules:
  - Streaming SDK.
  - OpenAI-compatible provider.
  - Local model loaders for Magpie, Soprano, Kokoro, Chatterbox, Maya-style loaders.
  - Audio pipeline, text pipeline, resampler, codecs.
- Agents/tools/knowledge subsystems.
- Auth, permissions, SQLAlchemy models, repositories, migrations.
- Streamlit and Gradio UIs.
- Local demo data and development scripts.

Risks:

- Large mixed-concern files, especially `voice_orchestrator.py`.
- Some runtime behavior is coupled to local demo assumptions.
- Some TODOs and `NotImplementedError` paths remain in tool/database backends.
- Production hardening is uneven.
- Some docs/output have encoding artifacts.

### flow-ui

`flow-ui` is a Next.js dashboard pointed at the old backend shape.

What exists:

- Auth pages.
- Agents CRUD screens.
- Tool creation/list screens.
- Knowledge base/forum/document screens.
- Settings page for ASR/TTS/LLM hot-swap.
- Voice test page with real mic capture, WebSocket streaming, transcript state, and TTS playback.

What is placeholder:

- Call history page.
- Call detail page.
- Tool edit page.

## Strategy

Use the old codebase for working behavior and the new package for clean shape.

Do not copy `Voice-Agent` wholesale. Port vertical slices that can be tested and run independently.

The target is:

1. `PolyVoice` owns the production package, runtime, APIs, tests, and examples.
2. `Voice-Agent` remains a reference implementation during migration.
3. `flow-ui` stays wired to the old API until `PolyVoice` reaches route parity.

## Migration Slices

### Slice 1: Mock End-to-End Runtime

Goal: make `PolyVoice` run a voice WebSocket session with mock services.

Build:

- `polyvoice/config/models.py`
- `polyvoice/config/loader.py`
- `polyvoice/audio/frames.py`
- `polyvoice/runtime/server.py`
- `polyvoice/runtime/bootstrap.py`
- `polyvoice/runtime/health.py`
- `polyvoice/transport/ws_voice.py`
- `polyvoice/transport/http_routes.py`
- `tests/mocks/stt.py`
- `tests/mocks/llm.py`
- `tests/mocks/tts.py`
- `tests/integration/test_pipeline_mocks.py`

Source references:

- `Voice-Agent/app/runtime/bootstrap.py`
- `Voice-Agent/app/runtime/server_runtime.py`
- `Voice-Agent/app/transport/server_app.py`
- `Voice-Agent/app/transport/voice_ws.py`
- `Voice-Agent/app/contracts/voice_events.py`

Definition of done:

- `pytest tests/unit tests/integration/test_pipeline_mocks.py` passes.
- A local WebSocket client can connect, send audio bytes, receive ready/transcript/LLM/TTS events.

### Slice 2: Audio Foundation

Goal: lock audio data types and conversion behavior before telephony.

Build:

- `polyvoice/audio/codecs.py`
- `polyvoice/audio/resample.py`
- `polyvoice/audio/agc.py`
- codec/frame tests.

Source references:

- `Voice-Agent/tts_sdk/pipeline/resampler.py`
- `Voice-Agent/tts_sdk/pipeline/format_converter.py`
- `Voice-Agent/asr/processing/agc.py`
- `Voice-Agent/tts_sdk/codecs/`

Definition of done:

- Deterministic tests for PCM16, mulaw, alaw, WAV-ish framing where applicable.
- Audio chunks have one canonical internal format: PCM16 mono 16 kHz unless explicitly declared otherwise.

### Slice 3: Service Implementations

Goal: make the service ABCs useful with real providers.

Build:

- `polyvoice/services/llm/openai_compat.py`
- `polyvoice/services/tts/openai_compat.py`
- `polyvoice/services/tts/kokoro.py` or first local TTS adapter.
- `polyvoice/services/asr/*` after the mock runtime is stable.

Source references:

- `Voice-Agent/llm/sdk/streaming_sdk.py`
- `Voice-Agent/llm/models/llm_client.py`
- `Voice-Agent/tts_sdk/sdk/streaming_sdk.py`
- `Voice-Agent/tts_sdk/providers/openai_compatible.py`
- `Voice-Agent/asr/sdk/streaming_sdk.py`

Definition of done:

- Mock services and one real LLM/TTS path share the same public interface.
- Provider failures produce typed `PolyVoiceError` subclasses.

### Slice 4: Orchestration

Goal: port the actual turn-taking intelligence without preserving the old monolith.

Build:

- `polyvoice/orchestration/orchestrator.py`
- `polyvoice/orchestration/barge_in.py`
- `polyvoice/orchestration/tts_control.py`
- `polyvoice/orchestration/stream_state.py`
- `polyvoice/orchestration/turn_coordinator.py`
- `polyvoice/orchestration/interrupted_context.py`

Source references:

- `Voice-Agent/voice_orchestrator.py`
- `Voice-Agent/app/orchestration/`
- `Voice-Agent/asr/processing/barge_in_classifier.py`
- `Voice-Agent/llm/processing/turn_coordinator.py`
- `Voice-Agent/llm/processing/tts_coordinator.py`

Definition of done:

- Tests cover normal turn, interrupted turn, true barge-in, and backchannel/resume behavior.

### Slice 5: Telephony Adapters

Goal: add CPaaS/provider adapters on top of a stable internal voice pipeline.

Build:

- `polyvoice/telephony/base.py`
- `polyvoice/telephony/twilio.py`
- `polyvoice/telephony/freeswitch.py`
- `polyvoice/telephony/asterisk.py`

Definition of done:

- The same orchestrator runs unchanged behind Twilio, FreeSWITCH, and Asterisk mocks.
- Provider wire formats are normalized before entering orchestration.

### Slice 6: API Parity and UI Cleanup

Goal: move `flow-ui` from old backend routes to `PolyVoice` when ready.

Build or port:

- Auth strategy.
- Agent CRUD API.
- Tool CRUD API.
- Knowledge API.
- Calls/session history API.
- Config status/update API.

Then fix `flow-ui` placeholders:

- Replace call history placeholder with real session list.
- Replace call detail placeholder with transcript, timings, and metrics.
- Replace tool edit placeholder with the existing create form loaded from API state.

Definition of done:

- `flow-ui` can point to `PolyVoice` without route changes.
- Placeholder dashboard pages are gone.

## Immediate Next Targets

1. Build Slice 1 with mocks.
2. Keep the WebSocket event names compatible with `flow-ui/src/hooks/use-voice-session.ts`.
3. Add integration tests before porting the old orchestration.
4. Only after mock runtime works, start porting audio and real services.

## Non-Goals For The First Pass

- Do not port every provider at once.
- Do not rebuild the whole dashboard first.
- Do not copy the old monolithic orchestrator directly.
- Do not start with benchmark/docs-site work.
- Do not make telephony adapters before the internal mock voice loop is stable.

