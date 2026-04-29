# PolyVoice — Sprint Plan

Six one-week sprints. Each ends with a release tag on `main`. Mock-driven development through Sprint 5 — no GPU required. Benchmark phase in Sprint 6 with the NetoAI India team. Paper submission gated on real benchmark numbers.

## Headline timeline

| Sprint | Dates | Goal | Tag |
|---|---|---|---|
| **0** | This week (Days 1–3) | Repo hygiene + specs + sprint plan | `v0.1.0-pre` |
| **1** | Week 1 | Core abstractions + Twilio adapter | `v0.1.1-alpha` |
| **2** | Week 2 | FreeSWITCH + Asterisk adapters | `v0.1.2-alpha` |
| **3** | Week 3 | Orchestration + agents layer | `v0.1.3-alpha` |
| **4** | Week 4 | Observability + production-readiness fixes | `v0.1.4-alpha` |
| **5** | Week 5 | Examples + docs site + benchmark harness | `v0.2.0-beta` |
| **6** | Week 6 | India-team benchmarks + paper finalization | `v0.2.1-beta` |

## Cross-cutting standards (apply every sprint)

- All work via PRs from feature branches; `main` always green
- CI must pass (pytest unit + ruff + mypy)
- 1 maintainer approval required per PR
- Conventional commits enforced via pre-commit
- Each sprint closes with a tag + GitHub Release notes auto-generated from commits
- `CHANGELOG.md` updated in every PR under `## Unreleased`

## Definition of Done — applies every sprint

Before tagging:
- [ ] All sprint deliverables checked in
- [ ] CI green on `main`
- [ ] Unit test coverage on touched modules ≥ 60%
- [ ] No new mypy errors
- [ ] No new ruff/black/isort violations
- [ ] All public APIs added in this sprint have docstrings
- [ ] Examples (when present) smoke-test passes against mocks
- [ ] CHANGELOG entry under the sprint's version
- [ ] Tag pushed, GitHub Release published

---

## Sprint 0 — Repo Hygiene (Days 1–3)

**Goal:** repo looks like a real OSS project before any feature code lands.

**Deliverables:**

Already shipped in this batch:
- [x] `README.md`
- [x] `LICENSE` (Apache 2.0)
- [x] `VISION.md`
- [x] `CONTRIBUTING.md`
- [x] `pyproject.toml` (with all extras)
- [x] `.gitignore`

