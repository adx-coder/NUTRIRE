"""Configuration for the PolyVoice TTS SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TTSConfig:
    """Configuration for SDK providers and processing pipelines."""

    providers: list[dict[str, Any]] = field(default_factory=list)
    text_pipeline: dict[str, Any] = field(default_factory=dict)
    audio_pipeline: dict[str, Any] = field(default_factory=dict)
    log_level: str = "INFO"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TTSConfig:
        """Create config from a mapping."""

        return cls(
            providers=list(data.get("providers", [])),
            text_pipeline=dict(data.get("text_pipeline", {})),
            audio_pipeline=dict(data.get("audio_pipeline", {})),
            log_level=str(data.get("log_level", "INFO")),
        )

