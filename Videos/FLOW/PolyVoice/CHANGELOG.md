# Changelog

All notable changes to PolyVoice are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

While the project is `0.x`, breaking changes can occur in any release; we will call them out clearly in the entry. The first stable API contract lands at `1.0.0`.

## [Unreleased]

### Added

- SDK-first runtime recovery with config loading, mock pipeline, health checks, CLI bootstrap, and WebSocket voice transport.
- Audio primitives for frames, codec conversion, resampling, and AGC.
- TTS SDK with provider, codec, and model-loader registries.
- Kokoro local TTS loader, `kokoro` optional dependency group, example config, and smoke script.
- ASR SDK with model-loader registry, Qwen3/Nemotron loader shape, VAD registry, and streaming processor.
- Qwen3 ASR example and smoke script, including fake mode for CPU-safe CI/dev validation.
- LLM SDK with OpenAI-compatible client, response processor, conversation state, turn coordination, metrics, and service wrapper.
- Legacy FLOW config bridge and recipe tests for selected model settings.
- Integration tests covering mock runtime and SDK-backed pipeline wiring.
- Model-extension guide, scaffold script, and golden ASR/VAD/LLM/TTS extension contract tests.

### Changed

- Preserved old FLOW Qwen3 ASR GPU-tested defaults, including `gpu_memory_utilization: 0.08`, `max_model_len: 4096`, low-latency streaming windows, and Silero VAD thresholds.
- Refreshed project planning docs around the SDK-first recovery path instead of one-off provider wiring.
- Added VAD and LLM client registry listing helpers to match ASR model and TTS loader discovery.

### Fixed

- Nested legacy ASR recipe extraction now forces the nested backend key, preventing Qwen3 recipes from inheriting an unrelated active backend.
- VAD recipe mapping now prefers `vad.backend` before legacy fallback fields.

### Verification

- `python -m pytest tests/unit tests/integration/test_pipeline_mocks.py tests/integration/test_pipeline_sdks.py`
- `python scripts/kokoro_smoke.py --device cpu --output C:\tmp\kokoro_smoke.wav`
- `python scripts/qwen3_asr_smoke.py --fake-qwen-asr --language en --device cpu`

---

## [0.1.0-pre] - 2026-04-26

### Added

- Repository scaffold: `README`, `LICENSE` (Apache 2.0), `VISION`, `CONTRIBUTING`, `CODE_OF_CONDUCT`, `SECURITY`, `AGENTS`.
- `STRUCTURE.md` canonical file tree.
- `CONTEXT.md` master context document.
- `SPRINT_PLAN.md` sprint plan.
- `BUILD_ORDER.md` dependency-ordered build queue.
- `pyproject.toml` with optional extras grouped by feature family.
- `.gitignore`, `.gitattributes`, `.python-version`, `.pre-commit-config.yaml`.
- GitHub templates and CI skeleton.
- Empty package skeleton and smoke test.

### Notes

- Initial public planning/scaffold commit.
- License: Apache 2.0. Patent grant included.

[Unreleased]: https://github.com/adx-coder/PolyVoice/compare/v0.1.0-pre...HEAD
[0.1.0-pre]: https://github.com/adx-coder/PolyVoice/releases/tag/v0.1.0-pre
