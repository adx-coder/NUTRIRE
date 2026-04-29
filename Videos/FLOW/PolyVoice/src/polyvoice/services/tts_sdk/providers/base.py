"""Base provider contract for the PolyVoice TTS SDK."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from polyvoice.services.tts_sdk.models import SDKTTSChunk, TTSCapability, TTSRequest, VoiceInfo


class BaseTTSProvider(ABC):
    """Provider contract: initialize, synthesize, shutdown."""

    CAPABILITIES: set[TTSCapability] = set()

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider name."""

    @property
    @abstractmethod
    def native_sample_rate(self) -> int:
        """Native provider sample rate."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize provider resources."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        request: TTSRequest,
    ) -> AsyncIterator[SDKTTSChunk]:
        """Synthesize one text segment."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Release provider resources."""

    def get_voices(self) -> list[VoiceInfo]:
        """Return available voices."""

        return []

