# PolyVoice

> A model-agnostic, platform-agnostic open framework for building **local-first** voice agents that run in production.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange.svg)](#status)

PolyVoice is a voice agent framework purpose-built for **regulated and on-premises deployments** — healthcare, banking, telecom, government — where the data and the models cannot leave your infrastructure. It composes any (ASR, LLM, TTS) including locally-served vLLM models, dials any CPaaS provider via clean adapters, and ships the production orchestration techniques (reversible barge-in, latency-aware filler scheduling, RAG, autonomous escalation) you actually need on real phone calls.

## Why PolyVoice

| | Cloud-API stacks (Vapi, Retell) | Open WebRTC frameworks (Pipecat, LiveKit) | **PolyVoice** |
|---|---|---|---|
| Open source | ❌ | ✅ | ✅ |
| Local models first-class | ❌ | retrofit | ✅ |
| vLLM-served TTS + ASR | ❌ | partial | ✅ |
| Multi-CPaaS adapter | locked to one | partial | ✅ |
| HIPAA / PCI deployment | ❌ | ❌ | ✅ |
| FreeSWITCH / Asterisk native | ❌ | ❌ | ✅ |

The position: **"the local-first complement to Pipecat."** Not a replacement — a different default. If your reference deployment is fully on-prem and your worry is BAA, FedRAMP, or PCI-DSS, this is your stack.

## Architecture at a glance

```
┌────────────────────────────────────────────────┐
│ Voice agent core                               │
│  (orchestration · barge-in · RAG · escalation) │
├────────────────────────────────────────────────┤
│ Service layer                                  │
│  ASR · LLM · TTS — uniform interface,          │
│  vLLM / local / cloud all first-class          │
├────────────────────────────────────────────────┤
│ Audio normalization                            │
│  μ-law · A-law · L16 · Opus → PCM16/16k mono   │
├────────────────────────────────────────────────┤
│ Telephony adapter                              │
│  FreeSWITCH · Asterisk · Twilio · Vonage ·     │
│  Telnyx · Plivo · raw SIP                      │
├────────────────────────────────────────────────┤
│ Carrier / PSTN                                 │
└────────────────────────────────────────────────┘
```

Read [`VISION.md`](./VISION.md) for the full positioning, what's in scope, and what's deliberately out.

## Status

**Pre-alpha — not production-ready.** Active development. APIs will break before `v1.0`.

This is a public scaffold. Core abstractions land in `v0.1`, telephony adapters in `v0.2`, the [TelephonyBench](./benchmarks/telephonybench/) evaluation suite and accompanying paper land in `v0.3`.

See [`CHANGELOG.md`](./CHANGELOG.md) for what's shipped and [`docs/roadmap.md`](./docs/roadmap.md) for what's coming.

## Quickstart (when v0.2 lands)

```bash
pip install "polyvoice[twilio,vllm]"
```

```python
from polyvoice import VoiceAgent
from polyvoice.services.asr import NemotronASR
from polyvoice.services.llm import VLLMService
from polyvoice.services.tts import MagpieTTS
from polyvoice.telephony import TwilioAdapter

agent = VoiceAgent(
    asr=NemotronASR(),
    llm=VLLMService(model="meta-llama/Llama-3.3-70B-Instruct"),
    tts=MagpieTTS(voice="default"),
    telephony=TwilioAdapter(account_sid=..., auth_token=...),
)

agent.serve(port=8092)
```

Hot-swap any component at runtime via `/config/asr`, `/config/llm`, `/config/tts`, `/config/telephony`.

## What ships in PolyVoice

**ASR services**: Nemotron streaming, Qwen3-ASR (vLLM), Whisper (local + API), Deepgram, AssemblyAI

**LLM services**: any OpenAI-compatible (vLLM, Ollama, llama.cpp, OpenRouter, ...), Mistral, Anthropic, Llama models served by vLLM directly

**TTS services**: Magpie, Soprano, Kokoro, Chatterbox / Chatterbox-MTL, Maya1 (vLLM), Voxtral (vLLM-Omni), ElevenLabs, Cartesia, Piper

**Telephony adapters**: FreeSWITCH (mod_audio_fork), Asterisk (AudioSocket), Twilio (Media Streams), Vonage, Telnyx, Plivo, raw SIP

**Orchestration**: reversible 3-stage barge-in classification, latency-aware filler scheduling, two-pass tool calling, interrupted-context preservation, grounded RAG with two-stage rerank, autonomous red-flag escalation

**Observability**: OpenTelemetry traces and metrics out of the box, immutable per-call audit logs

**Compliance profiles**: HIPAA-mode, PCI-mode (configuration-only — no code changes)

## What PolyVoice deliberately is *not*

- Not a WebRTC SFU (use [LiveKit](https://livekit.io) or [Daily](https://daily.co))
- Not a multi-modal vision/avatar framework (use [Pipecat](https://pipecat.ai) or [HeyGen](https://heygen.com))
- Not a cloud realtime API (use [OpenAI Realtime](https://platform.openai.com/docs/guides/realtime) or [Gemini Live](https://ai.google.dev/gemini-api/docs/multimodal-live))
- Not a browser-only chat-style voice product (use [Vapi](https://vapi.ai) or [Retell](https://retellai.com))

If your reference deployment is *cloud-first*, those are the right tools. PolyVoice exists for the cases they don't cover.

## Contributing

We welcome service plugins, telephony adapters, and orchestration improvements. See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the plugin contract and review process.

For security issues, see [`SECURITY.md`](./SECURITY.md).

## License

[Apache License 2.0](./LICENSE) — permissive, patent-grant included, regulated-buyer friendly.

## Acknowledgements

PolyVoice builds on the shoulders of [Pipecat](https://github.com/pipecat-ai/pipecat), [LiveKit Agents](https://github.com/livekit/agents), [vLLM](https://github.com/vllm-project/vllm), [vLLM-Omni](https://github.com/vllm-project/vllm-omni), [Silero VAD](https://github.com/snakers4/silero-vad), [Smart Turn](https://github.com/pipecat-ai/smart-turn), and the open speech-model ecosystem (Nemotron, Qwen, Magpie, Maya1, Voxtral, Kokoro, Whisper). We thank the maintainers of each.
