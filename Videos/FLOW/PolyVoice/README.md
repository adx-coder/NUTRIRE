# PolyVoice

> A model-agnostic, platform-agnostic open framework for building local-first voice agents that can run in regulated production environments.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange.svg)](#status)

PolyVoice is aimed at voice agents for healthcare, banking, telecom, government, and other environments where data and model execution often need to stay inside your infrastructure. The long-term goal is a local-first stack with swappable ASR, LLM, TTS, VAD, telephony, orchestration, and compliance profiles.

The current recovery work is SDK-first: adding a new model should mean adding one loader/client/provider, registering it, adding a recipe, and running focused smoke tests. The runtime should not need to be rewritten for each model.

## Status

**Pre-alpha, SDK recovery active. Not production-ready. APIs will change before `v1.0`.**

What works today:

- Mock end-to-end voice pipeline over the current runtime contracts.
- Config loading, recipe loading, and a bridge for selected legacy FLOW config.
- Audio frames, codec helpers, resampling, and AGC utilities.
- TTS SDK with provider/codec/model-loader registries.
- Kokoro local TTS loader and smoke script.
- ASR SDK with Qwen3/Nemotron loader shape, VAD registry, and streaming processor.
- Qwen3 ASR recipe preserving the old GPU-tested FLOW defaults.
- LLM SDK with OpenAI-compatible client, response processor, conversation state, turn coordination, and service wrapper.
- OpenAI-compatible LLM/TTS examples and SDK integration tests.

Still in progress:

- Telephony adapters such as FreeSWITCH, Asterisk, Twilio, Vonage, Telnyx, Plivo, and raw SIP.
- Production orchestration: barge-in, filler scheduling, tool timing, RAG, escalation, audit logs, and observability.
- Real GPU smoke for Qwen3 ASR in this repo. The config has been preserved from the old FLOW codebase, but the heavy `qwen-asr[vllm]` path still needs a GPU environment.
- Model-extension docs and scaffold tooling.

See [`SPRINT_PLAN.md`](./SPRINT_PLAN.md), [`RECOVERY_PLAN.md`](./RECOVERY_PLAN.md), and [`BUILD_ORDER.md`](./BUILD_ORDER.md) for the live plan.

## Current Quickstart

Install for local development:

```bash
pip install -e ".[dev]"
```

Run the CPU-safe tests:

```bash
python -m pytest tests/unit tests/integration/test_pipeline_mocks.py tests/integration/test_pipeline_sdks.py
```

Run the mock runtime example:

```bash
python -m polyvoice.cli run examples/mock-runtime/config.yaml
```

Run Kokoro local TTS smoke:

```bash
pip install -e ".[kokoro]"
python scripts/kokoro_smoke.py --device cpu --output C:\tmp\kokoro_smoke.wav
```

Run Qwen3 ASR SDK smoke without loading the real GPU model:

```bash
python scripts/qwen3_asr_smoke.py --fake-qwen-asr --language en --device cpu
```

The real Qwen3 ASR recipe is in [`examples/qwen3-asr-local/config.yaml`](./examples/qwen3-asr-local/config.yaml). It keeps the old tested FLOW GPU settings, including `device: cuda`, `gpu_memory_utilization: 0.08`, `max_model_len: 4096`, and the low-latency VAD/streaming windows.

## Architecture At A Glance

```text
Carrier / PSTN
  -> Telephony adapter edge
  -> Audio normalization
  -> ASR SDK / service
  -> LLM SDK / service
  -> TTS SDK / service
  -> Transport/runtime
```

The target architecture includes orchestration, tools, RAG, observability, compliance profiles, and multiple telephony adapters. The implemented recovery baseline is concentrated in:

- `src/polyvoice/config/`
- `src/polyvoice/audio/`
- `src/polyvoice/runtime/`
- `src/polyvoice/transport/`
- `src/polyvoice/services/asr_sdk/`
- `src/polyvoice/services/llm_sdk/`
- `src/polyvoice/services/tts_sdk/`

Read [`VISION.md`](./VISION.md) for the full product thesis.

## Provider Targets

Current or partially recovered:

- ASR: Qwen3 ASR, Nemotron shape, Silero/energy VAD paths.
- LLM: OpenAI-compatible providers such as vLLM, Ollama, llama.cpp, OpenRouter, and local gateways.
- TTS: Kokoro local loader and OpenAI-compatible TTS path.

Planned provider families:

- ASR: Whisper, Deepgram, AssemblyAI.
- TTS: Magpie, Soprano, Chatterbox, Maya1, Voxtral, ElevenLabs, Cartesia, Piper.
- Telephony: FreeSWITCH, Asterisk, Twilio, Vonage, Telnyx, Plivo, raw SIP.

## What PolyVoice Deliberately Is Not

- Not a WebRTC SFU. Use LiveKit or Daily for that.
- Not a multi-modal vision/avatar framework. Use Pipecat or HeyGen for that.
- Not a cloud realtime API. Use OpenAI Realtime or Gemini Live for that.
- Not a browser-only chat-style voice product. Use Vapi or Retell for that.

If your reference deployment is cloud-first, those may be the right tools. PolyVoice exists for the cases they do not cover.

## Contributing

We welcome service plugins, telephony adapters, orchestration improvements, and hardening work. See [`CONTRIBUTING.md`](./CONTRIBUTING.md), [`CONTEXT.md`](./CONTEXT.md), and [`AGENTS.md`](./AGENTS.md) before making architecture changes.

For security issues, see [`SECURITY.md`](./SECURITY.md).

## License

[Apache License 2.0](./LICENSE). Permissive, patent-grant included, regulated-buyer friendly.

## Acknowledgements

PolyVoice builds on patterns from Pipecat, LiveKit Agents, vLLM, vLLM-Omni, Silero VAD, Smart Turn, and the open speech-model ecosystem including Nemotron, Qwen, Magpie, Maya1, Voxtral, Kokoro, and Whisper.
