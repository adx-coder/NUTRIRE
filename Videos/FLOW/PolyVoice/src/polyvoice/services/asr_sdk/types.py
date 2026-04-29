"""Shared ASR SDK data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ASRSegment:
    """One ASR segment emitted by the SDK."""

    text: str
    is_final: bool
    confidence: float | None = None
    start_time: float | None = None
    end_time: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ASRRequest:
    """Streaming ASR request metadata."""

    model: str
    sample_rate: int = 16_000
    language: str | None = None
