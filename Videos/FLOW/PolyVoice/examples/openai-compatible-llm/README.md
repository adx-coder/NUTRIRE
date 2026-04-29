# OpenAI-Compatible LLM Example

Runs PolyVoice with mock STT and TTS, but sends the LLM turn to an OpenAI-compatible chat-completions endpoint.

```bash
polyvoice serve --config examples/openai-compatible-llm/config.yaml
```

Point `llm.params.endpoint_url` at a local vLLM, Ollama-compatible, OpenRouter, or OpenAI-style `/v1/chat/completions` endpoint.

You can also run against the preserved FLOW model registry:

```bash
polyvoice serve --config ../Voice-Agent/config.yaml --llm-model mistral_large
```

Then smoke-test the WebSocket in a second terminal:

```bash
python scripts/ws_smoke_client.py
```