Remaining:
- [ ] `STRUCTURE.md` ✓ this PR
- [ ] `CONTEXT.md` ✓ this PR
- [ ] `SPRINT_PLAN.md` ✓ this PR
- [ ] `BUILD_ORDER.md`
- [ ] `CODE_OF_CONDUCT.md`
- [ ] `SECURITY.md`
- [ ] `CHANGELOG.md`
- [ ] `CITATION.cff`
- [ ] `AGENTS.md` (cleaned)
- [ ] `.python-version`
- [ ] `.pre-commit-config.yaml`
- [ ] `.gitattributes`
- [ ] `.github/CODEOWNERS`
- [ ] `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] `.github/dependabot.yml`
- [ ] `.github/ISSUE_TEMPLATE/{bug_report,feature_request,adapter_request}.yml`
- [ ] `.github/workflows/ci.yml`
- [ ] `.github/workflows/codeql.yml`
- [ ] `specs/README.md` and the numbered spec files (00–22)
- [ ] Empty `src/polyvoice/__init__.py` + `py.typed` so `pip install -e .` works
- [ ] Empty `tests/__init__.py` + a single `tests/unit/test_smoke.py` that imports the package

**Definition of Done:**
- `pip install -e ".[dev]"` works from a clean venv
- `pytest tests/unit` passes (smoke test only)
- `pre-commit run --all-files` passes
- CI green on a no-op PR
- Branch protection on `main`: require PR + CI + 1 approval
- `v0.1.0-pre` tag pushed
- Repo is public on `github.com/adx-coder/PolyVoice`

---

## Sprint 1 — Core Abstractions + Twilio (Week 1)

**Goal:** ship a working Twilio Media Streams call end-to-end against mock services. Lock the public service interfaces.

**Deliverables — code:**
- `src/polyvoice/core/processor.py` — `Processor` base (async `process(event)`)
- `src/polyvoice/core/events.py` — `VoiceEvent` types (Pydantic)
- `src/polyvoice/core/session.py` — `VoiceSessionState`
- `src/polyvoice/core/exceptions.py` — `PolyVoiceError` hierarchy
- `src/polyvoice/config/models.py` — Pydantic config models (root + per-section)
- `src/polyvoice/config/loader.py` — YAML/env loader
- `src/polyvoice/services/base.py` — `STTService` / `LLMService` / `TTSService` ABCs (per spec 02)
- `src/polyvoice/services/registry.py` — plugin registry
- `src/polyvoice/audio/codecs.py` — μ-law/A-law/L16/PCM16 conversion
- `src/polyvoice/audio/resample.py` — sample-rate conversion
- `src/polyvoice/audio/frames.py` — `AudioFrame` dataclass + framing utilities
- `src/polyvoice/telephony/base.py` — `TelephonyAdapter` ABC + `CallSession` (per spec 07)
- `src/polyvoice/telephony/twilio.py` — full Twilio adapter (per spec 08)
- `src/polyvoice/observability/logging.py` — loguru setup

**Deliverables — tests:**
- `tests/mocks/stt.py`, `tests/mocks/llm.py`, `tests/mocks/tts.py`, `tests/mocks/telephony.py`
- `tests/unit/audio/test_codecs.py` (golden-file tests for each conversion)
- `tests/unit/audio/test_resample.py`
- `tests/unit/audio/test_frames.py`
- `tests/unit/core/test_processor.py`
- `tests/unit/core/test_events.py`
- `tests/unit/services/test_base.py`
- `tests/unit/telephony/test_base.py`
- `tests/unit/telephony/test_twilio.py` (using `aioresponses` + recorded WS frame fixtures)
- `tests/integration/test_pipeline_mocks.py` — Twilio adapter ↔ orchestrator skeleton ↔ mock services, end-to-end against a fake Twilio WS server

**Tag:** `v0.1.1-alpha`

**Out of scope this sprint:**
- Real ASR/LLM/TTS implementations (mocks only)
- Real orchestration (just enough to wire the pipeline)
- FreeSWITCH/Asterisk (Sprint 2)

---

## Sprint 2 — FreeSWITCH + Asterisk (Week 2)

**Goal:** ship the two telephony adapters Pipecat doesn't have natively. Lock codec normalization layer.

**Deliverables — code:**
- `src/polyvoice/telephony/freeswitch.py` — full adapter (mod_audio_fork, L16 binary, ESL call control) per spec 09
- `src/polyvoice/telephony/asterisk.py` — full adapter (AudioSocket TCP, slin16, ARI call control) per spec 10
- `src/polyvoice/audio/agc.py` — port from existing `asr/processing/agc.py`
- Helper modules:
  - `src/polyvoice/telephony/_esl.py` — minimal ESL client (FreeSWITCH)
  - `src/polyvoice/telephony/_audiosocket.py` — TCP framing parser
- Codec auto-negotiation in `polyvoice/telephony/base.py` — adapter declares supported codecs, runtime picks

**Deliverables — tests:**
- `tests/unit/telephony/test_freeswitch.py` — mock ESL server + WS frame replay
- `tests/unit/telephony/test_asterisk.py` — mock AudioSocket TCP server
- `tests/integration/test_telephony_mocks.py` — three adapters interchangeable via config
- `tests/unit/audio/test_agc.py`

**Definition of Done addition:** the same agent code runs unchanged across Twilio + FreeSWITCH + Asterisk via config.

**Tag:** `v0.1.2-alpha`

---

## Sprint 3 — Orchestration + Agents Layer (Week 3)

**Goal:** port the orchestration techniques (barge-in, fillers, two-pass tool calling) into clean modular form.

**Deliverables — code:**
- `src/polyvoice/orchestration/orchestrator.py` — top-level `VoiceOrchestrator` (port + clean `voice_orchestrator.py`)
- `src/polyvoice/orchestration/barge_in.py` — 3-stage barge-in classifier (port `app/orchestration/barge_in.py` + `asr/processing/barge_in_classifier.py`) per spec 12
- `src/polyvoice/orchestration/tts_control.py` — port from existing
- `src/polyvoice/orchestration/stream_state.py` — port from existing
- `src/polyvoice/orchestration/turn_coordinator.py` — extract from `voice_orchestrator.py`
- `src/polyvoice/orchestration/interrupted_context.py` — `[interrupted]` marker handling
- `src/polyvoice/agents/executor.py` — two-pass tool-call executor (port `agents_sdk/core/agent_executor.py`) per spec 14
- `src/polyvoice/agents/state_tracker.py` — port
- `src/polyvoice/agents/timing_oracle.py` — per-tool p75 oracle (port `agents_sdk/core/tool_timing_oracle.py`)
- `src/polyvoice/agents/filler_scheduler.py` — time-spaced filler scheduler per spec 13
- `src/polyvoice/agents/tools/base.py` — `Tool` ABC + registry
- `src/polyvoice/agents/tools/builtin.py` — built-in `escalate` and `transfer`

**Deliverables — tests:**
- Full coverage on each orchestration module
- `tests/integration/test_bargein_full.py` — 3-stage flow via mocks: backchannel resume + true interrupt cancel
- `tests/integration/test_filler_scheduling.py` — fillers fire at correct offsets given mock tool timings
- `tests/integration/test_two_pass_tools.py` — text-only path + tool-call path both flow correctly

**Tag:** `v0.1.3-alpha`

---

## Sprint 4 — Observability + Production-Readiness (Week 4)

**Goal:** wire up OpenTelemetry, ship audit logging, fix the AGENTS.md production bugs.

**Deliverables — code:**
- `src/polyvoice/observability/otel.py` — tracer + metrics (deps already in `pyproject.toml`)
- `src/polyvoice/observability/audit.py` — JSONL audit log writer, immutable, signable
- `src/polyvoice/observability/metrics.py` — `MetricsCollector` (port + clean)
- `src/polyvoice/runtime/health.py` — liveness + readiness endpoints
- `src/polyvoice/runtime/lifecycle.py` — startup/shutdown hooks
- `src/polyvoice/runtime/server.py` — port `unified_server.py` with lifecycle wiring
- `src/polyvoice/runtime/bootstrap.py` — wires config → services → orchestrator → telephony → server
- `src/polyvoice/transport/http_routes.py` — `/config/{asr,llm,tts,telephony}` hot-swap routes
- `src/polyvoice/transport/ws_voice.py` — WebSocket voice endpoint
- `src/polyvoice/transport/auth.py` — JWT + API-key middleware
- `src/polyvoice/cli.py` — `polyvoice` command

**Production-readiness fixes (from AGENTS.md):**
- CORS lockdown — no `allow_origins=["*"]`
- Hot-swap coordination via single mutex on the model registry
- Backpressure path — pick one and stick with it; remove the half-implemented queue
- Typed config across ASR/VAD wrappers
- Graceful shutdown hooks

**Deliverables — tests:**
- `tests/integration/test_otel_traces.py` — verify spans emitted at expected boundaries
- `tests/integration/test_audit_log.py` — immutability, completeness, schema
- `tests/integration/test_hot_swap.py` — model swap during a live mock call doesn't drop audio
- `tests/integration/test_health_endpoints.py`

**Tag:** `v0.1.4-alpha`

---

## Sprint 5 — Examples + Docs Site + Benchmark Harness (Week 5)

**Goal:** make external developers want to adopt this. Make the India team able to benchmark without back-and-forth.

**Deliverables — code:**
- `src/polyvoice/services/asr/{nemotron,qwen3_vllm,whisper_local,deepgram}.py` — real implementations (the four reference ASRs)
- `src/polyvoice/services/llm/{openai_compat,anthropic,vllm_native}.py` — real implementations
- `src/polyvoice/services/tts/{magpie,maya1_vllm,kokoro,elevenlabs}.py` — real implementations
- `src/polyvoice/knowledge/rag.py` — port from existing
- `src/polyvoice/knowledge/stores.py` — Qdrant + pgvector adapters
- `src/polyvoice/knowledge/rerank.py` — cross-encoder reranker (MiniLM)

**Deliverables — examples:**
- `examples/twilio-llama-vllm/` — Twilio inbound bot, fully local Llama-vLLM + Magpie + Nemotron, 1-command launch
- `examples/freeswitch-onprem/` — FreeSWITCH self-hosted with audit logs on
- `examples/asterisk-rag-agent/` — Asterisk + RAG with red-flag escalation

**Deliverables — docs:**
- MkDocs Material site
- Per-service docs page (one per provider)
- Per-CPaaS docs page with on-the-wire details
- Architecture explainer
- Compliance guide stubs (HIPAA-mode, PCI-mode)
- Plugin authoring guides
- Reference docs auto-generated via mkdocstrings
- Site published to GitHub Pages or `polyvoice.dev`

**Deliverables — benchmarks:**
- `benchmarks/telephonybench/` — full TelephonyBench v0 implementation
- `benchmarks/configs/cell_01.yaml` … `cell_13.yaml` — all 13 cells
- `benchmarks/BENCHMARK.md` — India team handoff doc with run commands, expected runtime per cell, output schema, hardware spec
- `scripts/benchmark-cell.sh` — single-cell runner
- A 30-minute Loom recorded showing one full benchmark run on a small dummy config

**Tag:** `v0.2.0-beta`

---

## Sprint 6 — India Benchmarks + Paper (Week 6)

**Goal:** real numbers in, paper submitted.

**Phase 6a — India team (Days 36–40):**
- India team smoke-tests each cell: `python scripts/benchmark-cell.sh --cell cell_01 --smoke` confirms basic plumbing
- Any integration bugs found in smoke test → fix in `main` within 24h, India re-pulls
- Full benchmark runs across all 13 cells (1500–2000 calls total)
- Results pushed as a PR: `benchmarks/results/v1.0/cell_*.json` + `summary.md`

**Phase 6b — Paper finalization (Days 40–43):**
- `scripts/paper-build.sh` injects benchmark numbers into LaTeX/Markdown via `paper/macros/results.tex`
- Plots generated: cost/quality Pareto, latency CDF, failure-mode breakdown
- Final read-through, internal review
- `CITATION.cff` updated with paper bibtex

**Phase 6c — Submission (Days 43–45):**
- Submit to **EMNLP 2026 Industry Track** (or NeurIPS Datasets & Benchmarks if the May 16 window is hit)
- arXiv preprint with the same content
- Tag `v0.2.1-beta` on `main`
- HackerNews / Twitter / LinkedIn announcement coordinated

**Tag:** `v0.2.1-beta`

**Definition of Done — Sprint 6:**
- All 13 cells benchmarked with real numbers; results JSON + manifests in repo
- Paper compiles with no `\benchresult{...}` red flags remaining
- Paper submitted; arXiv ID assigned
- Press kit (announcement post + technical blog draft) ready

---

## What can slip and what can't

**Can slip (recovery plan available):**
- Real service implementations of long-tail providers (Deepgram, AssemblyAI, Anthropic, ElevenLabs) — push to v0.3 if Sprint 5 runs hot
- Vonage / Telnyx / Plivo adapters — these are in scope but not on the critical path; Sprint 5 budget if remaining time
- Helm chart and systemd unit — push to v0.3 if Sprint 5 runs hot
- Multi-tenant routing — never on critical path; Tier 2

**Cannot slip (paper-blocking):**
- Twilio + FreeSWITCH + Asterisk adapters (Sprint 1–2)
- Orchestration techniques (Sprint 3)
- OTEL + audit (Sprint 4)
- 4 reference ASRs + 3 reference LLMs + 3 reference TTSes (Sprint 5)
- Benchmark harness + India handoff doc (Sprint 5)
- Real benchmark numbers (Sprint 6)
- Paper submission (Sprint 6)

If a Sprint 1–4 deliverable is at risk by Wednesday of its sprint, raise it in standup; do not push silently.

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Asterisk AudioSocket integration harder than estimated | Medium | Sprint 2 slips | Have Twilio + FreeSWITCH ready by EOW1; Asterisk by EOW2 even if it's Day 14 |
| Real ASR/LLM/TTS integrations break in Sprint 5 | High | Examples don't run | Pre-allocate $50–100 of cloud-GPU time for one fully-local cell smoke test in W3 |
| Pipecat ships native FreeSWITCH or AudioSocket before us | Low | Loses one differentiator | Lean on Asterisk + multi-CPaaS routing as remaining differentiators |
| Benchmark results show fully-local cells lose badly to cloud | Medium | Weakens paper | Frame paper around Pareto frontier + compliance/cost dimensions, not just quality |
| EMNLP Industry deadline misses | Medium | Push to next venue | NeurIPS D&B (May 16) backup; ASRU 2026 (Aug); ICASSP 2027 (Sept) |
| Production-readiness bugs (CORS, backpressure) take longer | Medium | Sprint 4 overruns | Budget 1.5 days each, not 0.5 |
| India team can't commit to a 5–7 day window | High if not locked early | Paper slips a sprint | Lock the dates with India lead during Sprint 0 |

## Communication cadence

- Daily async standup in `#polyvoice-eng` (or equivalent): yesterday / today / blockers
- Friday: sprint close demo + tag + retro
- Monday: sprint open + capacity check
- Blocking issues: tag `@netoai/engineering` in the issue, post in `#polyvoice-eng`

## Resource plan

| Role | FTE | Sprints |
|---|---|---|
| Lead engineer (orchestration + adapters) | 1.0 | All |
| ASR/LLM/TTS engineer (services + tests) | 0.5 | 1, 2, 4, 5 |
| DevOps / observability engineer | 0.3 | 0, 4, 5 |
| Tech writer (docs site) | 0.3 | 5 |
| India team (benchmarks) | 1.5 (compressed into W6) | 6 |
| CTO (review, paper, decisions) | 0.5 | All |

If actual staffing is less, drop Sprint 5 docs site to v0 (just an index page + per-service stubs) and push the docs site polish to v0.3.
