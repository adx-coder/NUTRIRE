"""ASR-to-LLM turn coordination."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class RequestPriority(IntEnum):
    """Priority levels matching the old FLOW LLM SDK."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass(frozen=True, slots=True)
class TurnDecision:
    """Decision produced from one ASR transcript event."""

    should_respond: bool
    text: str
    priority: int = int(RequestPriority.NORMAL)
    reason: str | None = None


class TurnCoordinator:
    """Decides when an ASR transcript should trigger an LLM turn."""

    def __init__(
        self,
        *,
        min_confidence: float = 0.0,
        enable_partial_preparation: bool = True,
    ) -> None:
        self.min_confidence = min_confidence
        self.enable_partial_preparation = enable_partial_preparation
        self.last_partial_text: str | None = None

    def process_asr_transcript(
        self,
        transcript: str,
        *,
        is_final: bool = True,
        confidence: float | None = None,
        priority: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> TurnDecision:
        """Return whether the transcript should become a user turn."""

        text = transcript.strip()
        if not is_final:
            if self.enable_partial_preparation:
                self.last_partial_text = text
            return TurnDecision(
                should_respond=False,
                text=text,
                priority=priority or int(RequestPriority.LOW),
                reason="partial",
            )

        passes_confidence = confidence is None or confidence >= self.min_confidence
        if not passes_confidence:
            return TurnDecision(
                should_respond=False,
                text=text,
                priority=priority or int(RequestPriority.LOW),
                reason="low_confidence",
            )

        return TurnDecision(
            should_respond=bool(text),
            text=text,
            priority=priority or int(self._determine_priority(metadata or {})),
            reason=None if text else "empty",
        )

    def handle_interruption(self) -> TurnDecision:
        """Return an urgent decision marker for barge-in handling."""

        return TurnDecision(
            should_respond=False,
            text="",
            priority=int(RequestPriority.URGENT),
            reason="interruption",
        )

    def _determine_priority(self, metadata: dict[str, Any]) -> RequestPriority:
        if metadata.get("is_interruption"):
            return RequestPriority.URGENT
        if metadata.get("is_command"):
            return RequestPriority.HIGH
        return RequestPriority.NORMAL
