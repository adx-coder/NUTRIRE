"""Tests for service contracts and registry."""

from collections.abc import AsyncIterator, Sequence
from typing import Any

import pytest

from polyvoice.core.exceptions import ConfigurationError
from polyvoice.services.base import ChatMessage, LLMChunk, LLMService
from polyvoice.services.registry import ServiceRegistry


class MockLLM(LLMService):
    name = "mock"

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        yield LLMChunk(text=messages[-1].content, is_final=True)


async def test_llm_service_contract_streams_chunks() -> None:
    service = MockLLM()
    chunks = [
        chunk
        async for chunk in service.stream_chat([ChatMessage(role="user", content="hello")])
    ]

    assert chunks == [LLMChunk(text="hello", is_final=True)]


def test_service_registry_registers_and_retrieves() -> None:
    registry: ServiceRegistry[LLMService] = ServiceRegistry()

    registry.register("mock", MockLLM)

    assert registry.get("mock") is MockLLM
    assert registry.names() == ["mock"]


def test_service_registry_rejects_duplicates() -> None:
    registry: ServiceRegistry[LLMService] = ServiceRegistry()
    registry.register("mock", MockLLM)

    with pytest.raises(ConfigurationError):
        registry.register("mock", MockLLM)

