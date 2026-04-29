# PolyVoice — Master Context

**This is the doc to read first.** Whether you're a contributor, a reviewer, or an AI coding assistant, everything you need to make a sound contribution starts here.

---

## What PolyVoice is

A model-agnostic, platform-agnostic open framework for building **local-first** voice agents that run in production telephony deployments — especially in regulated industries (healthcare, banking, telecom, government) where on-premises is mandatory.

The full positioning is in [`VISION.md`](./VISION.md). Read it before submitting a PR.

## What problem we are solving

**Existing voice agent stacks split into two camps**, and both fail the regulated/on-prem segment:

1. **Cloud-locked platforms** (Vapi, Retell, Cresta, OpenAI Realtime, Gemini Live) — closed, cannot be deployed on-prem, cannot be HIPAA-compliant without major engineering.
2. **Open WebRTC frameworks** (Pipecat, LiveKit Agents, Daily) — open and great, but cloud-API-led by default. Local model support exists but is retrofit; FreeSWITCH/Asterisk are second-class; HIPAA-mode profiles don't exist.

**PolyVoice fills the slot:** open, local-first by default, telephony-native, compliance-aware. Not a replacement for Pipecat — a complement aimed at the segment Pipecat doesn't optimize for.

## What we are not building

Read these explicitly so you don't waste time on out-of-scope work:

