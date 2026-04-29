"""FLOW-style ASR streaming processor boundary."""

from __future__ import annotations

from collections.abc import Sequence

from polyvoice.services.asr_sdk.models.base import BaseASRModel
from polyvoice.services.asr_sdk.types import ASRRequest, ASRSegment
from polyvoice.services.asr_sdk.vad.base import BaseVAD


class StreamingASRProcessor:
    """Coordinates VAD, ASR model calls, and confidence filtering."""

    def __init__(
        self,
        model: BaseASRModel,
        *,
        vad: BaseVAD | None = None,
        min_partial_confidence: float = 0.0,
        min_final_confidence: float = 0.0,
    ) -> None:
        self.model = model
        self.vad = vad
        self.min_partial_confidence = min_partial_confidence
        self.min_final_confidence = min_final_confidence

    async def process_stream_chunk(
        self,
        chunk: bytes,
        *,
        timestamp: float,
        request: ASRRequest,
    ) -> Sequence[ASRSegment]:
        """Process one audio chunk."""

        if self.vad is not None:
            has_speech = await self.vad.is_speech(chunk, sample_rate=request.sample_rate)
            if not has_speech:
                return []

        segments = await self.model.transcribe_chunk(chunk, timestamp=timestamp, request=request)
        return [
            segment
            for segment in segments
            if self._meets_confidence(segment)
        ]

    async def reset(self) -> None:
        """Reset processor-owned state."""

        await self.model.reset()
        if self.vad is not None:
            await self.vad.reset()

    def _meets_confidence(self, segment: ASRSegment) -> bool:
        confidence = 1.0 if segment.confidence is None else segment.confidence
        threshold = self.min_final_confidence if segment.is_final else self.min_partial_confidence
        return confidence >= threshold
