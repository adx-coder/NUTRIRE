# Changelog

All notable changes to PolyVoice are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

While the project is `0.x`, breaking changes can occur in any release; we will call them out clearly in the entry. The first stable API contract lands at `1.0.0`.

## [Unreleased]

### Added
- Initial importable `polyvoice` package with core events, processor, session state,
  exception hierarchy, service ABCs, service registry, and unit tests.

### Changed
-

### Deprecated
-

### Removed
-

### Fixed
-

### Security
-

---

## [0.1.0-pre] — 2026-04-26

### Added

- Repository scaffold: `README`, `LICENSE` (Apache 2.0), `VISION`, `CONTRIBUTING`, `CODE_OF_CONDUCT`, `SECURITY`, `AGENTS`
- `STRUCTURE.md` — canonical file tree
- `CONTEXT.md` — master context document
- `SPRINT_PLAN.md` — 6-sprint plan to v0.2.1-beta
- `BUILD_ORDER.md` — dependency-ordered build queue
- `pyproject.toml` with all optional extras grouped (`asr`, `llm`, `tts`, `telephony`, `dev`, etc.)
- `.gitignore`, `.gitattributes`, `.python-version`, `.pre-commit-config.yaml`
- `.github/CODEOWNERS`, PR template, issue templates, dependabot config
- `.github/workflows/ci.yml` — pytest + ruff + mypy on PR
- `specs/` directory with module specifications (00–22)
- Empty package skeleton (`src/polyvoice/__init__.py` + `py.typed`)
- Smoke test (`tests/unit/test_smoke.py`)

### Notes

- This is the first public commit. **No feature code yet.** The repo exists as a scaffold for Sprints 1–6.
- License: Apache 2.0. Patent grant included.
- Contributors: NetoAI engineering team. See [CODEOWNERS](./.github/CODEOWNERS).

[Unreleased]: https://github.com/adx-coder/PolyVoice/compare/v0.1.0-pre...HEAD
[0.1.0-pre]: https://github.com/adx-coder/PolyVoice/releases/tag/v0.1.0-pre
