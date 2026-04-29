"""Base VAD contract."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseVAD(ABC):
    """Implemented by voice activity detectors."""

    def __init__(self, config: dict) -> None:
        self.config = config

    async def load(self, config: dict) -> None:
        """Load VAD resources."""

    @abstractmethod
    async def is_speech(self, audio: bytes, *, sample_rate: int) -> bool:
        """Return whether this chunk contains speech."""

    async def reset(self) -> None:
        """Reset streaming state."""

    async def unload(self) -> None:
        """Release resources."""
