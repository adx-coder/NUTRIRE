"""Local model provider backed by registered model loaders."""

from __future__ import annotations

from collections.abc import AsyncIterator

import numpy as np

from polyvoice.services.tts_sdk.codecs import get_codec
from polyvoice.services.tts_sdk.model_loaders import BaseModelLoader, get_model_loader
from polyvoice.services.tts_sdk.models import AudioFormat, SDKTTSChunk, TTSRequest, VoiceInfo
from polyvoice.services.tts_sdk.providers.base import BaseTTSProvider
from polyvoice.services.tts_sdk.providers.registry import register_provider


@register_provider("local_model")
class LocalModelProvider(BaseTTSProvider):
    """Provider that delegates inference to a registered model loader."""

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.loader: BaseModelLoader | None = None
        self.codec = None

    @property
    def provider_name(self) -> str:
        return "local_model"

    @property
    def native_sample_rate(self) -> int:
        if self.loader is None:
            return int(self.config.get("sample_rate", 24_000))
        return self.loader.native_sample_rate

    async def initialize(self) -> None:
        loader_name = str(self.config.get("model_loader", "")).strip().lower()
        loader_cls = get_model_loader(loader_name)
        self.loader = loader_cls()
        await self.loader.load(self.config)

        codec_name = str(self.config.get("codec", "passthrough")).strip().lower()
        codec_cls = get_codec(codec_name)
        self.codec = codec_cls()
        await self.codec.load(self.config.get("codec_config", {}))

    async def synthesize(
        self,
        text: str,
        request: TTSRequest,
    ) -> AsyncIterator[SDKTTSChunk]:
        if self.loader is None or self.codec is None:
            raise RuntimeError("Provider not initialized")

        chunk_index = 0
        async for audio, sample_rate in self.loader.synthesize_stream(text, request):
            decoded = await self.codec.decode(audio)
            if len(decoded) == 0:
                continue
            if decoded.dtype != np.float32:
                decoded = decoded.astype(np.float32)
            yield SDKTTSChunk(
                audio=decoded,
                sample_rate=sample_rate,
                format=AudioFormat.F32,
                chunk_index=chunk_index,
                sentence_text=text,
            )
            chunk_index += 1

    async def shutdown(self) -> None:
        if self.loader is not None:
            await self.loader.unload()
            self.loader = None
        if self.codec is not None:
            await self.codec.unload()
            self.codec = None

    def get_voices(self) -> list[VoiceInfo]:
        if self.loader is None:
            return []
        return self.loader.get_voices()

