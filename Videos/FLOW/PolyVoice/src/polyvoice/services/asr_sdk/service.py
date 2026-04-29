"""PolyVoice STTService adapter for the ASR SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator

from polyvoice.services.asr_sdk.config import ASRConfig
from polyvoice.services.asr_sdk.sdk import StreamingASRSDK
from polyvoice.services.asr_sdk.types import ASRRequest
from polyvoice.services.base import STTResult, STTService


class SDKSTTService(STTService):
    """Wrap StreamingASRSDK in the runtime STTService contract."""

    name = "asr-sdk"

    def __init__(
        self,
        *,
        config: ASRConfig | None = None,
        model: str,
        sample_rate: int = 16_000,
        sdk: StreamingASRSDK | None = None,
    ) -> None:
        self.config = config or ASRConfig()
        self.model = model
        self.sample_rate = sample_rate
        self.sdk = sdk or StreamingASRSDK()

    async def start(self) -> None:
        """Initialize the SDK."""

        await self.sdk.initialize(self.config)

    async def stop(self) -> None:
        """Shutdown the SDK."""

        await self.sdk.shutdown()

    async def transcribe_stream(
        self,
        audio: AsyncIterator[bytes],
        *,
        sample_rate: int = 16_000,
        language: str | None = None,
    ) -> AsyncIterator[STTResult]:
        """Transcribe audio through the SDK."""

        request = ASRRequest(
            model=self.model,
            sample_rate=sample_rate or self.sample_rate,
            language=language,
        )
        async for segment in self.sdk.transcribe_stream(audio, request=request):
            yield STTResult(
                text=segment.text,
                is_final=segment.is_final,
                confidence=segment.confidence,
                start_time=segment.start_time,
                end_time=segment.end_time,
                metadata=segment.metadata,
            )
