# OpenAI-Compatible TTS Example

Runs PolyVoice with mock STT and LLM, but sends assistant text to an OpenAI-compatible `/v1/audio/speech` endpoint.

```bash
polyvoice serve --config examples/openai-compatible-tts/config.yaml
```

Then smoke-test the WebSocket in a second terminal:

```bash
python scripts/ws_smoke_client.py
```

