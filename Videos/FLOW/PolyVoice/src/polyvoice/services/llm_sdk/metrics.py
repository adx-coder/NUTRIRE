"""Lightweight LLM SDK metrics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LLMMetrics:
    """Tracks a small set of runtime counters."""

    requests: int = 0
    chunks: int = 0
    interruptions: int = 0

    def report(self) -> dict[str, int]:
        """Return metrics as a dict."""

        return {
            "requests": self.requests,
            "chunks": self.chunks,
            "interruptions": self.interruptions,
        }

    def reset(self) -> None:
        """Reset counters."""

        self.requests = 0
        self.chunks = 0
        self.interruptions = 0
