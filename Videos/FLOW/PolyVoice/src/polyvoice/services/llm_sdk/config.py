"""Configuration for the PolyVoice LLM SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LLMConfig:
    """Configuration for clients and response processing."""

    clients: list[dict[str, Any]] = field(default_factory=list)
    response_processing: dict[str, Any] = field(default_factory=dict)
    conversation: dict[str, Any] = field(default_factory=dict)
    turn_coordinator: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    log_level: str = "INFO"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LLMConfig:
        """Create config from a mapping."""

        return cls(
            clients=list(data.get("clients", [])),
            response_processing=dict(data.get("response_processing", {})),
            conversation=dict(data.get("conversation", {})),
            turn_coordinator=dict(data.get("turn_coordinator", {})),
            metrics=dict(data.get("metrics", {})),
            log_level=str(data.get("log_level", "INFO")),
        )
