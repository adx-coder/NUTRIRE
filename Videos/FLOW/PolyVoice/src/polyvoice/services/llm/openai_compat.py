"""OpenAI-compatible streaming chat-completions LLM service."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from polyvoice.core.exceptions import ServiceError
from polyvoice.services.base import ChatMessage, LLMChunk, LLMService


class OpenAICompatibleLLM(LLMService):
    """LLM adapter for OpenAI-compatible `/chat/completions` endpoints."""

    name = "openai-compatible"

    def __init__(
        self,
        *,
        endpoint_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
        default_temperature: float = 0.7,
        default_max_tokens: int = 200,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens
        self._client = client
        self._owns_client = client is None

    async def start(self) -> None:
        """Create an HTTP client if one was not injected."""

        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=self.timeout_seconds,
                    write=10.0,
                    pool=10.0,
                ),
            )

    async def stop(self) -> None:
        """Close the owned HTTP client."""

        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream assistant chunks from an OpenAI-compatible endpoint."""

        if self._client is None:
            await self.start()
        if self._client is None:
            raise ServiceError("HTTP client was not initialized")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [self._message_payload(message) for message in messages],
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": self.default_temperature if temperature is None else temperature,
            "max_tokens": self.default_max_tokens if max_tokens is None else max_tokens,
        }
        if tools:
            payload["tools"] = list(tools)

        try:
            async with self._client.stream("POST", self.endpoint_url, json=payload) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    detail = body.decode("utf-8", errors="replace")
                    raise ServiceError(
                        f"LLM endpoint returned {response.status_code}: {detail}"
                    )

                index = 0
                async for line in response.aiter_lines():
                    for chunk in self._parse_sse_line(line, index):
                        index += 1
                        yield chunk
        except httpx.HTTPError as exc:
            raise ServiceError(f"LLM request failed: {exc}") from exc

        yield LLMChunk(text="", is_final=True)

    @staticmethod
    def _message_payload(message: ChatMessage) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.name:
            payload["name"] = message.name
        if message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        return payload

    @staticmethod
    def _parse_sse_line(line: str, chunk_id: int) -> list[LLMChunk]:
        stripped = line.strip()
        if not stripped:
            return []
        if stripped.startswith("data:"):
            stripped = stripped[5:].strip()
        if stripped == "[DONE]":
            return []

        try:
            event = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ServiceError("Invalid JSON in LLM stream") from exc

        usage = event.get("usage")
        choices = event.get("choices") or []
        if not choices:
            if usage:
                return [LLMChunk(text="", chunk_id=chunk_id, metadata={"usage": usage})]
            return []

        choice = choices[0]
        delta = choice.get("delta") or {}
        content = delta.get("content") or ""
        tool_calls = delta.get("tool_calls") or []
        finish_reason = choice.get("finish_reason")

        if not content and not tool_calls and not usage:
            return []

        return [
            LLMChunk(
                text=content,
                chunk_id=chunk_id,
                tool_calls=tool_calls,
                metadata={
                    key: value
                    for key, value in {
                        "finish_reason": finish_reason,
                        "usage": usage,
                    }.items()
                    if value is not None
                },
            )
        ]

