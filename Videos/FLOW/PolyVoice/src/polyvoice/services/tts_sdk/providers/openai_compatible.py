"""SDK provider wrapper for the existing OpenAI-compatible TTS service."""

from __future__ import annotations

from collections.abc import AsyncIterator

from polyvoice.services.tts.openai_compat import OpenAICompatibleTTS
from polyvoice.services.tts_sdk.models import AudioFormat, SDKTTSChunk, TTSRequest
from polyvoice.services.tts_sdk.providers.base import BaseTTSProvider
from polyvoice.services.tts_sdk.providers.registry import register_provider


@register_provider("openai_compatible")
@register_provider("openai-compatible")
class OpenAICompatibleProvider(BaseTTSProvider):
    """Provider that calls an OpenAI-compatible speech endpoint."""

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        endpoint = str(self.config.get("endpoint") or self.config.get("endpoint_url") or "")
        if endpoint and not endpoint.endswith("/audio/speech"):
            endpoint = endpoint.rstrip("/") + "/v1/audio/speech"
        self.service = OpenAICompatibleTTS(
            endpoint_url=endpoint,
            model=str(self.config.get("model", "tts-1")),
            api_key=self.config.get("api_key"),
            voice=str(self.config.get("default_voice", self.config.get("voice", "alloy"))),
            response_format=self.config.get("response_format", "wav"),
            sample_rate=int(self.config.get("sample_rate", 24_000)),
            speed=float(self.config.get("speed", 1.0)),
            timeout_seconds=float(self.config.get("timeout_seconds", 30.0)),
            extra_body=self.config.get("extra_body", {}),
        )

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    @property
    def native_sample_rate(self) -> int:
        return self.service.sample_rate

    async def initialize(self) -> None:
        await self.service.start()

    async def synthesize(
        self,
        text: str,
        request: TTSRequest,
    ) -> AsyncIterator[SDKTTSChunk]:
        async def text_once():
            yield text

        async for chunk in self.service.synthesize_stream(
            text_once(),
            voice=request.voice,
            language=request.language,
        ):
            yield SDKTTSChunk(
                audio=chunk.audio,
                sample_rate=chunk.sample_rate,
                format=AudioFormat.WAV if chunk.format == "wav" else AudioFormat.PCM_BYTES,
                chunk_index=chunk.chunk_index or 0,
                is_final=chunk.is_final,
                sentence_text=text,
                metadata=chunk.metadata,
            )

    async def shutdown(self) -> None:
        await self.service.stop()

