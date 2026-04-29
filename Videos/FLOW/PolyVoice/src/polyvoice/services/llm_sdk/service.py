"""PolyVoice LLMService adapter for the LLM SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

from polyvoice.services.base import ChatMessage, LLMChunk, LLMService
from polyvoice.services.llm_sdk.config import LLMConfig
from polyvoice.services.llm_sdk.sdk import LLMStreamingSDK


class SDKLLMService(LLMService):
    """Wrap LLMStreamingSDK in the runtime LLMService contract."""

    name = "llm-sdk"

    def __init__(
        self,
        *,
        config: LLMConfig | None = None,
        client: str,
        model_name: str | None = None,
        sdk: LLMStreamingSDK | None = None,
    ) -> None:
        self.config = config or LLMConfig()
        self.client = client
        self.model = model_name or client
        self.sdk = sdk or LLMStreamingSDK()

    async def start(self) -> None:
        """Initialize the SDK."""

        await self.sdk.initialize(self.config)

    async def stop(self) -> None:
        """Shutdown the SDK."""

        await self.sdk.shutdown()

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream a response through the SDK."""

        user_input = messages[-1].content if messages else ""
        async for chunk in self.sdk.generate_response(
            user_input,
            client=self.client,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk
