"""In-process mock services for tests and local plumbing checks."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

from polyvoice.services.base import (
    ChatMessage,
    LLMChunk,
    LLMService,
    STTResult,
    STTService,
    TTSChunk,
    TTSService,
)


class MockSTTService(STTService):
    """Deterministic speech-to-text service for mock runtime tests."""

    name = "mock-stt"
    sample_rate = 16_000

    async def transcribe_stream(
        self,
        audio: AsyncIterator[bytes],
        *,
        sample_rate: int = 16_000,
        language: str | None = None,
    ) -> AsyncIterator[STTResult]:
        async for chunk in audio:
            if not chunk:
                continue
            yield STTResult(text="hello", is_final=False, confidence=0.5)
            yield STTResult(text="hello from mock audio", is_final=True, confidence=1.0)


class MockLLMService(LLMService):
    """Deterministic LLM service for mock runtime tests."""

    name = "mock-llm"

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        user_text = messages[-1].content if messages else ""
        yield LLMChunk(text=f"Echo: {user_text}", chunk_id=1)
        yield LLMChunk(text="", is_final=True, chunk_id=2)


class MockTTSService(TTSService):
    """Deterministic text-to-speech service for mock runtime tests."""

    name = "mock-tts"
    sample_rate = 16_000

    async def synthesize_stream(
        self,
        text: AsyncIterator[str],
        *,
        voice: str | None = None,
        language: str | None = None,
    ) -> AsyncIterator[TTSChunk]:
        index = 0
        async for chunk in text:
            if not chunk:
                continue
            index += 1
            yield TTSChunk(
                audio=b"RIFFmock-wave-bytes",
                sample_rate=self.sample_rate,
                format="wav",
                chunk_index=index,
                is_final=True,
            )

