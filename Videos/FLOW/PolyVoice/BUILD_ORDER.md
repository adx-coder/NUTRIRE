# PolyVoice — Build Order

A dependency-ordered queue of files to implement. Build top to bottom. Earlier files have no dependencies on later files.

This is the file a coding agent (Codex / Claude Code / Cursor) consumes when asked "what do I work on next?"

Each entry: `# <build-step>. <path> — <one-line purpose> [spec: <spec-file>] [sprint: <N>]`

---

## Phase 0 — Repo bootstrap (Sprint 0)

Already done in this PR:
- `README.md`, `LICENSE`, `VISION.md`, `CONTEXT.md`, `STRUCTURE.md`, `SPRINT_PLAN.md`, `BUILD_ORDER.md`
- `pyproject.toml`, `.gitignore`, `.gitattributes`, `.python-version`, `.pre-commit-config.yaml`
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`, `CITATION.cff`, `AGENTS.md`
- `.github/CODEOWNERS`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/dependabot.yml`
- `.github/ISSUE_TEMPLATE/{bug_report,feature_request,adapter_request}.yml`
- `.github/workflows/{ci,codeql}.yml`
- `specs/README.md`, `specs/00..22-*.md`
- `src/polyvoice/__init__.py`, `src/polyvoice/py.typed`
- `tests/__init__.py`, `tests/unit/test_smoke.py`

---

## Phase 1 — Core foundations (Sprint 1, Days 4–6)

Build leaf-first. Nothing in this phase has runtime dependencies on later phases.

```
1.  src/polyvoice/core/exceptions.py            PolyVoiceError hierarchy                       [spec: 00] [sprint: 1]
2.  src/polyvoice/core/events.py                VoiceEvent Pydantic types                      [spec: 11, 19] [sprint: 1]
3.  src/polyvoice/core/processor.py             Processor base class                           [spec: 00] [sprint: 1]
4.  src/polyvoice/core/session.py               VoiceSessionState dataclass                    [spec: 11] [sprint: 1]
5.  src/polyvoice/config/models.py              Root + per-section Pydantic config             [spec: 01] [sprint: 1]
6.  src/polyvoice/config/loader.py              YAML + env loader                              [spec: 01] [sprint: 1]
7.  src/polyvoice/config/validation.py          Cross-field validation                         [spec: 01] [sprint: 1]
8.  src/polyvoice/observability/logging.py      loguru setup                                   [spec: 17] [sprint: 1]
```

After this group: `pip install -e ".[dev]"` works, smoke tests pass, you can import `polyvoice`.

---

## Phase 2 — Audio primitives (Sprint 1, Days 5–7)

Pure DSP. No external deps beyond numpy/scipy. CPU-only. Golden-file testable.

```
9.  src/polyvoice/audio/frames.py               AudioFrame dataclass + framing utilities       [spec: 06] [sprint: 1]
10. src/polyvoice/audio/codecs.py               μ-law / A-law / L16 / PCM16 conversion         [spec: 06] [sprint: 1]
11. src/polyvoice/audio/resample.py             Sample-rate conversion                         [spec: 06] [sprint: 1]
12. src/polyvoice/audio/agc.py                  Automatic Gain Control (port existing)         [spec: 06] [sprint: 2]
```

Tests for each must be written in the same PR.

---

## Phase 3 — Service ABCs + registry (Sprint 1, Days 6–8)

The contract every plugin must satisfy. Keep these stable — anything we change later is a breaking change.

```
13. src/polyvoice/services/base.py              STTService / LLMService / TTSService ABCs      [spec: 02] [sprint: 1]
14. src/polyvoice/services/registry.py          Plugin registry (entry points)                 [spec: 02] [sprint: 1]
15. src/polyvoice/services/vad/silero.py        Silero VAD (port existing)                     [spec: 02] [sprint: 1]
```

---

## Phase 4 — Mocks (Sprint 1, Days 7–8)

Without these, mock-driven dev doesn't work. Ship them with the ABCs.

