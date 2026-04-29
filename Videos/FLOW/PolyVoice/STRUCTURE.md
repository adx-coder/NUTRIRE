# PolyVoice — Repository Structure

This file describes the target repository structure. During the current recovery sprint, the implemented subset is concentrated in `config`, `audio`, `runtime`, `transport`, and the `services/*_sdk` packages. Telephony, orchestration, agents, knowledge, observability, compliance profiles, docs site, and benchmarks are still planned or partial.

Use [`CONTEXT.md`](./CONTEXT.md), [`SPRINT_PLAN.md`](./SPRINT_PLAN.md), [`RECOVERY_PLAN.md`](./RECOVERY_PLAN.md), and [`BUILD_ORDER.md`](./BUILD_ORDER.md) for the live state. If you add a new architectural area, update this file in the same PR.

```
PolyVoice/
│
├── README.md                                 Public-facing pitch + status
├── LICENSE                                   Apache 2.0
├── VISION.md                                 The model+platform-agnostic local-first thesis
├── CONTEXT.md                                "Read me first" — master context doc for contributors / coding agents
├── STRUCTURE.md                              This file
├── SPRINT_PLAN.md                            6-sprint plan with deliverables
├── BUILD_ORDER.md                            Dependency-ordered file build queue
├── CONTRIBUTING.md                           How to add a service / adapter / fix
├── CODE_OF_CONDUCT.md                        Contributor Covenant 2.1
├── SECURITY.md                               Responsible disclosure policy
├── CHANGELOG.md                              Keep-a-Changelog format
├── CITATION.cff                              Paper citation (filled at submission)
├── AGENTS.md                                 Repo conventions for AI coding assistants
├── .python-version                           3.11
├── .pre-commit-config.yaml                   ruff, isort, mypy, conventional-commits
├── .gitignore                                Python + voice-agent ignores
├── .gitattributes                            LFS + line endings
├── pyproject.toml                            Package metadata + extras + tool config
│
├── .github/
│   ├── CODEOWNERS                            Required reviewers per path
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── dependabot.yml
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml
│   │   ├── feature_request.yml
│   │   └── adapter_request.yml
│   └── workflows/
│       ├── ci.yml                            pytest + ruff + mypy on PR
│       ├── codeql.yml                        Security scanning
│       ├── docs.yml                          Build + deploy docs site
│       └── release.yml                       Tag → PyPI + GitHub release
│
├── specs/                                    Module specifications — Codex implements against these
│   ├── README.md                             How to use specs
│   ├── 00-architecture.md                    The architecture in depth
│   ├── 01-config.md                          Pydantic config schema
│   ├── 02-services-base.md                   STTService / LLMService / TTSService ABCs
│   ├── 03-services-asr.md                    Per-provider ASR specs (Nemotron, Qwen3, Whisper, Deepgram)
│   ├── 04-services-llm.md                    Per-provider LLM specs (vLLM, OpenAI-compat, Anthropic)
│   ├── 05-services-tts.md                    Per-provider TTS specs (Magpie, Maya1, Voxtral, Kokoro, ElevenLabs)
│   ├── 06-codecs.md                          μ-law/A-law/L16/Opus → PCM16/16k normalization
│   ├── 07-telephony-base.md                  TelephonyAdapter ABC
│   ├── 08-telephony-twilio.md                Twilio Media Streams adapter
│   ├── 09-telephony-freeswitch.md            FreeSWITCH mod_audio_fork adapter
│   ├── 10-telephony-asterisk.md              Asterisk AudioSocket adapter
│   ├── 11-orchestration.md                   Orchestrator + session state
│   ├── 12-orchestration-bargein.md           3-stage barge-in classifier
│   ├── 13-orchestration-fillers.md           Latency-aware filler scheduling
│   ├── 14-agents-executor.md                 Two-pass tool-call streaming executor
│   ├── 15-agents-tools.md                    Tool registry + tool base class
│   ├── 16-knowledge-rag.md                   Two-stage rerank RAG
│   ├── 17-observability.md                   OTEL spans + audit log
│   ├── 18-runtime.md                         Server bootstrap + lifecycle
│   ├── 19-transport.md                       FastAPI routes + WebSocket protocol
│   ├── 20-cli.md                             `polyvoice` CLI entry point
│   ├── 21-tests.md                           Test layout + mocks + markers
│   └── 22-telephonybench.md                  Benchmark task families + scoring
│
├── src/polyvoice/                            Code (Codex implements per specs)
│   ├── __init__.py                           Public API surface (re-exports)
│   ├── py.typed                              PEP 561 marker
│   ├── cli.py                                `polyvoice` CLI
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── processor.py                      Processor base class (async event)
│   │   ├── events.py                         VoiceEvent types (Pydantic)
│   │   ├── session.py                        VoiceSessionState
│   │   └── exceptions.py                     PolyVoiceError hierarchy
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── models.py                         Pydantic config models
│   │   ├── loader.py                         YAML/env loader with Pydantic
│   │   └── validation.py                     Cross-field validation
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── base.py                           STTService / LLMService / TTSService ABCs
│   │   ├── registry.py                       Plugin registry (entry points)
│   │   ├── asr/
│   │   │   ├── __init__.py
│   │   │   ├── nemotron.py
│   │   │   ├── qwen3_vllm.py
│   │   │   ├── whisper_local.py
│   │   │   ├── whisper_api.py
│   │   │   ├── deepgram.py
│   │   │   └── assemblyai.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── openai_compat.py              vLLM, Ollama, OpenAI, OpenRouter — all via this
│   │   │   ├── anthropic.py
│   │   │   ├── mistral.py
│   │   │   └── vllm_native.py                Direct vLLM AsyncLLMEngine
│   │   ├── tts/
│   │   │   ├── __init__.py
│   │   │   ├── magpie.py
│   │   │   ├── soprano.py
│   │   │   ├── kokoro.py
│   │   │   ├── chatterbox.py
│   │   │   ├── maya1_vllm.py
│   │   │   ├── voxtral_omni.py               2-stage via vllm-omni
│   │   │   ├── elevenlabs.py
│   │   │   ├── cartesia.py
│   │   │   └── piper.py
│   │   └── vad/
│   │       ├── __init__.py
│   │       ├── silero.py
│   │       └── smart_turn.py
│   │
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── codecs.py                         mu_law/a_law/l16/opus ↔ PCM16
│   │   ├── resample.py                       Sample-rate conversion
│   │   ├── frames.py                         AudioFrame, framing utilities
│   │   └── agc.py                            Automatic Gain Control (port existing)
│   │
│   ├── telephony/
│   │   ├── __init__.py
│   │   ├── base.py                           TelephonyAdapter ABC + CallSession
│   │   ├── twilio.py                         Twilio Media Streams (μ-law 8k JSON)
│   │   ├── freeswitch.py                     FreeSWITCH mod_audio_fork (L16 binary)
│   │   ├── asterisk.py                       Asterisk AudioSocket (TCP, slin16)
│   │   ├── vonage.py                         Vonage Voice WebSocket (L16 16k binary)
│   │   ├── telnyx.py                         Telnyx Media Streaming
│   │   ├── plivo.py                          Plivo Audio Streaming
│   │   └── sip.py                            Raw SIP via aiortc/pjsip bridge
│   │
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── orchestrator.py                   Top-level VoiceOrchestrator
│   │   ├── barge_in.py                       3-stage barge-in classifier
│   │   ├── tts_control.py                    TTS pause/resume/cancel
│   │   ├── stream_state.py                   Streaming state machine
│   │   ├── turn_coordinator.py               Turn-level coordination
│   │   └── interrupted_context.py            [interrupted] marker handling
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── executor.py                       Two-pass tool-call streaming executor
│   │   ├── state_tracker.py                  Agent state machine
│   │   ├── timing_oracle.py                  Per-tool p75 latency oracle
│   │   ├── filler_scheduler.py               Time-spaced filler scheduler
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── base.py                       Tool ABC + registry
│   │       └── builtin.py                    Built-in tools (escalate, etc.)
│   │
│   ├── knowledge/
│   │   ├── __init__.py
│   │   ├── rag.py                            Two-stage rerank RAG
│   │   ├── stores.py                         Qdrant + pgvector adapters
│   │   ├── chunking.py                       Parent/child chunk strategy
│   │   └── rerank.py                         Cross-encoder reranker
│   │
│   ├── observability/
│   │   ├── __init__.py
│   │   ├── otel.py                           OpenTelemetry tracer + metrics
│   │   ├── audit.py                          Per-call immutable JSONL audit log
│   │   ├── metrics.py                        MetricsCollector
│   │   └── logging.py                        loguru setup
│   │
│   ├── runtime/
│   │   ├── __init__.py
│   │   ├── bootstrap.py                      App startup wiring
│   │   ├── server.py                         FastAPI server
│   │   ├── lifecycle.py                      Startup/shutdown hooks
│   │   └── health.py                         Liveness + readiness endpoints
│   │
│   └── transport/
│       ├── __init__.py
│       ├── http_routes.py                    HTTP REST routes (/config/*)
│       ├── ws_voice.py                       /v1/ws/voice/{session_id}
│       └── auth.py                           JWT + API-key middleware
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                           Shared fixtures
│   ├── mocks/
│   │   ├── __init__.py
│   │   ├── stt.py                            MockSTTService
│   │   ├── llm.py                            MockLLMService
│   │   ├── tts.py                            MockTTSService
│   │   ├── telephony.py                      MockTelephonyAdapter
│   │   └── fixtures/
│   │       └── sample_calls/                 Pre-recorded WS frames per provider
│   ├── unit/
│   │   ├── audio/
│   │   ├── core/
│   │   ├── config/
│   │   ├── services/
│   │   ├── telephony/
│   │   ├── orchestration/
│   │   ├── agents/
│   │   ├── knowledge/
│   │   ├── observability/
│   │   ├── runtime/
│   │   └── transport/
│   ├── integration/
│   │   ├── test_pipeline_mocks.py            ASR→LLM→TTS with mocks end-to-end
│   │   ├── test_telephony_mocks.py           Adapter ↔ orchestrator wired up
│   │   └── test_otel_traces.py
│   └── e2e/
│       ├── test_twilio_smoke.py              @pytest.mark.telephony
│       ├── test_freeswitch_smoke.py          @pytest.mark.telephony
│       ├── test_asterisk_smoke.py            @pytest.mark.telephony
│       └── test_local_vllm_smoke.py          @pytest.mark.gpu
│
├── benchmarks/
│   ├── README.md                             How to run TelephonyBench
│   ├── BENCHMARK.md                          India-team handoff doc
│   ├── telephonybench/
│   │   ├── __init__.py
│   │   ├── tasks/
│   │   │   ├── inbound_cs.py                 Customer support inquiries
│   │   │   ├── outbound_notification.py      Appointment / payment reminders
│   │   │   └── ivr_replacement.py            Multi-step navigation
│   │   ├── personas.py                       5 caller personas (LLM-driven)
│   │   ├── runner.py                         Per-cell call runner
│   │   ├── metrics.py                        TTFB, WER, hallucination, etc.
│   │   ├── scoring.py                        Programmatic ground-truth checks
│   │   └── validate.py                       Result manifest validator
│   ├── configs/                              One YAML per cell (cell_01 .. cell_13)
│   │   ├── cell_01_cloud_baseline_a.yaml
│   │   ├── cell_02_cloud_baseline_b.yaml
│   │   ├── cell_03_local_premium.yaml
│   │   ├── cell_04_local_cheap.yaml
│   │   ├── cell_05_local_voxtral.yaml
│   │   ├── cell_06_hybrid_llm_cloud.yaml
│   │   ├── cell_07_hybrid_asr_cloud.yaml
│   │   ├── cell_08_hybrid_tts_cloud.yaml
│   │   ├── cell_09_livekit_reference.yaml
│   │   ├── cell_10_cpaas_freeswitch.yaml
│   │   ├── cell_11_cpaas_asterisk.yaml
│   │   ├── cell_12_cpaas_twilio.yaml
│   │   └── cell_13_cpaas_vonage.yaml
│   └── results/                              Output JSON manifests (gitignored except summary)
│       └── .gitkeep
│
├── examples/
│   ├── twilio-llama-vllm/                    Twilio inbound bot, fully local
│   │   ├── README.md
│   │   ├── docker-compose.yml
│   │   ├── config.yaml
│   │   └── agent.py
│   ├── freeswitch-onprem/                    FreeSWITCH self-hosted with audit logs
│   │   ├── README.md
│   │   ├── docker-compose.yml
│   │   └── agent.py
│   └── asterisk-rag-agent/                   Asterisk + RAG with red-flag escalation
│       ├── README.md
│       ├── docker-compose.yml
│       ├── docs/                             Sample knowledge-base documents
│       └── agent.py
│
├── docs/                                     MkDocs Material site source
│   ├── index.md
│   ├── getting-started.md
│   ├── architecture.md
│   ├── services/                             One page per service
│   │   ├── nemotron.md
│   │   ├── vllm.md
│   │   ├── magpie.md
│   │   └── ...
│   ├── telephony/                            One page per CPaaS adapter
│   │   ├── twilio.md
│   │   ├── freeswitch.md
│   │   └── ...
│   ├── orchestration/
│   │   ├── barge-in.md
│   │   ├── filler-scheduling.md
│   │   └── tool-calling.md
│   ├── observability/
│   │   ├── opentelemetry.md
│   │   └── audit-logs.md
│   ├── compliance/
│   │   ├── hipaa-mode.md
│   │   └── pci-mode.md
│   ├── deployment/
│   │   ├── docker-compose.md
│   │   ├── helm.md
│   │   └── on-prem.md
│   ├── plugin-authoring/
│   │   ├── adding-a-service.md
│   │   └── adding-an-adapter.md
│   ├── reference/                            Auto-generated via mkdocstrings
│   └── roadmap.md
│
├── deploy/
│   ├── docker-compose.yml                    Reference all-local deployment
│   ├── helm/
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   ├── systemd/
│   │   └── polyvoice.service
│   └── nginx/
│       └── polyvoice.conf
│
├── paper/
│   ├── README.md                             Paper-build instructions
│   ├── main.tex                              Or main.md if Markdown-first
│   ├── bibliography.bib
│   ├── figures/
│   ├── tables/
│   └── macros/
│       └── results.tex                       Auto-generated from benchmark JSON
│
└── scripts/
    ├── format.sh                             Run ruff format + isort
    ├── typecheck.sh                          Run mypy
    ├── test.sh                               Run pytest with coverage
    ├── docs-build.sh                         Build docs locally
    ├── benchmark-cell.sh                     Run one benchmark cell
    └── paper-build.sh                        Inject benchmark results, build paper
```

