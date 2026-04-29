"""PolyVoice TTSService wrapper around StreamingTTSSDK."""

from __future__ import annotations

from collections.abc import AsyncIterator

import numpy as np

from polyvoice.audio.codecs import float32_to_pcm16_bytes
from polyvoice.services.base import TTSChunk, TTSService
from polyvoice.services.tts_sdk.config import TTSConfig
from polyvoice.services.tts_sdk.models import AudioFormat, TTSRequest
from polyvoice.services.tts_sdk.sdk import StreamingTTSSDK


class SDKTTSService(TTSService):
    """PolyVoice service adapter for the FLOW-style TTS SDK."""

    name = "tts-sdk"

    def __init__(
        self,
        *,
        config: TTSConfig,
        provider: str,
        voice: str | None = None,
        speed: float = 1.0,
        output_sample_rate: int = 24_000,
        sdk: StreamingTTSSDK | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.voice = voice
        self.speed = speed
        self.sample_rate = output_sample_rate
        self.sdk = sdk or StreamingTTSSDK()

    async def start(self) -> None:
        """Initialize SDK providers."""

        await self.sdk.initialize(self.config)

    async def stop(self) -> None:
        """Shutdown SDK providers."""

        await self.sdk.shutdown()

    async def synthesize_stream(
        self,
        text: AsyncIterator[str],
        *,
        voice: str | None = None,
        language: str | None = None,
    ) -> AsyncIterator[TTSChunk]:
        """Synthesize a text stream into PolyVoice TTS chunks."""

        index = 0
        async for text_chunk in text:
            request = TTSRequest(
                text=text_chunk,
                provider=self.provider,
                voice=voice or self.voice,
                language=language,
                speed=self.speed,
                output_sample_rate=self.sample_rate,
                output_format=AudioFormat.PCM_BYTES,
            )
            async for chunk in self.sdk.synthesize(request):
                index += 1
                audio = chunk.audio
                if isinstance(audio, np.ndarray):
                    if audio.dtype == np.float32:
                        audio_bytes = float32_to_pcm16_bytes(audio)
                    else:
                        audio_bytes = audio.astype("<i2").tobytes()
                else:
                    audio_bytes = audio
                yield TTSChunk(
                    audio=audio_bytes,
                    sample_rate=chunk.sample_rate,
                    format="pcm16" if chunk.format != AudioFormat.WAV else "wav",
                    chunk_index=index,
                    is_final=chunk.is_final,
                    metadata=dict(chunk.metadata),
                )