```
16. tests/mocks/stt.py                          MockSTTService                                 [spec: 21] [sprint: 1]
17. tests/mocks/llm.py                          MockLLMService                                 [spec: 21] [sprint: 1]
18. tests/mocks/tts.py                          MockTTSService                                 [spec: 21] [sprint: 1]
19. tests/mocks/telephony.py                    MockTelephonyAdapter                           [spec: 21] [sprint: 1]
20. tests/mocks/fixtures/sample_calls/twilio.json    Recorded Twilio WS frames                 [spec: 21] [sprint: 1]
```

---

## Phase 5 — Telephony foundation (Sprint 1, Days 8–10)

The base contract for adapters, then the most common provider.

```
21. src/polyvoice/telephony/base.py             TelephonyAdapter ABC + CallSession             [spec: 07] [sprint: 1]
22. src/polyvoice/telephony/twilio.py           Twilio Media Streams adapter                   [spec: 08] [sprint: 1]
```

After this: a smoke test where MockSTT + MockLLM + MockTTS run an end-to-end "call" against a fake Twilio WebSocket server.

---

## Phase 6 — On-prem telephony (Sprint 2, Week 2)

The two adapters Pipecat doesn't have natively.

```
23. src/polyvoice/telephony/_esl.py             Minimal FreeSWITCH ESL client                  [spec: 09] [sprint: 2]
24. src/polyvoice/telephony/freeswitch.py       FreeSWITCH mod_audio_fork adapter              [spec: 09] [sprint: 2]
25. src/polyvoice/telephony/_audiosocket.py     Asterisk AudioSocket TCP framing               [spec: 10] [sprint: 2]
26. src/polyvoice/telephony/asterisk.py         Asterisk AudioSocket adapter                   [spec: 10] [sprint: 2]
```

After this: same agent code runs unchanged across Twilio + FreeSWITCH + Asterisk via config.

---

## Phase 7 — Orchestration (Sprint 3, Week 3)

Port from the existing NetoAI codebase. Heavy refactor; same behavior.

```
27. src/polyvoice/orchestration/stream_state.py        Streaming state machine                 [spec: 11] [sprint: 3]
28. src/polyvoice/orchestration/tts_control.py         TTS pause/resume/cancel                 [spec: 11] [sprint: 3]
29. src/polyvoice/orchestration/barge_in.py            3-stage barge-in classifier             [spec: 12] [sprint: 3]
30. src/polyvoice/orchestration/turn_coordinator.py    Turn-level coordination                 [spec: 11] [sprint: 3]
31. src/polyvoice/orchestration/interrupted_context.py [interrupted] marker                    [spec: 11] [sprint: 3]
32. src/polyvoice/orchestration/orchestrator.py        Top-level VoiceOrchestrator             [spec: 11] [sprint: 3]
```

---

## Phase 8 — Agents layer (Sprint 3, Week 3)

Two-pass tool-call streaming and latency-aware filler scheduling.

```
33. src/polyvoice/agents/state_tracker.py        Agent state machine                            [spec: 14] [sprint: 3]
34. src/polyvoice/agents/timing_oracle.py        Per-tool p75 latency oracle                   [spec: 14] [sprint: 3]
35. src/polyvoice/agents/filler_scheduler.py     Time-spaced filler scheduler                  [spec: 13] [sprint: 3]
36. src/polyvoice/agents/tools/base.py           Tool ABC + registry                           [spec: 15] [sprint: 3]
37. src/polyvoice/agents/tools/builtin.py        Built-in escalate / transfer                  [spec: 15] [sprint: 3]
38. src/polyvoice/agents/executor.py             Two-pass tool-call streaming executor         [spec: 14] [sprint: 3]
```

---

## Phase 9 — Observability + runtime (Sprint 4, Week 4)