- ❌ A WebRTC SFU (use LiveKit / Daily)
- ❌ A multi-modal vision/avatar framework (use Pipecat / HeyGen)
- ❌ A cloud realtime API (use OpenAI / Gemini)
- ❌ A browser-only chat-style voice product (use Vapi / Retell)
- ❌ A mobile SDK or IDE plugin
- ❌ Pipecat parity on cloud-API breadth (we'll always be behind there, deliberately)

If a feature request fits one of these, the answer is "out of scope, here's why" with a link to [VISION.md](./VISION.md).

## Architecture in one paragraph

A voice agent is decomposed into **services** (ASR, LLM, TTS, VAD), **telephony adapters** (CPaaS providers), an **orchestration layer** (barge-in, fillers, turn-taking, tool calling), an **agents layer** (executor, tools, RAG), and an **observability layer** (OTEL, audit). Services and adapters implement uniform abstract base classes, so any combination can be wired at runtime via config — vLLM-served local models are first-class peers to cloud APIs. The orchestrator is event-driven over WebSocket (not frame-based) and exposes a small `Processor` base for external contributors. Audio is normalized to PCM16/16k mono internally; codec conversion happens at the adapter edge. Full architectural rationale is in [`specs/00-architecture.md`](./specs/00-architecture.md).

## Six architectural commitments

These are non-negotiable. They flow from the vision and they shape every PR.

1. **vLLM-everywhere is the reference path.** Local models first-class.
2. **Hot-swap at runtime.** Every model/adapter is config-swappable.
3. **Telephony is core.** FreeSWITCH/Asterisk/SIP are first-class peers to Twilio/Vonage.
4. **Compliance is a first-class concern.** HIPAA-mode and PCI-mode are config profiles.
5. **Orchestration techniques ship in core.** Barge-in, fillers, RAG, escalation — not examples.
6. **Event-driven WebSocket pipeline + minimal Processor abstraction.** Not frame-based. Defended choice.

## How the codebase is organized

See [`STRUCTURE.md`](./STRUCTURE.md) for the canonical file tree.

Top-level layers (mirror in `src/polyvoice/`):

| Layer | Purpose | Touches GPU? |
|---|---|---|
| `core/` | Processor base, events, session state | No |
| `config/` | Pydantic config models + loader | No |
| `services/` | ASR / LLM / TTS / VAD plugins | Some |
| `audio/` | Codec normalization, resampling, AGC | No (pure DSP) |
| `telephony/` | CPaaS adapters | No |
| `orchestration/` | Barge-in, TTS control, turn coordination | No |
| `agents/` | Executor, tools, filler scheduling | No |
| `knowledge/` | RAG, vector store, reranker | Light (embedding model only) |
| `observability/` | OTEL, audit logs, metrics | No |
| `runtime/` | Server bootstrap + lifecycle | No |
| `transport/` | FastAPI routes + WebSocket protocol | No |

**~85% of the codebase has no GPU dependency.** That's deliberate. It means most development is mock-driven and most tests run on CPU.

## How to make a change

1. Read the relevant spec in `specs/`. If a spec is missing, write one in the same PR.
2. Read [`CONTRIBUTING.md`](./CONTRIBUTING.md).
3. Add or update a unit test. If your change touches a public API, the test goes in `tests/unit/`. If it touches multiple modules, add an integration test in `tests/integration/`.
4. Update `CHANGELOG.md` under `## Unreleased`.
5. Run `pre-commit run --all-files`, `mypy src/`, `pytest tests/unit`.
6. Open a PR. CODEOWNERS will route it to the right reviewers.

## How to read the specs

Specs in `specs/` are numbered by build order. Lower numbers are foundational; higher numbers depend on earlier ones.

Each spec contains:
- **Purpose** — what this module does and why
- **Interface** — Python ABCs, function signatures, types
- **Behavior** — concrete behavioral contracts (events fired, errors raised)
- **Test cases** — what tests must pass for the module to be "done"
- **Dependencies** — which other specs/modules this depends on
- **References** — files in the existing NetoAI Voice-Agent codebase to port from, if any

A coding agent (Codex, Claude Code, Cursor) should be able to implement a module given only its spec + the dependency specs + the existing codebase.

## How to read the sprint plan

[`SPRINT_PLAN.md`](./SPRINT_PLAN.md) lists 6 one-week sprints. Each sprint has:
- A goal
- A list of files to create or modify
- A "definition of done" gate
- A version tag at the end

The sprint plan is the contract. Don't deviate without a PR that updates it.

## Status today

- **Sprint 0 (in progress):** repo hygiene + specs + sprint plan. No feature code yet.
- **Code phase:** Sprints 1–5. Mock-driven, no GPU required.
- **Benchmark phase:** Sprint 6. NetoAI India team runs the matrix on real hardware.
- **Paper:** drafted across Sprints 4–6, submitted only after benchmark numbers land.

## What you'll find in the existing NetoAI codebase

The reference implementation is in the `Voice-Agent-feature-voice-pipeline-e2e` zip / branch. Notable files to port from:

| Existing file | Goes to | Notes |
|---|---|---|
| `app/orchestration/barge_in.py` | `src/polyvoice/orchestration/barge_in.py` | Already clean — minor refactor only |
| `app/orchestration/tts_control.py` | `src/polyvoice/orchestration/tts_control.py` | Port as-is |
| `app/orchestration/state.py` | `src/polyvoice/core/session.py` | Rename + clean |
| `app/contracts/voice_events.py` | `src/polyvoice/core/events.py` | Port + extend with telephony events |
| `voice_orchestrator.py` | `src/polyvoice/orchestration/orchestrator.py` | Heavy refactor; extract mixins to focused modules |
| `asr/processing/barge_in_classifier.py` | `src/polyvoice/orchestration/barge_in.py` (classifier portion) | Port |
| `agents_sdk/core/agent_executor.py` | `src/polyvoice/agents/executor.py` | Port two-pass logic |
| `agents_sdk/core/tool_timing_oracle.py` | `src/polyvoice/agents/timing_oracle.py` | Port |
| `agents_sdk/core/state_tracker.py` | `src/polyvoice/agents/state_tracker.py` | Port |
| `agents_sdk/knowledge/rag_tool.py` | `src/polyvoice/knowledge/rag.py` | Port |
| `tts_sdk/sdk/streaming_sdk.py` | `src/polyvoice/services/tts/__init__.py` (factory) | Refactor as registry |
| `tts_sdk/providers/*` | `src/polyvoice/services/tts/<provider>.py` | One file per provider |
| `tts_sdk/model_loaders/*` | merged into the per-provider files | |
| `asr/sdk/streaming_sdk.py` | `src/polyvoice/services/asr/__init__.py` (factory) | Refactor as registry |
| `asr/processing/agc.py` | `src/polyvoice/audio/agc.py` | Port |
| `asr/processing/streaming_processor.py` | split between `src/polyvoice/services/asr/` and `src/polyvoice/orchestration/` | Heavy refactor |
| `vllm_omni/model_executor/stage_configs/voxtral_tts.yaml` | `src/polyvoice/services/tts/voxtral_omni.py` (config) + `examples/` | Wrap as a service |
| `unified_server.py` | `src/polyvoice/runtime/server.py` | Port + add lifecycle hooks |

The legacy `Voice-Agent` zip will not be checked into PolyVoice. Port code, attribute appropriately in commit messages, then archive the zip.

## What you'll find in adjacent projects (read but don't copy)

Useful references for "what good looks like":
- **Pipecat** — service plugin shape (`pipecat-ai/pipecat:src/pipecat/services/`), telephony serializers (`src/pipecat/serializers/`), context aggregator pattern, OTEL observers.
- **LiveKit Agents** — plugin contract, model overview docs, Adaptive Interruption Handling.
- **vLLM-Omni** — multi-stage pipeline pattern with shared-memory connectors.

We borrow patterns; we don't fork.

## Conventions worth memorizing

- **No bare prints in library code** — use `loguru.logger`.
- **No `Optional[X]` in new code** — use `X | None` (PEP 604).
- **All public APIs have type hints + docstrings.**
- **Async by default** in I/O paths; sync helpers are for pure compute.
- **Config goes through Pydantic.** No raw dicts in new code.
- **Errors raise `polyvoice.core.exceptions.<Specific>Error`.** Never bare `Exception`.
- **GPU-required tests are marked `@pytest.mark.gpu`.** Never assume GPU in CI.
- **Telephony tests against real providers are marked `@pytest.mark.telephony`.** Never run in CI.

## Who owns what

Core team: **NetoAI engineering** (`@netoai/engineering` on GitHub). Specialized review:
- Audit / compliance code → `@netoai/security` and `@netoai/compliance`
- Service plugins (ASR/LLM/TTS) → `@netoai/ml`
- Benchmarks → `@netoai/india-team`
- Paper / research artifacts → `@netoai/research`

CODEOWNERS file ([`/.github/CODEOWNERS`](./.github/CODEOWNERS)) is the source of truth.

## When you don't know what to do next

1. Check the active sprint in [`SPRINT_PLAN.md`](./SPRINT_PLAN.md).
2. Look at the spec for the file you're touching.
3. If still stuck, open a discussion or DM `@netoai/engineering`.

## License

Apache 2.0. Patent grant included. Permissive enough for commercial deployment, restrictive enough that contributors keep credit.
