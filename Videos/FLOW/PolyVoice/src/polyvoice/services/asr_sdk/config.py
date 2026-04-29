"""Configuration for the PolyVoice ASR SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ASRConfig:
    """Configuration for ASR models, VAD, and streaming processing."""

    models: list[dict[str, Any]] = field(default_factory=list)
    vad: dict[str, Any] = field(default_factory=dict)
    processing: dict[str, Any] = field(default_factory=dict)
    log_level: str = "INFO"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ASRConfig:
        """Create config from a mapping."""

        return cls(
            models=list(data.get("models", [])),
            vad=dict(data.get("vad", {})),
            processing=dict(data.get("processing", {})),
            log_level=str(data.get("log_level", "INFO")),
        )
