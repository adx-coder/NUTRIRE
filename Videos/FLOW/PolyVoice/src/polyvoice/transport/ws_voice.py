"""Browser-compatible voice WebSocket endpoint."""

from __future__ import annotations

import base64
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from polyvoice.audio.frames import AudioFrame
from polyvoice.core.events import TTSAudioEvent, ready_event
from polyvoice.runtime.pipeline import VoicePipeline


def _event_payload(event: Any) -> dict[str, Any]:
    if isinstance(event, TTSAudioEvent):
        payload = event.model_dump(mode="json", exclude={"audio"})
        if event.audio is not None:
            payload["audio"] = base64.b64encode(event.audio).decode("ascii")
        return payload
    payload = event.model_dump(mode="json")
    return payload


def register_voice_ws(app: FastAPI) -> None:
    """Register the `/v1/ws/voice/{session_id}` endpoint."""

    @app.websocket("/v1/ws/voice/{session_id}")
    async def voice_ws(websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        await websocket.send_json(ready_event(session_id).model_dump(mode="json"))
        pipeline: VoicePipeline = websocket.app.state.voice_pipeline
        sequence = 0

        try:
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    return
                if "bytes" not in message or message["bytes"] is None:
                    continue

                sequence += 1
                frame = AudioFrame(
                    audio=message["bytes"],
                    sample_rate=16_000,
                    channels=1,
                    format="pcm16",
                    sequence=sequence,
                )
                async for event in pipeline.process_audio_frame(session_id, frame):
                    await websocket.send_json(_event_payload(event))
        except WebSocketDisconnect:
            return
