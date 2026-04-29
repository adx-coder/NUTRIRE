"""FLOW-style streaming TTS SDK for PolyVoice."""

from __future__ import annotations

from collections.abc import AsyncIterator

from polyvoice.core.exceptions import ServiceError
from polyvoice.services.tts_sdk.config import TTSConfig
from polyvoice.services.tts_sdk.models import SDKTTSChunk, TTSRequest, VoiceInfo
from polyvoice.services.tts_sdk.pipeline import AudioPipeline, TextPipeline
from polyvoice.services.tts_sdk.providers import BaseTTSProvider, get_provider


class StreamingTTSSDK:
    """Provider-pattern TTS SDK preserving the FLOW extension model."""

    def __init__(self) -> None:
        self.providers: dict[str, BaseTTSProvider] = {}
        self.text_pipeline = TextPipeline()
        self.audio_pipeline = AudioPipeline()
        self.initialized = False

    async def initialize(self, config: TTSConfig | None = None) -> None:
        """Initialize configured providers."""

        cfg = config or TTSConfig()
        text_cfg = cfg.text_pipeline
        self.text_pipeline = TextPipeline(
            min_sentence_length=int(text_cfg.get("min_sentence_length", 10)),
            max_sentence_length=int(text_cfg.get("max_sentence_length", 500)),
        )
        self.audio_pipeline = AudioPipeline()

        errors: list[str] = []
        for provider_cfg in cfg.providers:
            provider_type = str(provider_cfg.get("provider", "local_model"))
            name = str(
                provider_cfg.get("name")
                or provider_cfg.get("model_loader")
                or provider_type
            )
            try:
                provider_cls = get_provider(provider_type)
                provider = provider_cls(provider_cfg)
                await provider.initialize()
                self.providers[name] = provider
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        self.initialized = True
        if errors and not self.providers:
            raise ServiceError(f"All TTS SDK providers failed: {errors}")

    async def add_provider(self, name: str, provider: BaseTTSProvider) -> None:
        """Add a pre-initialized provider."""

        self.providers[name] = provider
        self.initialized = True

    async def synthesize(self, request: TTSRequest) -> AsyncIterator[SDKTTSChunk]:
        """Synthesize text to audio through the selected provider."""

        self._check_initialized()
        provider = self._get_provider(request.provider)
        sentences = self.text_pipeline.process(request.text)
        chunk_index = 0
        for sentence_index, sentence in enumerate(sentences):
            is_last = sentence_index == len(sentences) - 1
            async for chunk in provider.synthesize(sentence, request):
                processed = self.audio_pipeline.process_chunk(chunk, request)
                processed.chunk_index = chunk_index
                processed.sentence_text = sentence
                processed.is_segment_end = is_last
                chunk_index += 1
                yield processed

    async def shutdown(self) -> None:
        """Shutdown all providers."""

        for provider in self.providers.values():
            await provider.shutdown()
        self.providers.clear()
        self.initialized = False

    @property
    def available_providers(self) -> list[str]:
        """Return loaded provider names."""

        return sorted(self.providers)

    def get_voices(self, provider_name: str | None = None) -> list[VoiceInfo]:
        """Return voices across providers or one provider."""

        voices: list[VoiceInfo] = []
        for name, provider in self.providers.items():
            if provider_name is not None and provider_name != name:
                continue
            voices.extend(provider.get_voices())
        return voices

    def _check_initialized(self) -> None:
        if not self.initialized:
            raise ServiceError("TTS SDK is not initialized")

    def _get_provider(self, name: str) -> BaseTTSProvider:
        try:
            return self.providers[name]
        except KeyError as exc:
            available = ", ".join(sorted(self.providers)) or "(none)"
            raise ServiceError(f"TTS provider '{name}' not loaded. Available: {available}") from exc

