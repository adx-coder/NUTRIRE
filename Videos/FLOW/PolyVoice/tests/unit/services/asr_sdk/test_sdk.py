"""Tests for FLOW-style ASR SDK skeleton."""

from collections.abc import Sequence
import builtins

import pytest

from polyvoice.config.legacy import legacy_to_polyvoice_config
from polyvoice.config.recipes import select_asr_recipe
from polyvoice.core.exceptions import ServiceError
from polyvoice.services.asr_sdk import ASRConfig, ASRRequest, ASRSegment, SDKSTTService
from polyvoice.services.asr_sdk.models import BaseASRModel, get_asr_model, register_asr_model
from polyvoice.services.asr_sdk.sdk import StreamingASRSDK
from polyvoice.services.asr_sdk.vad import get_vad


@register_asr_model("fake_asr")
class FakeASRModel(BaseASRModel):
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
                text="hello",
                is_final=False,
                confidence=0.6,
                start_time=timestamp,
            ),
            ASRSegment(
                text="hello from fake asr",
                is_final=True,
                confidence=0.95,
                start_time=timestamp,
            ),
        ]

    @property
    def model_name(self) -> str:
        return "fake_asr"


async def test_sdk_loads_registered_asr_model_without_core_changes() -> None:
    sdk = StreamingASRSDK()
    await sdk.initialize(
        ASRConfig(
            models=[
                {
                    "model_loader": "fake_asr",
                    "name": "fake",
                }
            ],
            vad={"provider": "energy"},
        )
    )

    async def audio_stream():
        yield b"\x01\x02"

    segments = [
        segment
        async for segment in sdk.transcribe_stream(
            audio_stream(),
            request=ASRRequest(model="fake", sample_rate=16_000),
        )
    ]
    await sdk.shutdown()

    assert [segment.text for segment in segments] == ["hello", "hello from fake asr"]
    assert segments[-1].is_final is True


async def test_sdk_stt_service_wraps_sdk_for_polyvoice_runtime() -> None:
    service = SDKSTTService(
        config=ASRConfig(
            models=[
                {
                    "model_loader": "fake_asr",
                    "name": "fake",
                }
            ]
        ),
        model="fake",
    )
    await service.start()

    async def audio_stream():
        yield b"\x01\x02"

    results = [result async for result in service.transcribe_stream(audio_stream())]
    await service.stop()

    assert results[-1].text == "hello from fake asr"
    assert results[-1].is_final is True


def test_select_asr_recipe_activates_sdk_config() -> None:
    config = legacy_to_polyvoice_config(
        {
            "asr": {
                "backend": "qwen3",
                "model_name": "Qwen/Qwen3-ASR",
                "sample_rate": 16_000,
                "enable_vad": True,
                "vad": {"type": "energy"},
                "qwen3": {"model_name": "Qwen/Qwen3-ASR", "sample_rate": 16_000},
            },
            "llm": {"backend": "mock"},
            "tts": {"backend": "mock"},
        }
    )

    selected = select_asr_recipe(config, "qwen3")

    assert selected.stt.provider == "asr-sdk"
    assert selected.stt.model == "qwen3"
    assert selected.stt.params["sdk_config"]["models"][0]["model_loader"] == "qwen3"
    assert selected.stt.params["sdk_config"]["vad"]["provider"] == "energy"


def test_real_asr_loader_names_are_registered_lazily() -> None:
    assert get_asr_model("qwen3").__name__ == "Qwen3ASRModel"
    assert get_asr_model("nemotron").__name__ == "NemotronASRModel"
    assert get_vad("silero").__name__ == "SileroVAD"


async def test_qwen3_loader_reports_missing_optional_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "qwen_asr":
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    model = get_asr_model("qwen3")({"model_name": "Qwen/Qwen3-ASR-0.6B"})

    with pytest.raises(ServiceError, match="Qwen3 ASR requires"):
        await model.load({})
