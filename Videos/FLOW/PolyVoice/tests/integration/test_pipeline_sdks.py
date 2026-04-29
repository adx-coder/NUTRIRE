"""Integration test for SDK-backed ASR -> LLM -> TTS runtime."""

from collections.abc import AsyncIterator, Sequence
from typing import Any

import numpy as np

from polyvoice.audio.frames import AudioFrame
from polyvoice.core.events import LLMChunkEvent, TTSAudioEvent, TranscriptEvent
from polyvoice.runtime.pipeline import VoicePipeline
from polyvoice.services.asr_sdk import ASRConfig, ASRRequest, ASRSegment, SDKSTTService
from polyvoice.services.asr_sdk.models import BaseASRModel, register_asr_model
from polyvoice.services.base import ChatMessage, LLMChunk
from polyvoice.services.llm_sdk import LLMConfig, SDKLLMService
from polyvoice.services.llm_sdk.clients import BaseLLMClient, register_llm_client
from polyvoice.services.tts_sdk import SDKTTSService, TTSConfig, TTSRequest
from polyvoice.services.tts_sdk.model_loaders import BaseModelLoader, register_model_loader
from polyvoice.services.tts_sdk.models import TTSCapability


@register_asr_model("pipeline_fake_asr")
class PipelineFakeASR(BaseASRModel):
    async def load(self, config: dict) -> None:
        del config

    async def transcribe_chunk(
        self,
        audio: bytes,
        *,
        timestamp: float,
        request: ASRRequest,
    ) -> Sequence[ASRSegment]:
        del audio, request
        return [
            ASRSegment(text="hello", is_final=False, confidence=0.8, start_time=timestamp),
            ASRSegment(text="hello pipeline", is_final=True, confidence=0.95, start_time=timestamp),
        ]

    @property
    def model_name(self) -> str:
        return "pipeline_fake_asr"


@register_llm_client("pipeline_fake_llm")
class PipelineFakeLLM(BaseLLMClient):
    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        del tools, temperature, max_tokens
        yield LLMChunk(text=f"SDK echo: {messages[-1].content}.", chunk_id=1)
        yield LLMChunk(text="", is_final=True, chunk_id=2)

    @property
    def model_name(self) -> str:
        return "pipeline_fake_llm"


@register_model_loader("pipeline_fake_tts")
class PipelineFakeTTS(BaseModelLoader):
    CAPABILITIES = {TTSCapability.BATCH}

    async def load(self, config: dict) -> None:
        del config

    async def synthesize(self, text: str, request: TTSRequest) -> tuple[np.ndarray, int]:
        del text, request
        return np.full(160, 0.25, dtype=np.float32), 16_000

    async def unload(self) -> None:
        pass

    @property
    def native_sample_rate(self) -> int:
        return 16_000

    @property
    def loader_name(self) -> str:
        return "pipeline_fake_tts"


async def test_pipeline_runs_through_all_three_sdks() -> None:
    pipeline = VoicePipeline(
        stt=SDKSTTService(
            config=ASRConfig(
                models=[{"model_loader": "pipeline_fake_asr", "name": "asr"}]
            ),
            model="asr",
        ),
        llm=SDKLLMService(
            config=LLMConfig(
                clients=[{"client": "pipeline_fake_llm", "name": "llm"}]
            ),
            client="llm",
        ),
        tts=SDKTTSService(
            config=TTSConfig(
                providers=[
                    {
                        "provider": "local_model",
                        "model_loader": "pipeline_fake_tts",
                        "name": "tts",
                    }
                ]
            ),
            provider="tts",
            output_sample_rate=16_000,
        ),
    )
    await pipeline.start()

    events = [
        event
        async for event in pipeline.process_audio_frame(
            "session-1",
            AudioFrame(audio=b"\x01\x02", sample_rate=16_000),
        )
    ]
    await pipeline.stop()

    assert any(isinstance(event, TranscriptEvent) and event.text == "hello pipeline" for event in events)
    assert any(isinstance(event, LLMChunkEvent) and "SDK echo" in event.text for event in events)
    assert any(isinstance(event, TTSAudioEvent) and event.audio for event in events)
