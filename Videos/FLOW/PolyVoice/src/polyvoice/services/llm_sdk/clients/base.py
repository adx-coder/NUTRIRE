"""Base LLM client contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from typing import Any

from polyvoice.services.base import ChatMessage, LLMChunk


class BaseLLMClient(ABC):
    """Implemented by concrete chat-completion clients."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    async def start(self) -> None:
        """Open client resources."""

    async def stop(self) -> None:
        """Close client resources."""

    @abstractmethod
    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream model output chunks."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the active model name."""
