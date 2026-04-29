"""Tests for OpenAI-compatible TTS service."""

from __future__ import annotations

from collections.abc import AsyncIterator
import json

import httpx
import pytest

from polyvoice.core.exceptions import ServiceError
from polyvoice.services.tts import OpenAICompatibleTTS


async def _text_once(value: str) -> AsyncIterator[str]:
    yield value


async def test_synthesize_stream_posts_openai_speech_payload_and_returns_wav() -> None:
    seen_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, content=b"RIFFfake-wav")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = OpenAICompatibleTTS(
        endpoint_url="http://tts.local/v1/audio/speech",
        model="tts-test",
        voice="alloy",
        response_format="wav",
        client=client,
    )

    chunks = [chunk async for chunk in service.synthesize_stream(_text_once("hello"))]
    await client.aclose()

    assert len(chunks) == 1
    assert chunks[0].audio == b"RIFFfake-wav"
    assert chunks[0].format == "wav"
    assert chunks[0].sample_rate == 24_000
    assert seen_payloads == [
        {
            "model": "tts-test",
            "input": "hello",
            "voice": "alloy",
            "response_format": "wav",
        }
    ]


async def test_synthesize_stream_supports_pcm_and_overrides() -> None:
    seen_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, content=b"\x00\x00\x01\x00")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = OpenAICompatibleTTS(
        endpoint_url="http://tts.local/v1/audio/speech",
        model="tts-test",
        voice="alloy",
        response_format="pcm",
        sample_rate=16_000,
        speed=1.2,
        extra_body={"task_type": "Base"},
        client=client,
    )

    chunks = [
        chunk
        async for chunk in service.synthesize_stream(
            _text_once("hello"),
            voice="verse",
            language="en",
        )
    ]
    await client.aclose()

    assert chunks[0].audio == b"\x00\x00\x01\x00"
    assert chunks[0].format == "pcm16"
    assert chunks[0].sample_rate == 16_000
    assert seen_payloads[0] == {
        "model": "tts-test",
        "input": "hello",
        "voice": "verse",
        "response_format": "pcm",
        "speed": 1.2,
        "language": "en",
        "task_type": "Base",
    }


async def test_synthesize_stream_raises_service_error_for_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"boom")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = OpenAICompatibleTTS(
        endpoint_url="http://tts.local/v1/audio/speech",
        model="tts-test",
        client=client,
    )

    with pytest.raises(ServiceError, match="500"):
        [_ async for _ in service.synthesize_stream(_text_once("hello"))]
    await client.aclose()

