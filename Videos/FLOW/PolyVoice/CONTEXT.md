# PolyVoice Master Context

**Read this first.** Whether you are a contributor, reviewer, or AI coding assistant, this file explains the shape of the project and the current recovery state.

## What PolyVoice Is

PolyVoice is a model-agnostic, platform-agnostic open framework for building local-first voice agents, especially for regulated environments where on-premises deployment matters.

The full positioning is in [`VISION.md`](./VISION.md). The live recovery plan is in [`SPRINT_PLAN.md`](./SPRINT_PLAN.md), [`RECOVERY_PLAN.md`](./RECOVERY_PLAN.md), and [`BUILD_ORDER.md`](./BUILD_ORDER.md).

## Current State

The repo is no longer only a scaffold. It now has a working SDK-first baseline:

- Config models, recipe loading, and selected legacy FLOW config bridging.
- Mock runtime and integration pipeline tests.
- Audio frames, codec helpers, resampling, and AGC utilities.
- TTS SDK with provider, codec, and model-loader registries.
- Kokoro local TTS loader and smoke script.
- ASR SDK with model-loader registry, Qwen3/Nemotron loader shape, VAD registry, and streaming processor.
- Qwen3 ASR local example preserving the old GPU-tested FLOW defaults.
- LLM SDK with OpenAI-compatible client, conversation state, response processing, turn coordination, and service wrapper.
- OpenAI-compatible LLM/TTS examples.

The repo is still pre-alpha. Telephony adapters, production orchestration, agent tools, RAG, observability, and compliance profiles are planned but not done.

## Architectural Commitments

These are still the rails:

1. **Local models are first-class.** vLLM and local runtime paths are reference use cases, not afterthoughts.
2. **Runtime hot-swap stays config-driven.** New model support should not require runtime rewrites.
3. **Telephony is core.** FreeSWITCH, Asterisk, SIP, and CPaaS adapters remain first-class targets.
4. **Compliance matters.** HIPAA/PCI-style deployment constraints shape logging, audit, and data flow.
5. **Orchestration ships in core.** Barge-in, fillers, tool timing, RAG, and escalation are not just demo examples.
6. **The pipeline is event-oriented.** Do not collapse the design into a generic frame-only clone.

## How The Codebase Is Organized

Implemented recovery areas:

| Area | Current location | Notes |
|---|---|---|
| Config | `src/polyvoice/config/` | Models, loader, recipes, legacy bridge |
| Audio | `src/polyvoice/audio/` | Frames, codecs, resampling, AGC |
| Runtime | `src/polyvoice/runtime/` | Bootstrap, pipeline, health, server |
| Transport | `src/polyvoice/transport/` | WebSocket voice transport |
| Mock services | `src/polyvoice/services/mocks.py` | CPU-safe test pipeline |
| ASR SDK | `src/polyvoice/services/asr_sdk/` | Registry-first ASR model/VAD support |
| LLM SDK | `src/polyvoice/services/llm_sdk/` | OpenAI-compatible client and turn helpers |
| TTS SDK | `src/polyvoice/services/tts_sdk/` | Provider/codec/model-loader split |

Planned or partial areas:

| Area | Target |
|---|---|
| Telephony | FreeSWITCH, Asterisk, Twilio, Vonage, Telnyx, Plivo, raw SIP |
| Orchestration | barge-in, TTS control, filler scheduling, interruption preservation |
| Agents | executor, tools, timing oracle, state tracker |
| Knowledge | RAG, vector store, reranker |
| Observability | OpenTelemetry, metrics, audit logs |
| Compliance | HIPAA/PCI configuration profiles |

## How To Make A Change

1. Read [`SPRINT_PLAN.md`](./SPRINT_PLAN.md), [`RECOVERY_PLAN.md`](./RECOVERY_PLAN.md), and [`BUILD_ORDER.md`](./BUILD_ORDER.md).
2. For model support, use the existing SDK extension path: add a loader/client/provider, register it, add a recipe or example, add a focused unit test, then add a smoke path if the dependency is heavy.
3. If a formal spec exists for the area, follow it. If a spec is absent or stale, update the relevant plan/doc in the same change instead of silently inventing architecture.
4. Add or update tests. CPU-safe tests are the default; GPU tests must be marked `@pytest.mark.gpu`.
5. Update [`CHANGELOG.md`](./CHANGELOG.md) under `## [Unreleased]`.

Useful verification commands:

```bash
python -m pytest tests/unit tests/integration/test_pipeline_mocks.py tests/integration/test_pipeline_sdks.py
python scripts/kokoro_smoke.py --device cpu --output C:\tmp\kokoro_smoke.wav
python scripts/qwen3_asr_smoke.py --fake-qwen-asr --language en --device cpu
```

## Legacy FLOW Porting Map

The old FLOW/Voice-Agent codebase had important working pieces. Port behavior and tested configuration, not old file structure.

| Legacy source | Current or target PolyVoice home | State |
|---|---|---|
| `tts_sdk/model_loaders/kokoro_loader.py` | `src/polyvoice/services/tts_sdk/model_loaders/kokoro.py` | Recovered |
| `tts_sdk/sdk/streaming_sdk.py` | `src/polyvoice/services/tts_sdk/sdk.py` | Recovered baseline |
| `asr/models/qwen3_asr.py` | `src/polyvoice/services/asr_sdk/models/qwen3.py` | Recovered baseline |
| `asr/models/silero_vad.py` | `src/polyvoice/services/asr_sdk/vad/silero.py` | Recovered baseline |
| Qwen3 GPU config in `Voice-Agent/config.yaml` | `examples/qwen3-asr-local/config.yaml` and legacy recipe bridge | Preserved |
| `llm/processing/response_processor.py` | `src/polyvoice/services/llm_sdk/response_processor.py` | Recovered baseline |
| `voice_orchestrator.py` | `src/polyvoice/orchestration/` | Planned |
| `app/orchestration/barge_in.py` | `src/polyvoice/orchestration/barge_in.py` | Planned |
| `agents_sdk/core/agent_executor.py` | `src/polyvoice/agents/executor.py` | Planned |
| `agents_sdk/knowledge/rag_tool.py` | `src/polyvoice/knowledge/rag.py` | Planned |
| `unified_server.py` | `src/polyvoice/runtime/server.py` | Partial runtime recovered |

## Conventions

- Python 3.11+, full type hints, `X | None` over `Optional[X]`.
- Pydantic config models for structured configuration.
- Async by default in I/O paths.
- No secrets, API keys, model weights, generated audio files, or DB files in git.
- No generic `utils.py`, `helpers.py`, `common.py`, `misc.py`, `*_v2.py`, or `*_old.py`.
- GPU-required tests are marked `@pytest.mark.gpu`.
- Telephony tests against real providers are marked `@pytest.mark.telephony`.

## When You Do Not Know What To Do Next

1. Check [`SPRINT_PLAN.md`](./SPRINT_PLAN.md).
2. Check [`RECOVERY_PLAN.md`](./RECOVERY_PLAN.md) for missing parity.
3. Check [`BUILD_ORDER.md`](./BUILD_ORDER.md) for the next high-value target.
4. If touching model support, keep the SDK extension contract intact.

## License

Apache 2.0. Patent grant included.
