# Mock Runtime Example

Runs PolyVoice with in-process mock STT, LLM, and TTS services.

```bash
polyvoice serve --config examples/mock-runtime/config.yaml
```

This is the fastest way to validate the HTTP server and `/v1/ws/voice/{session_id}` WebSocket without credentials or model servers.

In a second terminal, run the smoke client:

```bash
python scripts/ws_smoke_client.py
```

It sends a short PCM16 tone and prints received event types until `tts_audio_chunk` arrives.
