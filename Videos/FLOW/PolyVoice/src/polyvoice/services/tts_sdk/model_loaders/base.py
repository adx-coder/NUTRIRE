"""Base model loader interface for local TTS models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import numpy as np

from polyvoice.services.tts_sdk.models import TTSCapability, TTSRequest, VoiceInfo


class BaseModelLoader(ABC):
    """Model-specific local inference contract."""

    CAPABILITIES: set[TTSCapability] = set()

    @abstractmethod
    async def load(self, config: dict) -> None:
        """Load model resources."""

    @abstractmethod
    async def synthesize(self, text: str, request: TTSRequest) -> tuple[np.ndarray, int]:
        """Return one complete audio array plus sample rate."""

    async def synthesize_stream(
        self,
        text: str,
        request: TTSRequest,
    ) -> AsyncIterator[tuple[np.ndarray, int]]:
        """Yield streaming audio chunks. Defaults to one complete chunk."""

        yield await self.synthesize(text, request)

    @abstractmethod
    async def unload(self) -> None:
        """Release model resources."""

    @property
    @abstractmethod
    def native_sample_rate(self) -> int:
        """Native model sample rate."""

    @property
    @abstractmethod
    def loader_name(self) -> str:
        """Registered loader name."""

    def get_voices(self) -> list[VoiceInfo]:
        """Return available voices."""

        return []

