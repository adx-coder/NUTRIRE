# AGENTS.md - Guidance For AI Coding Assistants

This file is read by AI coding assistants when they work on this repository. Humans should read [`CONTRIBUTING.md`](./CONTRIBUTING.md) and [`CONTEXT.md`](./CONTEXT.md) too.

## Project Context

PolyVoice is a model-agnostic, platform-agnostic open framework for building local-first voice agents. The project is in pre-alpha recovery: the SDK-first ASR/LLM/TTS/runtime baseline exists, while telephony, production orchestration, agents, RAG, observability, and compliance profiles are still being rebuilt.

Read these before changing architecture:

- [`VISION.md`](./VISION.md) for scope and product thesis.
- [`CONTEXT.md`](./CONTEXT.md) for current state.
- [`SPRINT_PLAN.md`](./SPRINT_PLAN.md) for sprint priorities.
- [`RECOVERY_PLAN.md`](./RECOVERY_PLAN.md) for parity gaps.
- [`BUILD_ORDER.md`](./BUILD_ORDER.md) for the ordered work queue.

## How To Find Work

1. Open `SPRINT_PLAN.md` and identify the current high-value target.
2. Open `BUILD_ORDER.md` and find the next unfinished item in that target.
3. Read `CONTEXT.md` for the legacy FLOW porting map.
4. If touching model support, use the SDK extension path: add one loader/client/provider, register it, add a recipe or example, add tests, and add a smoke script when dependency weight requires it.
5. Implement with the smallest runtime surface change possible.

Formal specs may be missing or stale during recovery. If a spec exists, follow it. If it does not, update the relevant plan/doc in the same change instead of silently inventing a new architecture.

## Hard Rules

- **Do not break the SDK-first extension contract.** New ASR/LLM/TTS support should not require runtime rewrites.
- **Do not expand beyond `VISION.md`.** WebRTC SFU, avatar/vision, cloud realtime API, mobile SDK, and IDE plugin work are out of scope.
- **Do not pretend planned areas are implemented.** Docs must clearly separate recovered, partial, and planned work.
- **Do not add generic dumping-ground modules.** Avoid `utils.py`, `helpers.py`, `common.py`, `misc.py`, `*_v2.py`, and `*_old.py`.
- **Do not commit secrets, API keys, model weights, generated audio files, or DB files.**
- **Do not run benchmarks in CI.** GPU and provider-live checks must stay explicit.

## Style Requirements

- Python 3.11+, full type hints, `X | None` over `Optional[X]`.
- Pydantic 2 for structured config.
- Async by default in I/O paths; sync helpers only for pure compute.
- Docstrings on public classes and methods.
- Domain-specific filenames and one clear responsibility per module.
- Library code should use the project logging/error style instead of bare `print()` or bare `Exception`.

## Test Requirements

Every implementation change adds or updates tests. Conventions:

- Unit tests under `tests/unit/<area>/test_<module>.py`.
- Integration tests under `tests/integration/test_<scenario>.py`.
- E2E tests under `tests/e2e/test_<scenario>.py`.
- Mock services live in `src/polyvoice/services/mocks.py` today.
- GPU-required tests must be marked `@pytest.mark.gpu`.
- Telephony tests against real providers must be marked `@pytest.mark.telephony`.
- Slow tests should be marked `@pytest.mark.slow`.

Useful CPU-safe verification:

```bash
python -m pytest tests/unit tests/integration/test_pipeline_mocks.py tests/integration/test_pipeline_sdks.py
python scripts/qwen3_asr_smoke.py --fake-qwen-asr --language en --device cpu
```

## Commit / PR Style

Use conventional commits:

```text
<type>(<scope>): <subject>

<optional body>

<optional footer>
```

Types: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `chore`, `ci`, `build`, `style`.

Every PR should update `CHANGELOG.md` under `## [Unreleased]` when behavior, public docs, examples, or tests change materially.

## Things That Look Like Good Ideas But Are Not

- "Unify ASR/LLM/TTS into one service base." No. Their contracts differ.
- "Add a frame-based pipeline clone." No. Keep the event-oriented design.
- "Add OpenAI Realtime support because it is popular." No. Cloud realtime APIs are out of scope.
- "Collapse TTS provider, loader, and codec into one class." No. Keep the layers separate.
- "Patch runtime bootstrap for each new model." No. Add to the SDK registries and recipes.

## Reference Implementations To Port From

The old FLOW/Voice-Agent codebase contains working behavior and tested configs. See [`CONTEXT.md`](./CONTEXT.md#legacy-flow-porting-map). Port behavior and settings; do not preserve old file structure just because it existed.

## When You Do Not Know What To Do

1. Read `SPRINT_PLAN.md`.
2. Read `RECOVERY_PLAN.md`.
3. Read `BUILD_ORDER.md`.
4. If the question is about model support, keep the SDK extension path intact.
