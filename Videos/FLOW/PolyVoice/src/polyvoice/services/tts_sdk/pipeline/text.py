"""Small text normalization/splitting pipeline."""

from __future__ import annotations

import re


class TextPipeline:
    """Normalize text and split into synthesizeable segments."""

    def __init__(self, *, min_sentence_length: int = 10, max_sentence_length: int = 500) -> None:
        self.min_sentence_length = min_sentence_length
        self.max_sentence_length = max_sentence_length

    def process(self, text: str) -> list[str]:
        """Return non-empty sentence-ish chunks."""

        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            return []
        parts = re.split(r"(?<=[.!?])\s+", normalized)
        chunks: list[str] = []
        current = ""
        for part in parts:
            candidate = f"{current} {part}".strip() if current else part
            if len(candidate) < self.min_sentence_length:
                current = candidate
                continue
            while len(candidate) > self.max_sentence_length:
                chunks.append(candidate[: self.max_sentence_length].strip())
                candidate = candidate[self.max_sentence_length :].strip()
            chunks.append(candidate)
            current = ""
        if current:
            chunks.append(current)
        return chunks

