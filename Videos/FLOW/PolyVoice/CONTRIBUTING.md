# Contributing to PolyVoice

Thanks for the interest. PolyVoice is in pre-alpha; we welcome contributors but the architecture is moving fast and PRs that miss the [vision](./VISION.md) will be sent back. Read that first.

## Quick start for contributors

```bash
git clone https://github.com/adx-coder/PolyVoice.git
cd PolyVoice
python -m venv .venv
source .venv/bin/activate          # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
pre-commit install
pytest tests/unit                   # should pass
```

For services / telephony work you'll typically want one of:

```bash
pip install -e ".[dev,vllm]"        # local LLM dev
pip install -e ".[dev,twilio]"      # Twilio adapter dev
pip install -e ".[dev,freeswitch]"  # FreeSWITCH adapter dev
```

## What kinds of contributions we want

In priority order:

1. **Telephony adapters** for CPaaS providers we don't yet support (see [in-scope list](./VISION.md#in-scope))
2. **Service plugins** for ASR / LLM / TTS — especially anything new in the open-weights world
3. **Bug fixes** with a regression test
4. **Examples** for novel deployments (PSTN, on-prem, RAG agents, function-calling agents)
5. **Documentation** improvements (we're under-invested here)
6. **Compliance hardening** (HIPAA-mode, PCI-mode profiles)

## What we don't want

- WebRTC SFU integrations — out of scope, see [VISION.md](./VISION.md#out-of-scope-and-we-say-so-loudly)
- Multi-modal / vision / avatar features — out of scope
- Cloud-realtime API wrappers (OpenAI Realtime, Gemini Live) — out of scope
- "I added 30 cloud TTS providers" — we're deliberately not chasing breadth there
- Refactors with no functional change beyond style

If you're not sure whether your idea is in scope, open a discussion first.

## How to add a new service

A service is an ASR, LLM, or TTS plugin. The contract:

1. Subclass the base from `polyvoice.services.base`:
   ```python
   from polyvoice.services.base import LLMService

   class MyLLM(LLMService):
       async def stream_chat(self, messages, tools=None): ...
   ```
2. Place it under `src/polyvoice/services/{asr,llm,tts}/<name>.py`
3. Add an optional dependency extra to `pyproject.toml` if you need extra packages:
   ```toml
   [project.optional-dependencies]
   my_llm = ["my-llm-sdk>=1.0"]
   ```
4. Add a `tests/unit/services/{asr,llm,tts}/test_<name>.py` with at least:
   - Construction succeeds with valid config
   - Construction fails clearly with invalid config
   - Streaming output is well-formed (use `MockLLMService` in `tests/mocks/` as a reference shape)
5. Add an entry to `docs/services/<name>.md` with: configuration options, an example, supported features, known limitations
6. Update `CHANGELOG.md` under the unreleased section

GPU-required tests should be marked `@pytest.mark.gpu` and will be skipped in standard CI. Integration tests with a real cloud API should be marked `@pytest.mark.integration` and gated on an environment variable for credentials.

## How to add a new telephony adapter

Adapters live under `src/polyvoice/telephony/<provider>.py`. Contract:

1. Subclass `polyvoice.telephony.base.TelephonyAdapter`. You implement:
   - `accept_inbound(webhook_payload) -> CallSession`
   - `initiate_outbound(to_number, params) -> CallSession`
   - `stream_in(session) -> AsyncIterator[AudioFrame]`
   - `stream_out(session, frames: AsyncIterator[AudioFrame]) -> None`
   - `hangup(session)`, `transfer(session, target)`
   - Declare `inbound_codec` and `outbound_codec` (the framework normalizes to PCM16/16k mono internally)
2. The framework provides codec conversion (`polyvoice.telephony.codecs`) — your adapter only deals in the codec the provider speaks natively.
3. Tests: `tests/unit/telephony/test_<provider>.py` using mocked WebSocket / HTTP responses (we ship `aioresponses` patterns).
4. End-to-end test: `tests/e2e/telephony/test_<provider>_smoke.py` with `@pytest.mark.telephony` — runs against the real provider, gated on credentials. Optional but encouraged.
5. Documentation: `docs/telephony/<provider>.md` with on-the-wire protocol details, codec, call control method, quirks.

## Code style

- **Formatter**: ruff format (alias for black-compatible formatting, line length 100)
- **Linter**: ruff
- **Types**: full mypy strict mode on `src/polyvoice/`
- **Imports**: ruff-isort (auto-fixed by pre-commit)
- **Logging**: use `loguru` — never bare `print()` or `logging.getLogger()` in library code
- **Docstrings**: Google style; required for all public methods
- **Async**: prefer `anyio` over raw `asyncio` where structured concurrency helps

Run the full check locally before pushing:

```bash
pre-commit run --all-files
mypy src/
pytest tests/unit
```

## Commit style

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body — optional>

<footer — optional>
```

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `ci`, `build`.

Examples:
- `feat(telephony): add Vonage Voice WebSocket adapter`
- `fix(orchestration): cancel push-stream on barge-in pause`
- `docs(architecture): document Processor base class contract`

Pre-commit enforces this on commit messages.

## PR checklist

Every PR must:

- [ ] Pass CI (pytest unit + ruff + mypy)
- [ ] Have at least one new or updated test
- [ ] Update `CHANGELOG.md` under the `## Unreleased` section
- [ ] Have a clear description: what changed, why, breaking changes, screenshot/log if useful
- [ ] Link to an issue (or use `closes #N`)
- [ ] Have one approval from a maintainer

PRs that touch `polyvoice/observability/audit.py`, `polyvoice/compliance/`, or any HIPAA/PCI-mode profile require approval from a CODEOWNERS-listed maintainer.

## Reporting bugs

Use the issue templates. Bug reports must include:
- PolyVoice version
- Python version
- OS
- Minimal reproducer
- Logs (use `loguru` debug level)

## Reporting security issues

**Do not file public issues for security problems.** See [`SECURITY.md`](./SECURITY.md) for the responsible disclosure process.

## Code of Conduct

Be kind. See [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md). Maintainers will enforce it.
