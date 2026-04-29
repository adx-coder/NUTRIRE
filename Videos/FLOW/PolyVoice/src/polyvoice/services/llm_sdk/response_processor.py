"""LLM response processing from the old SDK shape."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

from polyvoice.services.base import LLMChunk


class StatefulSentenceDetector:
    """Stateful sentence boundary detection with abbreviation handling."""

    ABBREVIATIONS = {
        "dr",
        "mr",
        "mrs",
        "ms",
        "prof",
        "sr",
        "jr",
        "st",
        "ave",
        "inc",
        "ltd",
        "co",
        "vs",
        "est",
        "etc",
        "approx",
        "dept",
        "fig",
        "vol",
        "ed",
        "gen",
        "gov",
        "hon",
        "rev",
    }

    def __init__(self) -> None:
        self.buffer = ""

    def process_token(self, token: str) -> list[str]:
        """Process incoming text and return complete sentences."""

        self.buffer += token
        sentences: list[str] = []
        pattern = r'(?<!\.)([.!?]+)["\'\s]*(?=\s+[A-Z]|\s*$)'
        matches = list(re.finditer(pattern, self.buffer))
        last_end_pos = 0
        for match in matches:
            sentence_end = match.end()
            candidate = self.buffer[last_end_pos:sentence_end].strip()
            if self._is_abbreviation(candidate):
                continue
            if candidate:
                sentences.append(candidate)
                last_end_pos = sentence_end
        remainder = self.buffer[last_end_pos:]
        if sentences and remainder and not remainder[0].isspace():
            remainder = " " + remainder
        self.buffer = remainder
        return sentences

    def flush(self) -> str:
        """Return and clear remaining buffered text."""

        remaining = self.buffer.strip()
        self.buffer = ""
        return remaining

    def reset(self) -> None:
        """Reset detector state."""

        self.buffer = ""

    def _is_abbreviation(self, text: str) -> bool:
        words = text.split()
        if not words:
            return False
        return words[-1].lower().rstrip(".!?") in self.ABBREVIATIONS


class ThinkingTagFilter:
    """Stateful filter for reasoning model thinking blocks."""

    def __init__(self) -> None:
        self.in_thinking_block = False
        self.partial_tag_buffer = ""

    def filter_content(self, content: str) -> str:
        """Filter thinking tags from streamed content."""

        if not content:
            return ""

        content = self.partial_tag_buffer + content
        self.partial_tag_buffer = ""
        last_open = content.rfind("<")
        last_close = content.rfind(">")
        if last_open > last_close:
            self.partial_tag_buffer = content[last_open:]
            content = content[:last_open]

        result: list[str] = []
        i = 0
        while i < len(content):
            lowered = content[i:].lower()
            if not self.in_thinking_block and lowered.startswith("<think>"):
                self.in_thinking_block = True
                i += 7
                continue
            if self.in_thinking_block:
                if lowered.startswith("</think>"):
                    self.in_thinking_block = False
                    i += 8
                    continue
                i += 1
                continue
            result.append(content[i])
            i += 1
        return "".join(result)

    def reset(self) -> None:
        """Reset filter state."""

        self.in_thinking_block = False
        self.partial_tag_buffer = ""


class ResponseProcessor:
    """Filters and chunks streamed response text."""

    def __init__(
        self,
        *,
        chunk_size_tokens: int = 8,
        enable_sentence_detection: bool = True,
        enable_thinking_filter: bool = True,
        enable_adaptive_chunking: bool = True,
    ) -> None:
        self.chunk_size_tokens = chunk_size_tokens
        self.current_chunk_size = chunk_size_tokens
        self.enable_sentence_detection = enable_sentence_detection
        self.enable_thinking_filter = enable_thinking_filter
        self.enable_adaptive_chunking = enable_adaptive_chunking
        self.sentence_detector = (
            StatefulSentenceDetector() if enable_sentence_detection else None
        )
        self.thinking_filter = ThinkingTagFilter() if enable_thinking_filter else None
        self.token_buffer: list[str] = []
        self.chunk_id = 0

    async def process_chunk(self, chunk: LLMChunk) -> AsyncIterator[LLMChunk]:
        """Process one raw LLM chunk into one or more output chunks."""

        if chunk.is_final:
            async for flushed in self.flush(metadata=chunk.metadata):
                yield flushed
            yield LLMChunk(
                text="",
                is_final=True,
                chunk_id=chunk.chunk_id,
                tool_calls=chunk.tool_calls,
                metadata=chunk.metadata,
            )
            return

        async for processed in self.process_token(
            chunk.text,
            chunk_id=chunk.chunk_id,
            tool_calls=chunk.tool_calls,
            metadata=chunk.metadata,
        ):
            yield processed

    async def process_token(
        self,
        token: str,
        *,
        chunk_id: str | int | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Process a single token or text fragment."""

        filtered = token
        if self.thinking_filter:
            filtered = self.thinking_filter.filter_content(filtered)
        if not filtered:
            return

        self.token_buffer.append(filtered)
        if self.sentence_detector:
            sentences = self.sentence_detector.process_token(filtered)
            for sentence in sentences:
                self.chunk_id += 1
                yield LLMChunk(
                    text=sentence,
                    chunk_id=chunk_id or self.chunk_id,
                    is_sentence_boundary=True,
                    tool_calls=tool_calls or [],
                    metadata={**(metadata or {}), "word_count": len(sentence.split())},
                )
            self.token_buffer.clear()
        elif len(self.token_buffer) >= self.current_chunk_size:
            self.chunk_id += 1
            chunk_text = "".join(self.token_buffer)
            yield LLMChunk(
                text=chunk_text,
                chunk_id=chunk_id or self.chunk_id,
                is_sentence_boundary=False,
                tool_calls=tool_calls or [],
                metadata={**(metadata or {}), "word_count": len(chunk_text.split())},
            )
            self.token_buffer.clear()

    async def flush(self, *, metadata: dict[str, Any] | None = None) -> AsyncIterator[LLMChunk]:
        """Flush remaining buffered text."""

        if self.sentence_detector:
            remaining = self.sentence_detector.flush()
            if remaining:
                self.chunk_id += 1
                yield LLMChunk(
                    text=remaining,
                    chunk_id=self.chunk_id,
                    is_sentence_boundary=True,
                    metadata={**(metadata or {}), "word_count": len(remaining.split())},
                )
        elif self.token_buffer:
            self.chunk_id += 1
            chunk_text = "".join(self.token_buffer)
            yield LLMChunk(
                text=chunk_text,
                chunk_id=self.chunk_id,
                is_sentence_boundary=False,
                metadata={**(metadata or {}), "word_count": len(chunk_text.split())},
            )
            self.token_buffer.clear()

    def adjust_chunk_size(self, new_size: int) -> None:
        """Dynamically adjust chunk size."""

        if not self.enable_adaptive_chunking:
            return
        self.current_chunk_size = min(30, max(1, new_size))

    def reset(self) -> None:
        """Reset processor state."""

        self.token_buffer.clear()
        self.chunk_id = 0
        self.current_chunk_size = self.chunk_size_tokens
        if self.sentence_detector:
            self.sentence_detector.reset()
        if self.thinking_filter:
            self.thinking_filter.reset()
