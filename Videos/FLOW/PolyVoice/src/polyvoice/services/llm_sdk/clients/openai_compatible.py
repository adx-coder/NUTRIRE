"""OpenAI-compatible client for the LLM SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

from polyvoice.services.base import ChatMessage, LLMChunk
from polyvoice.services.llm import OpenAICompatibleLLM
from polyvoice.services.llm_sdk.clients.base import BaseLLMClient
from polyvoice.services.llm_sdk.clients.registry import register_llm_client


@register_llm_client("openai_compatible")
@register_llm_client("openai-compatible")
class OpenAICompatibleClient(BaseLLMClient):
    """SDK client backed by the existing OpenAI-compatible transport."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.client = OpenAICompatibleLLM(
            endpoint_url=str(config["endpoint_url"]),
            model=str(config.get("model") or config.get("model_name")),
            api_key=config.get("api_key"),
            timeout_seconds=float(config.get("timeout_seconds", 30.0)),
            default_temperature=float(config.get("temperature", 0.7)),
            default_max_tokens=int(config.get("max_tokens", 200)),
        )

    async def start(self) -> None:
        await self.client.start()

    async def stop(self) -> None:
        await self.client.stop()

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        async for chunk in self.client.stream_chat(
            messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk

    @property
    def model_name(self) -> str:
        return self.client.model