```
39. src/polyvoice/observability/metrics.py       MetricsCollector                              [spec: 17] [sprint: 4]
40. src/polyvoice/observability/otel.py          OpenTelemetry tracer + metrics                [spec: 17] [sprint: 4]
41. src/polyvoice/observability/audit.py         Immutable JSONL audit log                     [spec: 17] [sprint: 4]
42. src/polyvoice/runtime/health.py              Liveness + readiness endpoints                [spec: 18] [sprint: 4]
43. src/polyvoice/runtime/lifecycle.py           Startup / shutdown hooks                      [spec: 18] [sprint: 4]
44. src/polyvoice/transport/auth.py              JWT + API-key middleware                      [spec: 19] [sprint: 4]
45. src/polyvoice/transport/http_routes.py       /config/* hot-swap routes                     [spec: 19] [sprint: 4]
46. src/polyvoice/transport/ws_voice.py          /v1/ws/voice/{session_id}                     [spec: 19] [sprint: 4]
47. src/polyvoice/runtime/server.py              FastAPI server                                [spec: 18] [sprint: 4]
48. src/polyvoice/runtime/bootstrap.py           App startup wiring                            [spec: 18] [sprint: 4]
49. src/polyvoice/cli.py                         polyvoice CLI                                 [spec: 20] [sprint: 4]
```

---

## Phase 10 — Real services (Sprint 5, Week 5)

These are the providers we evaluate in TelephonyBench. Build the four reference ASRs first, then the LLMs, then the TTSes.

```
50. src/polyvoice/services/asr/nemotron.py           NVIDIA Nemotron Streaming                 [spec: 03] [sprint: 5]
51. src/polyvoice/services/asr/qwen3_vllm.py         Qwen3-ASR via vLLM                        [spec: 03] [sprint: 5]
52. src/polyvoice/services/asr/whisper_local.py      faster-whisper                            [spec: 03] [sprint: 5]
53. src/polyvoice/services/asr/whisper_api.py        OpenAI Whisper API                        [spec: 03] [sprint: 5]
54. src/polyvoice/services/asr/deepgram.py           Deepgram                                  [spec: 03] [sprint: 5]

55. src/polyvoice/services/llm/openai_compat.py      OpenAI-compat (vLLM/Ollama/OpenAI/etc.)   [spec: 04] [sprint: 5]
56. src/polyvoice/services/llm/anthropic.py          Anthropic native                          [spec: 04] [sprint: 5]
57. src/polyvoice/services/llm/vllm_native.py        Direct vLLM AsyncLLMEngine                [spec: 04] [sprint: 5]

58. src/polyvoice/services/tts/magpie.py             Magpie                                    [spec: 05] [sprint: 5]
59. src/polyvoice/services/tts/maya1_vllm.py         Maya1 via vLLM                            [spec: 05] [sprint: 5]
60. src/polyvoice/services/tts/voxtral_omni.py       Voxtral via vllm-omni (2-stage)           [spec: 05] [sprint: 5]
61. src/polyvoice/services/tts/kokoro.py             Kokoro                                    [spec: 05] [sprint: 5]
62. src/polyvoice/services/tts/elevenlabs.py         ElevenLabs                                [spec: 05] [sprint: 5]
```

---

## Phase 11 — Knowledge / RAG (Sprint 5, Week 5)

```
63. src/polyvoice/knowledge/chunking.py          Parent/child chunk strategy                   [spec: 16] [sprint: 5]
64. src/polyvoice/knowledge/stores.py            Qdrant + pgvector adapters                    [spec: 16] [sprint: 5]
65. src/polyvoice/knowledge/rerank.py            Cross-encoder reranker (MiniLM)               [spec: 16] [sprint: 5]
66. src/polyvoice/knowledge/rag.py               Two-stage rerank RAG                          [spec: 16] [sprint: 5]
```

---

## Phase 12 — Examples (Sprint 5, Week 5)

```
67. examples/twilio-llama-vllm/agent.py + docker-compose.yml + README.md
68. examples/freeswitch-onprem/agent.py + docker-compose.yml + README.md
69. examples/asterisk-rag-agent/agent.py + docker-compose.yml + README.md
```

---

## Phase 13 — Benchmark harness (Sprint 5, Week 5)

