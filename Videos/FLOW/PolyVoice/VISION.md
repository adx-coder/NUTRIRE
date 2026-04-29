# PolyVoice — Vision

## One-line statement

> A model-agnostic, platform-agnostic open framework for building local-first voice agents that run in production.

## What this means concretely

**Model-agnostic** — every (ASR, LLM, TTS) is swappable. Locally-served models (vLLM, in-process, GGUF, ONNX) are first-class citizens, not retrofitted. Cloud APIs are an option, not the default. The reference deployment guide shows fully-local; cloud is an appendix.

**Platform-agnostic** — every telephony / CPaaS provider is supported via a clean adapter contract. SIP, FreeSWITCH, Asterisk, Twilio, Vonage, Telnyx, Plivo are all peers. No primary lock-in to any vendor's transport.

**Local-first that works** — production-grade for on-prem deployment in regulated industries: healthcare (HIPAA, BAA), banking (PCI-DSS), telecom-internal (cost, latency), government (FedRAMP, FISMA, air-gap). Not a demo. Not "you can theoretically run it on-prem if you wire it up."

## The market gap we fill

| | Open? | Default path | Local-first? | Telephony-native? |
|---|---|---|---|---|
| Pipecat | yes | cloud APIs | retrofit | yes |
| LiveKit Agents | yes | WebRTC + cloud | retrofit | partial |
| Vapi / Retell / Cresta | no | closed cloud | no | yes |
| OpenAI Realtime / Gemini Live | no | closed cloud | no | no |
| Daily Agents | yes | WebRTC SFU | retrofit | partial |
| **PolyVoice** | **yes** | **local vLLM + on-prem** | **first-class** | **first-class, multi-CPaaS** |

Regulated industries are forced to local-first by compliance, but every existing framework treats local as a footnote. PolyVoice fills that slot.

## Six architectural commitments

These flow from the vision. Treat them as forced moves, not suggestions.

1. **vLLM-everywhere is the reference path.** vLLM-served LLM, vLLM-served ASR (Qwen3-ASR), vLLM-served TTS (Maya1, Voxtral via vllm_omni). The reference deployment guide assumes fully-local; cloud is supported but not preferred.

2. **Every model and platform is swappable at runtime.** The `/config/asr|llm|tts|telephony` hot-swap endpoints are core. Configuration over code.

3. **Telephony is a first-class transport, not an integration.** FreeSWITCH, Asterisk, raw SIP are core. Twilio, Vonage, Telnyx are wrappers around the same core. The default deployment can dial real phone numbers.

4. **Compliance is a first-class concern.** HIPAA-mode and PCI-mode are configuration profiles, not aspirations. Audit logging, data-residency boundaries, BAA-friendly architecture, no telemetry to vendors-by-default.

5. **The orchestration techniques are core, not examples.** Reversible barge-in, latency-aware filler scheduling, RAG, autonomous escalation, two-pass tool calling — these ship in the core because every regulated voice agent needs them.

6. **Event-driven WebSocket pipeline + minimal Processor abstraction.** Not frame-based (that's Pipecat's terrain and earns its keep mainly for multimodal, which is out of scope). Extract a small `Processor` base so external contributors can plug stages in, but keep the WebSocket event protocol as the wire format. **This is a defended architectural choice, not a missing feature.**

## In scope

- Local-vLLM-served ASR/LLM/TTS as first-class
- 4–5 cloud providers per category as second-class (Deepgram, OpenAI, ElevenLabs, Cartesia for the "we support these too" claim)
- Telephony adapters: FreeSWITCH, Asterisk, Twilio, Vonage, Telnyx, raw SIP, Plivo
- Voice orchestration: barge-in, fillers, function calling, RAG, escalation
- HIPAA-mode and PCI-mode deployment profiles
- Helm chart + docker-compose + on-prem install guide
- TelephonyBench (open evaluation suite)
- OpenTelemetry observability with no vendor lock-in
- Per-call audit logs for compliance

## Out of scope (and we say so loudly)

- WebRTC SFU as primary transport — Daily and LiveKit own this
- Multi-modal vision / avatar (HeyGen, Tavus, Simli) — different product
- Realtime end-to-end APIs (OpenAI Realtime, Gemini Live) — they contradict the local-first vision
- 25+ cloud TTS providers as Pipecat does — irrelevant to local-first
- Browser-only chat-style voice — Vapi's territory
- IDE plugins, mobile SDKs, embedded ESP32 — let other projects own that

When someone files an issue asking for one of these, the answer is "out of scope, here's why" with a link to this section.

## North-star metrics

How we'll know PolyVoice is succeeding:

- **Time-to-deploy on-prem**: from `git clone` to first real PSTN call answered, fully-local, in under 30 minutes
- **Adapter portability**: same agent code runs unchanged across at least 4 telephony providers
- **Compliance readiness**: a healthcare or banking buyer can deploy without writing custom code for audit, data residency, or BAA-friendly architecture
- **Latency on local stack**: end-to-end p95 under 1.2 seconds on a single H100 with fully-local models
- **Community adoption**: external contributors land at least one new service or adapter per quarter by the end of year one

## Anti-goals

- Becoming a Pipecat clone
- Out-feature-counting cloud providers (we will *always* be behind on cloud-API breadth — that's fine)
- Becoming a SaaS company in addition to an OSS framework
- Adding a feature because a single user demanded it without it fitting the vision

## Read next

- [`README.md`](./README.md) — the public-facing pitch
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — how to add a service or adapter
- `docs/architecture.md` — the architecture in depth (lands Sprint 1)
- `docs/compliance.md` — HIPAA-mode and PCI-mode profiles (lands Sprint 5)