## File ownership / CODEOWNERS map

```
*                                  @netoai/engineering
src/polyvoice/observability/audit.py @netoai/engineering @netoai/security
src/polyvoice/telephony/           @netoai/engineering
src/polyvoice/services/llm/        @netoai/engineering @netoai/ml
src/polyvoice/services/asr/        @netoai/engineering @netoai/ml
src/polyvoice/services/tts/        @netoai/engineering @netoai/ml
docs/compliance/                   @netoai/engineering @netoai/compliance
benchmarks/                        @netoai/engineering @netoai/india-team
paper/                             @netoai/engineering @netoai/research
specs/                             @netoai/engineering
```

## Filename conventions

- Modules: `snake_case.py`
- Tests: `test_<module>.py`
- Per-provider: `<provider_lowercase>.py` (e.g. `twilio.py`, not `Twilio.py` or `twilio_adapter.py`)
- Spec files: `NN-area.md` where NN is the build-order number (zero-padded)
- One class per file in `services/`, `telephony/`, `agents/tools/` — keeps imports cheap

## Banned filenames

- `utils.py` — use a domain-specific name
- `helpers.py` — same
- `common.py` — same
- `misc.py` — never
- `tmp_*.py` / `_old.py` / `*_v2.py` — git is the version system, not the filesystem

## When to add a new top-level directory

Almost never. The current top-level set is intentional:
- `src/` `tests/` — code
- `specs/` — what code should do
- `benchmarks/` — eval suite
- `examples/` — runnable references
- `docs/` — public docs site
- `deploy/` — production deployment artifacts
- `paper/` — academic paper
- `scripts/` — repo-management scripts

If you think you need a new one, propose it in a PR that updates this file first.
