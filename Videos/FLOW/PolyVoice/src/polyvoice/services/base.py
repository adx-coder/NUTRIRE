"""Abstract service contracts for ASR, LLM, and TTS plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class STTResult:
    """One speech-to-text result from an STT service."""

    text: str
    is_final: bool
    confidence: float | None = None
    start_time: float | None = None
    end_time: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One chat message for LLM services."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None


@dataclass(frozen=True, slots=True)
class LLMChunk:
    """One streamed LLM output chunk."""

    text: str
    is_final: bool = False
    chunk_id: str | int | None = None
    is_sentence_boundary: bool = False
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TTSChunk:
    """One synthesized audio chunk."""

    audio: bytes
    sample_rate: int
    format: Literal["pcm16", "wav", "mulaw", "alaw", "opus"] = "pcm16"
    chunk_index: int | None = None
    is_final: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class STTService(ABC):
    """Contract implemented by ASR services."""

    name: str
    sample_rate: int = 16_000

    async def start(self) -> None:
        """Load resources needed by this service."""

    async def stop(self) -> None:
        """Release resources owned by this service."""

    @abstractmethod
    async def transcribe_stream(
        self,
        audio: AsyncIterator[bytes],
        *,
        sample_rate: int = 16_000,
        language: str | None = None,
    ) -> AsyncIterator[STTResult]:
        """Transcribe an audio stream into partial and final text."""


class LLMService(ABC):
    """Contract implemented by LLM services."""

    name: str

    async def start(self) -> None:
        """Open resources needed by this service."""

    async def stop(self) -> None:
        """Close resources owned by this service."""

    @abstractmethod
    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream an assistant response for the supplied messages."""


class TTSService(ABC):
    """Contract implemented by text-to-speech services."""

    name: str
    sample_rate: int

    async def start(self) -> None:
        """Load resources needed by this service."""

    async def stop(self) -> None:
        """Release resources owned by this service."""

    @abstractmethod
    async def synthesize_stream(
        self,
        text: AsyncIterator[str],
        *,
        voice: str | None = None,
        language: str | None = None,
    ) -> AsyncIterator[TTSChunk]:
        """Synthesize a text stream into audio chunks."""

