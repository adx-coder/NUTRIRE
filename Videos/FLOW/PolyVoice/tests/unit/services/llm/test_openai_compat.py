"""Tests for OpenAI-compatible LLM service."""

from __future__ import annotations

import json

import httpx
import pytest

from polyvoice.core.exceptions import ServiceError
from polyvoice.services.base import ChatMessage
from polyvoice.services.llm import OpenAICompatibleLLM


def _sse(data: dict | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data)
    return f"data: {payload}\n\n"


async def test_stream_chat_parses_sse_chunks_and_final() -> None:
    seen_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.content.decode("utf-8")))
        body = "".join(
            [
                _sse({"choices": [{"delta": {"content": "Hel"}}]}),
                _sse({"choices": [{"delta": {"content": "lo"}}]}),
                _sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
                _sse({"usage": {"prompt_tokens": 3, "completion_tokens": 2}}),
                _sse("[DONE]"),
            ]
        )
        return httpx.Response(200, content=body.encode("utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = OpenAICompatibleLLM(
        endpoint_url="http://llm.local/v1/chat/completions",
        model="test-model",
        client=client,
    )

    chunks = [
        chunk
        async for chunk in service.stream_chat(
            [ChatMessage(role="user", content="Say hello")],
            temperature=0.2,
            max_tokens=12,
        )
    ]
    await client.aclose()

    assert [chunk.text for chunk in chunks] == ["Hel", "lo", "", ""]
    assert chunks[-1].is_final
    assert chunks[-2].metadata == {"usage": {"prompt_tokens": 3, "completion_tokens": 2}}
    assert seen_payloads == [
        {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Say hello"}],
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": 0.2,
            "max_tokens": 12,
        }
    ]


async def test_stream_chat_includes_tools_when_provided() -> None:
    seen_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, content=_sse("[DONE]").encode("utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = OpenAICompatibleLLM(
        endpoint_url="http://llm.local/v1/chat/completions",
        model="test-model",
        client=client,
    )

    chunks = [
        chunk
        async for chunk in service.stream_chat(
            [ChatMessage(role="user", content="Use a tool")],
            tools=[{"type": "function", "function": {"name": "lookup"}}],
        )
    ]
    await client.aclose()

    assert chunks == [chunks[0]]
    assert chunks[0].is_final
    assert seen_payloads[0]["tools"] == [
        {"type": "function", "function": {"name": "lookup"}}
    ]


async def test_stream_chat_preserves_tool_call_deltas() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = _sse(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "lookup", "arguments": "{}"},
                                }
                            ]
                        }
                    }
                ]
            }
        )
        return httpx.Response(200, content=body.encode("utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = OpenAICompatibleLLM(
        endpoint_url="http://llm.local/v1/chat/completions",
        model="test-model",
        client=client,
    )

    chunks = [
        chunk
        async for chunk in service.stream_chat([ChatMessage(role="user", content="go")])
    ]
    await client.aclose()

    assert chunks[0].tool_calls[0]["id"] == "call_1"


async def test_stream_chat_raises_service_error_for_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"boom")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = OpenAICompatibleLLM(
        endpoint_url="http://llm.local/v1/chat/completions",
        model="test-model",
        client=client,
    )

    with pytest.raises(ServiceError, match="500"):
        [_ async for _ in service.stream_chat([ChatMessage(role="user", content="hi")])]
    await client.aclose()


async def test_stream_chat_raises_service_error_for_invalid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"data: nope\n\n")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = OpenAICompatibleLLM(
        endpoint_url="http://llm.local/v1/chat/completions",
        model="test-model",
        client=client,
    )

    with pytest.raises(ServiceError, match="Invalid JSON"):
        [_ async for _ in service.stream_chat([ChatMessage(role="user", content="hi")])]
    await client.aclose()

