"""Processor base class for event-driven PolyVoice pipeline stages."""

from __future__ import annotations

from abc import ABC, abstractmethod

from polyvoice.core.events import VoiceEvent


class Processor(ABC):
    """Base class for event-driven pipeline components.

    Processors receive a typed ``VoiceEvent`` and may return a transformed event,
    a new event, or ``None`` when the input is consumed.
    """

    def __init__(self, name: str | None = None) -> None:
        self.name = name or self.__class__.__name__
        self.started = False

    async def start(self) -> None:
        """Start resources owned by the processor."""

        self.started = True

    async def stop(self) -> None:
        """Release resources owned by the processor."""

        self.started = False

    @abstractmethod
    async def process(self, event: VoiceEvent) -> VoiceEvent | None:
        """Process one voice event."""

