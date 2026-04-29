# Kokoro Local TTS

Runs the PolyVoice runtime with mock ASR/LLM and real Kokoro TTS through the SDK.

Install Kokoro first:

```bash
pip install kokoro soundfile
```

Run:

```bash
polyvoice serve --config examples/kokoro-local/config.yaml
```

The first run may download `hexgrad/Kokoro-82M`.
