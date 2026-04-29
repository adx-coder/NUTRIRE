"""Mock end-to-end runtime tests."""

import json

from fastapi.testclient import TestClient
import httpx
import numpy as np

from polyvoice.runtime import create_app, create_mock_pipeline
from polyvoice.runtime.pipeline import VoicePipeline
from polyvoice.services.llm import OpenAICompatibleLLM
from polyvoice.services.mocks import MockLLMService, MockSTTService, MockTTSService
from polyvoice.services.tts import OpenAICompatibleTTS
from polyvoice.services.tts_sdk import SDKTTSService, TTSConfig, TTSRequest
from polyvoice.services.tts_sdk.model_loaders import BaseModelLoader, register_model_loader


@register_model_loader("fake_model")
class FakeModelLoader(BaseModelLoader):
    async def load(self, config: dict) -> None:
        pass

    async def synthesize(self, text: str, request: TTSRequest) -> tuple[np.ndarray, int]:
        return np.full(160, 0.25, dtype=np.float32), 16_000

    async def unload(self) -> None:
        pass

    @property
    def native_sample_rate(self) -> int:
        return 16_000

    @property
    def loader_name(self) -> str:
        return "fake_model"


def test_health_and_config_status() -> None:
    app = create_app(create_mock_pipeline())

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok", "service": "polyvoice"}
        assert client.get("/ready").json() == {"status": "ready"}
        assert client.get("/config/status").json() == {
            "stt": {"provider": "mock-stt"},
            "llm": {"provider": "mock-llm", "model": None},
            "tts": {"provider": "mock-tts"},
        }


def test_voice_websocket_runs_mock_pipeline() -> None:
    app = create_app(create_mock_pipeline())

    with TestClient(app) as client:
        with client.websocket_connect("/v1/ws/voice/session-1") as ws:
            assert ws.receive_json()["type"] == "ready"

            ws.send_bytes(b"\x00\x01" * 512)

            events = [ws.receive_json() for _ in range(5)]

    assert [event["type"] for event in events] == [
        "asr_partial",
        "asr_final",
        "llm_chunk",
        "llm_complete",
        "tts_audio_chunk",
    ]
    assert events[1]["text"] == "hello from mock audio"
    assert events[3]["text"] == "Echo: hello from mock audio"
    assert events[4]["audio"]


def test_voice_websocket_runs_openai_compatible_llm_pipeline() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "test-llm"
        body = "\n\n".join(
            [
                'data: {"choices":[{"delta":{"content":"Real "}}]}',
                'data: {"choices":[{"delta":{"content":"LLM"}}]}',
                "data: [DONE]",
            ]
        )
        return httpx.Response(200, content=body.encode("utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pipeline = VoicePipeline(
        stt=MockSTTService(),
        llm=OpenAICompatibleLLM(
            endpoint_url="http://llm.local/v1/chat/completions",
            model="test-llm",
            client=client,
        ),
        tts=MockTTSService(),
    )
    app = create_app(pipeline)

    with TestClient(app) as test_client:
        with test_client.websocket_connect("/v1/ws/voice/session-2") as ws:
            assert ws.receive_json()["type"] == "ready"

            ws.send_bytes(b"\x00\x01" * 512)
            events = [ws.receive_json() for _ in range(6)]

    assert [event["type"] for event in events] == [
        "asr_partial",
        "asr_final",
        "llm_chunk",
        "llm_chunk",
        "llm_complete",
        "tts_audio_chunk",
    ]
    assert events[2]["text"] == "Real "
    assert events[3]["text"] == "LLM"
    assert events[4]["text"] == "Real LLM"
    assert events[5]["audio"]


def test_voice_websocket_runs_openai_compatible_tts_pipeline() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "tts-test"
        assert payload["input"] == "Echo: hello from mock audio"
        return httpx.Response(200, content=b"RIFFreal-tts")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pipeline = VoicePipeline(
        stt=MockSTTService(),
        llm=MockLLMService(),
        tts=OpenAICompatibleTTS(
            endpoint_url="http://tts.local/v1/audio/speech",
            model="tts-test",
            client=client,
        ),
    )
    app = create_app(pipeline)

    with TestClient(app) as test_client:
        with test_client.websocket_connect("/v1/ws/voice/session-3") as ws:
            assert ws.receive_json()["type"] == "ready"

            ws.send_bytes(b"\x00\x01" * 512)
            events = [ws.receive_json() for _ in range(5)]

    assert [event["type"] for event in events] == [
        "asr_partial",
        "asr_final",
        "llm_chunk",
        "llm_complete",
        "tts_audio_chunk",
    ]
    assert events[4]["audio"]


def test_voice_websocket_runs_sdk_tts_pipeline() -> None:
    pipeline = VoicePipeline(
        stt=MockSTTService(),
        llm=MockLLMService(),
        tts=SDKTTSService(
            config=TTSConfig(
                providers=[
                    {
                        "provider": "local_model",
                        "model_loader": "fake_model",
                        "name": "fake",
                    }
                ]
            ),
            provider="fake",
            output_sample_rate=16_000,
        ),
    )
    app = create_app(pipeline)

    with TestClient(app) as test_client:
        with test_client.websocket_connect("/v1/ws/voice/session-4") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_bytes(b"\x00\x01" * 512)
            events = [ws.receive_json() for _ in range(5)]

    assert [event["type"] for event in events] == [
        "asr_partial",
        "asr_final",
        "llm_chunk",
        "llm_complete",
        "tts_audio_chunk",
    ]
    assert events[4]["audio"]
