"""FLOW-style streaming ASR SDK for PolyVoice."""

from __future__ import annotations

from collections.abc import AsyncIterator

from polyvoice.core.exceptions import ServiceError
from polyvoice.services.asr_sdk.config import ASRConfig
from polyvoice.services.asr_sdk.models import get_asr_model
from polyvoice.services.asr_sdk.models.base import BaseASRModel
from polyvoice.services.asr_sdk.processing import StreamingASRProcessor
from polyvoice.services.asr_sdk.types import ASRRequest, ASRSegment
from polyvoice.services.asr_sdk.vad import get_vad
from polyvoice.services.asr_sdk.vad.base import BaseVAD


class StreamingASRSDK:
    """Model/VAD-pattern ASR SDK preserving the FLOW extension model."""

    def __init__(self) -> None:
        self.models: dict[str, BaseASRModel] = {}
        self.processors: dict[str, StreamingASRProcessor] = {}
        self.vad: BaseVAD | None = None
        self.initialized = False

    async def initialize(self, config: ASRConfig | None = None) -> None:
        """Initialize configured models and optional VAD."""

        cfg = config or ASRConfig()
        if cfg.vad:
            vad_type = str(cfg.vad.get("provider", cfg.vad.get("type", "energy")))
            vad_cls = get_vad(vad_type)
            self.vad = vad_cls(cfg.vad)
            await self.vad.load(cfg.vad)

        errors: list[str] = []
        for model_cfg in cfg.models:
            loader = str(model_cfg.get("model_loader") or model_cfg.get("backend") or model_cfg.get("name"))
            name = str(model_cfg.get("name") or loader)
            try:
                model_cls = get_asr_model(loader)
                model = model_cls(model_cfg)
                await model.load(model_cfg)
                self.models[name] = model
                self.processors[name] = StreamingASRProcessor(
                    model,
                    vad=self.vad,
                    min_partial_confidence=float(
                        cfg.processing.get("min_partial_confidence", 0.0)
                    ),
                    min_final_confidence=float(
                        cfg.processing.get("min_finalization_confidence", 0.0)
                    ),
                )
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        self.initialized = True
        if errors and not self.models:
            raise ServiceError(f"All ASR SDK models failed: {errors}")

    async def add_model(self, name: str, model: BaseASRModel) -> None:
        """Add a pre-initialized ASR model."""

        self.models[name] = model
        self.processors[name] = StreamingASRProcessor(model, vad=self.vad)
        self.initialized = True

    async def process_stream_chunk(
        self,
        chunk: bytes,
        *,
        timestamp: float,
        request: ASRRequest,
    ) -> list[ASRSegment]:
        """Process one stream chunk through the selected model."""

        self._check_initialized()
        processor = self._get_processor(request.model)
        return list(
            await processor.process_stream_chunk(
                chunk,
                timestamp=timestamp,
                request=request,
            )
        )

    async def transcribe_stream(
        self,
        audio: AsyncIterator[bytes],
        *,
        request: ASRRequest,
    ) -> AsyncIterator[ASRSegment]:
        """Transcribe an async audio stream."""

        timestamp = 0.0
        bytes_per_second = max(1, request.sample_rate * 2)
        async for chunk in audio:
            for segment in await self.process_stream_chunk(
                chunk,
                timestamp=timestamp,
                request=request,
            ):
                yield segment
            timestamp += len(chunk) / bytes_per_second

    async def reset(self) -> None:
        """Reset all processors."""

        for processor in self.processors.values():
            await processor.reset()

    async def shutdown(self) -> None:
        """Shutdown all models and VAD."""

        for model in self.models.values():
            await model.unload()
        if self.vad is not None:
            await self.vad.unload()
        self.models.clear()
        self.processors.clear()
        self.vad = None
        self.initialized = False

    @property
    def available_models(self) -> list[str]:
        """Return loaded model names."""

        return sorted(self.models)

    def _check_initialized(self) -> None:
        if not self.initialized:
            raise ServiceError("ASR SDK is not initialized")

    def _get_processor(self, name: str) -> StreamingASRProcessor:
        try:
            return self.processors[name]
        except KeyError as exc:
            available = ", ".join(sorted(self.processors)) or "(none)"
            raise ServiceError(f"ASR model '{name}' not loaded. Available: {available}") from exc
