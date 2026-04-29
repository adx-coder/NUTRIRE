"""Golden tests for SDK-first model extension contracts."""

from collections.abc import AsyncIterator, Sequence
from typing import Any, ClassVar

import numpy as np

from polyvoice.services.asr_sdk import ASRConfig, ASRRequest, ASRSegment, StreamingASRSDK
from polyvoice.services.asr_sdk.models import BaseASRModel, list_asr_models, register_asr_model
from polyvoice.services.asr_sdk.vad import BaseVAD, list_vads, register_vad
from polyvoice.services.base import ChatMessage, LLMChunk
from polyvoice.services.llm_sdk import LLMConfig, LLMStreamingSDK
from polyvoice.services.llm_sdk.clients import (
    BaseLLMClient,
    list_llm_clients,
    register_llm_client,
)
from polyvoice.services.tts_sdk import StreamingTTSSDK, TTSConfig, TTSRequest
from polyvoice.services.tts_sdk.model_loaders import (
    BaseModelLoader,
    list_model_loaders,
    register_model_loader,
)
from polyvoice.services.tts_sdk.models import TTSCapability


@register_asr_model("contract_asr")
class ContractASRModel(BaseASRModel):
    """Tiny ASR extension used to lock the registry contract."""

    async def load(self, config: dict) -> None:
        self.loaded_config = config

    async def transcribe_chunk(
        self,
        audio: bytes,
        *,
        timestamp: float,
        request: ASRRequest,
    ) -> Sequence[ASRSegment]:
        del request
        if not audio:
            return []
        return [
            ASRSegment(
                text=f"contract-asr-{len(audio)}",
                is_final=True,
                confidence=0.99,
                start_time=timestamp,
            )
        ]

    @property
    def model_name(self) -> str:
        return "contract_asr"


@register_vad("contract_vad")
class ContractVAD(BaseVAD):
    """Tiny VAD extension used to lock the registry contract."""

    async def load(self, config: dict) -> None:
        self.loaded_config = config

    async def is_speech(self, audio: bytes, *, sample_rate: int) -> bool:
        del sample_rate
        return bool(audio)


@register_llm_client("contract_llm")
class ContractLLMClient(BaseLLMClient):
    """Tiny LLM extension used to lock the registry contract."""

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        del tools, temperature, max_tokens
        yield LLMChunk(text=f"contract-llm:{messages[-1].content}")
        yield LLMChunk(text="", is_final=True)

    @property
    def model_name(self) -> str:
        return "contract_llm"


@register_model_loader("contract_tts")
class ContractTTSLoader(BaseModelLoader):
    """Tiny TTS extension used to lock the registry contract."""

    CAPABILITIES: ClassVar[set[TTSCapability]] = {TTSCapability.BATCH}

    async def load(self, config: dict) -> None:
        self.loaded_config = config

    async def synthesize(self, text: str, request: TTSRequest) -> tuple[np.ndarray, int]:
        del request
        return np.full(80, min(len(text) / 100.0, 0.5), dtype=np.float32), 16_000

    async def unload(self) -> None:
        pass

    @property
    def native_sample_rate(self) -> int:
        return 16_000

    @property
    def loader_name(self) -> str:
        return "contract_tts"


def test_extension_registries_expose_registered_contract_entries() -> None:
    assert "contract_asr" in list_asr_models()
    assert "contract_vad" in list_vads()
    assert "contract_llm" in list_llm_clients()
    assert "contract_tts" in list_model_loaders()


async def test_asr_extension_loads_from_config_without_runtime_edits() -> None:
    sdk = StreamingASRSDK()
    await sdk.initialize(
        ASRConfig(
            models=[{"name": "demo_asr", "model_loader": "contract_asr"}],
            vad={"provider": "contract_vad"},
        )
    )

    async def audio_stream() -> AsyncIterator[bytes]:
        yield b"\x01\x02\x03"

    segments = [
        segment
        async for segment in sdk.transcribe_stream(
            audio_stream(),
            request=ASRRequest(model="demo_asr", sample_rate=16_000),
        )
    ]
    await sdk.shutdown()

    assert sdk.available_models == []
    assert [segment.text for segment in segments] == ["contract-asr-3"]


async def test_llm_extension_loads_from_config_without_runtime_edits() -> None:
    sdk = LLMStreamingSDK()
    await sdk.initialize(LLMConfig(clients=[{"name": "demo_llm", "client": "contract_llm"}]))

    chunks = [chunk async for chunk in sdk.generate_response("hello", client="demo_llm")]
    await sdk.shutdown()

    assert chunks[0].text == "contract-llm:hello"
    assert any(chunk.is_final for chunk in chunks)


async def test_tts_extension_loads_from_config_without_runtime_edits() -> None:
    sdk = StreamingTTSSDK()
    await sdk.initialize(
        TTSConfig(
            providers=[
                {
                    "name": "demo_tts",
                    "provider": "local_model",
                    "model_loader": "contract_tts",
                }
            ]
        )
    )

    chunks = [
        chunk
        async for chunk in sdk.synthesize(
            TTSRequest(
                text="hello",
                provider="demo_tts",
                output_sample_rate=16_000,
            )
        )
    ]
    await sdk.shutdown()

    assert len(chunks) == 1
    assert chunks[0].sample_rate == 16_000
    assert isinstance(chunks[0].audio, bytes)