```
70. benchmarks/telephonybench/personas.py            5 caller personas                         [spec: 22] [sprint: 5]
71. benchmarks/telephonybench/tasks/inbound_cs.py    Inbound CS task family                    [spec: 22] [sprint: 5]
72. benchmarks/telephonybench/tasks/outbound_notification.py  Notification task family         [spec: 22] [sprint: 5]
73. benchmarks/telephonybench/tasks/ivr_replacement.py        IVR replacement task family      [spec: 22] [sprint: 5]
74. benchmarks/telephonybench/metrics.py             TTFB, WER, hallucination, etc.           [spec: 22] [sprint: 5]
75. benchmarks/telephonybench/scoring.py             Programmatic ground-truth checks          [spec: 22] [sprint: 5]
76. benchmarks/telephonybench/runner.py              Per-cell call runner                      [spec: 22] [sprint: 5]
77. benchmarks/telephonybench/validate.py            Result manifest validator                 [spec: 22] [sprint: 5]
78. benchmarks/configs/cell_01.yaml ... cell_13.yaml All 13 cell configs                       [spec: 22] [sprint: 5]
79. benchmarks/BENCHMARK.md                          India team handoff doc                    [spec: 22] [sprint: 5]
80. scripts/benchmark-cell.sh                        Single-cell runner script                                [sprint: 5]
```

---

## Phase 14 — Docs site (Sprint 5, Week 5, parallel)

```
81. docs/index.md
82. docs/getting-started.md
83. docs/architecture.md
84. docs/services/{nemotron,vllm,magpie,maya1,voxtral,...}.md
85. docs/telephony/{twilio,freeswitch,asterisk,vonage,...}.md
86. docs/orchestration/{barge-in,filler-scheduling,tool-calling}.md
87. docs/observability/{opentelemetry,audit-logs}.md
88. docs/compliance/{hipaa-mode,pci-mode}.md
89. docs/deployment/{docker-compose,helm,on-prem}.md
90. docs/plugin-authoring/{adding-a-service,adding-an-adapter}.md
91. mkdocs.yml at repo root
```

---

## Phase 15 — Deployment artifacts (Sprint 5)

```
92. deploy/docker-compose.yml                    Reference all-local deployment
93. deploy/helm/Chart.yaml + values.yaml + templates/
94. deploy/systemd/polyvoice.service
95. deploy/nginx/polyvoice.conf
```

---

## Phase 16 — Paper machinery (Sprint 4–5, parallel with code)

```
96. paper/main.tex                               Paper draft (Sections 1–7 — see SPRINT_PLAN)
97. paper/bibliography.bib
98. paper/macros/results.tex                     Auto-generated (empty for now; Sprint 6 fills)
99. scripts/paper-build.sh                       Inject benchmark JSON into LaTeX
```

---

## Phase 17 — Benchmark execution (Sprint 6)

Owned by NetoAI India team.

```
100. benchmarks/results/v1.0/cell_01.json ... cell_13.json    Real benchmark numbers           [sprint: 6]
101. benchmarks/results/v1.0/summary.md                       Cross-cell rollup                [sprint: 6]
102. paper/figures/pareto.{pdf,png}                           Cost/quality Pareto              [sprint: 6]
103. paper/figures/latency_cdf.{pdf,png}                      Latency CDF                       [sprint: 6]
104. paper/tables/results_main.tex                            Main 9-cell results table        [sprint: 6]
105. paper/tables/results_cpaas.tex                           4-cell CPaaS portability table   [sprint: 6]
```

---

## How to use this list

**For human contributors:**
> "I want to work on PolyVoice." → Look at the lowest unchecked build step that's not blocked by an unfinished prereq. Read the spec for that step. Open a PR.

**For coding agents:**
> "Implement the next file." → Read this list top-to-bottom; find the first unfinished file; read its spec; implement; open PR.

**For sprint planning:**
> "What's left in Sprint N?" → Filter by `[sprint: N]`.

## Gating rules

- A file is "done" when: implemented, unit-tested, mypy-clean, ruff-clean, docstrings on public APIs, CHANGELOG entry under the right version.
- A phase is "done" when all its files are done AND the integration tests for that phase pass.
- A sprint is "done" when all its phases are done AND the sprint's tag is pushed.

Don't move on if a prereq isn't done.
