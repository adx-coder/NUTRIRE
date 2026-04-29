# AGENTS.md — Guidance for AI coding assistants

This file is read by AI coding assistants (Claude Code, Cursor, Codex, Aider, etc.) when they work on this repository. Humans should read [`CONTRIBUTING.md`](./CONTRIBUTING.md) and [`CONTEXT.md`](./CONTEXT.md) instead.

## Project context

PolyVoice is a model-agnostic, platform-agnostic open framework for building local-first voice agents. See [`VISION.md`](./VISION.md) for the positioning, [`STRUCTURE.md`](./STRUCTURE.md) for the file layout, [`SPRINT_PLAN.md`](./SPRINT_PLAN.md) for the work plan, and [`BUILD_ORDER.md`](./BUILD_ORDER.md) for the dependency-ordered build queue.

The core team is **NetoAI engineering**. Treat this as a serious open-source project: production-grade code, not prototype quality.

## How to find work

1. Open `BUILD_ORDER.md`. Find the lowest-numbered unfinished file in the active sprint.
2. Open the spec referenced in `[spec: NN]` (e.g., `specs/02-services-base.md`).
3. Read the spec end-to-end. Read any spec it depends on.
4. Read the existing reference implementation if `CONTEXT.md` lists one for that path (the legacy NetoAI Voice-Agent codebase).
5. Implement. Open a PR.

## Hard rules

- **Never invent a service / adapter / feature that isn't in [`STRUCTURE.md`](./STRUCTURE.md) and [`BUILD_ORDER.md`](./BUILD_ORDER.md).** If you think one is missing, propose it in a PR that updates both files.
- **Never expand scope beyond [`VISION.md`](./VISION.md).** WebRTC SFU, vision/avatar, cloud realtime APIs, mobile SDKs, IDE plugins — all out of scope. Don't add them, even if they look easy.
- **Never write code without a spec.** If you reach a file whose spec is missing, write the spec first in the same PR.
- **Never break a public API in a non-breaking version.** Use a deprecation cycle.
- **Never add a `utils.py`, `helpers.py`, `common.py`, `misc.py`, `*_v2.py`, or `*_old.py`.** Use a domain-specific name.
- **Never commit secrets, API keys, model weights, audio files, or DB files.** `.gitignore` blocks most of them; double-check.
- **Never run benchmarks in CI** — they require GPU and live providers. CI is unit-tests-only.

## Style requirements

- Python 3.11+, full type hints, `X | None` over `Optional[X]`, PEP 604 unions
- `loguru.logger` for all logging in library code; never bare `print()` or stdlib `logging`
- Pydantic 2 for config; never raw dicts in new code
- Async by default in I/O paths; sync helpers only for pure compute
- Docstrings (Google style) on every public class and method
- Errors raise from `polyvoice.core.exceptions`; never bare `Exception`
- Imports auto-sorted by ruff-isort
- Line length 100; ruff format handles it
- One class per file in `services/`, `telephony/`, `agents/tools/`

## Test requirements

Every PR adds or updates a test. Conventions:

- Unit tests under `tests/unit/<area>/test_<module>.py`
- Integration tests under `tests/integration/test_<scenario>.py`
- E2E tests under `tests/e2e/test_<scenario>.py`
- Mock services in `tests/mocks/` (already provided once Sprint 1 lands)
- GPU-required tests must be marked `@pytest.mark.gpu`
- Telephony tests against real providers must be marked `@pytest.mark.telephony`
- Slow tests (>5s) must be marked `@pytest.mark.slow`
- CI runs unit tests only; never relies on GPU or live providers

Coverage gate: 60% line coverage on touched modules. PRs that decrease coverage on a module are rejected.

## Commit / PR style

Conventional commits enforced:

```
<type>(<scope>): <subject>

<optional body>

<optional footer>
```

Types: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `chore`, `ci`, `build`, `style`.

Every PR must update `CHANGELOG.md` under the `## Unreleased` section.

PRs to `main` require:
- CI green
- 1 maintainer approval (`@netoai/engineering`)
- For paths under CODEOWNERS: the listed reviewers must approve

## Things that look like good ideas but aren't

- "Let me unify the ASR/LLM/TTS into one base class." → No. Three separate ABCs because the contracts genuinely differ.
- "Let me add a frame-based pipeline like Pipecat." → No. Defended architectural choice; see [VISION.md commitment 6](./VISION.md#six-architectural-commitments).
- "Let me add Realtime API support since OpenAI Realtime is popular." → No. Out of scope.
- "Let me consolidate `provider`, `loader`, `codec` into one class for the TTS layer." → No. Three layers, each with one responsibility.
- "Let me parallelize the codec normalization with multiprocessing." → No. The audio path is async I/O-bound, not CPU-bound, in the realistic latency budget. Don't optimize what isn't slow.
- "Let me cache the LLM responses." → Not in core. Caching belongs to the agent layer; even there, it's not in the critical path for v0.x.

## Things that look like overkill but aren't

- **Pydantic config models** for every config section. Yes, write them. Validation at startup beats debugging at runtime.
- **OpenTelemetry spans** at every async boundary. Yes, instrument them. Production deployments need this.
- **Audit log entries** for every model swap, every barge-in, every escalation. Yes, log them. Compliance needs them.
- **Mock services** for every real service. Yes, ship them. CI without GPU depends on them.

## Reference implementations to port from

The legacy NetoAI Voice-Agent codebase contains working implementations of most orchestration mechanisms. See [`CONTEXT.md`](./CONTEXT.md#what-youll-find-in-the-existing-netoai-codebase) for the porting map. **Port the behavior, not the file structure.** The new layout in [`STRUCTURE.md`](./STRUCTURE.md) is the canonical home; old paths are not.

## When you don't know what to do

1. Check the active sprint in [`SPRINT_PLAN.md`](./SPRINT_PLAN.md).
2. Look at the spec in `specs/`.
3. If still stuck, open a discussion. Don't guess and don't expand scope.
