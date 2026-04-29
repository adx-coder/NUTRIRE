"""Tests for FLOW-style TTS SDK skeleton."""

import builtins

import numpy as np
import pytest

from polyvoice.config.legacy import legacy_to_polyvoice_config
from polyvoice.config.recipes import select_tts_recipe
from polyvoice.core.exceptions import ServiceError
from polyvoice.services.tts_sdk import SDKTTSService, StreamingTTSSDK, TTSConfig, TTSRequest
from polyvoice.services.tts_sdk.model_loaders import (
    BaseModelLoader,
    get_model_loader,
    register_model_loader,
)
from polyvoice.services.tts_sdk.models import TTSCapability


@register_model_loader("fake_model")
class FakeModelLoader(BaseModelLoader):
    CAPABILITIES = {TTSCapability.BATCH}

    async def load(self, config: dict) -> None:
        self.config = config

    async def synthesize(self, text: str, request: TTSRequest) -> tuple[np.ndarray, int]:
        value = min(0.5, max(0.0, len(text) / 100.0))
        return np.full(160, value, dtype=np.float32), 16_000

    async def unload(self) -> None:
        pass

    @property
    def native_sample_rate(self) -> int:
        return 16_000

    @property
    def loader_name(self) -> str:
        return "fake_model"


async def test_sdk_loads_registered_model_loader_without_core_changes() -> None:
    sdk = StreamingTTSSDK()
    await sdk.initialize(
        TTSConfig(
            providers=[
                {
                    "provider": "local_model",
                    "model_loader": "fake_model",
                    "name": "fake",
                }
            ]
        )
    )

    chunks = [
        chunk
        async for chunk in sdk.synthesize(
            TTSRequest(
                text="Hello from the registered loader.",
                provider="fake",
                output_sample_rate=16_000,
            )
        )
    ]
    await sdk.shutdown()

    assert len(chunks) == 1
    assert chunks[0].sample_rate == 16_000
    assert isinstance(chunks[0].audio, bytes)
    assert len(chunks[0].audio) == 320


async def test_sdk_tts_service_wraps_sdk_for_polyvoice_runtime() -> None:
    service = SDKTTSService(
        config=TTSConfig(
            providers=[
                {
                    "provider": "local_model",
                    "model_loader": "fake_model",
                    "name": "fake",
                }
            ]
        ),
        provider="fake",
        output_sample_rate=16_000,
    )
    await service.start()

    async def text_stream():
        yield "Hello from service."

    chunks = [chunk async for chunk in service.synthesize_stream(text_stream())]
    await service.stop()

    assert len(chunks) == 1
    assert chunks[0].format == "pcm16"
    assert chunks[0].sample_rate == 16_000
    assert len(chunks[0].audio) == 320


def test_select_tts_recipe_activates_sdk_config() -> None:
    config = legacy_to_polyvoice_config(
        {
            "asr": {"backend": "mock"},
            "llm": {"backend": "mock"},
            "tts": {
                "backend": "kokoro",
                "kokoro": {
                    "language": "en",
                    "voice": "af_heart",
                    "repo_id": "hexgrad/Kokoro-82M",
                },
            },
        }
    )

    selected = select_tts_recipe(config, "kokoro")

    assert selected.tts.provider == "tts-sdk"
    assert selected.tts.model == "kokoro"
    provider = selected.tts.params["sdk_config"]["providers"][0]
    assert provider["provider"] == "local_model"
    assert provider["model_loader"] == "kokoro"
    assert provider["voice"] == "af_heart"


def test_kokoro_loader_is_registered_lazily() -> None:
    loader_cls = get_model_loader("kokoro")

    assert loader_cls.__name__ == "KokoroLoader"
    voices = loader_cls().get_voices()
    assert any(voice.voice_id == "af_heart" for voice in voices)


async def test_kokoro_loader_reports_missing_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "kokoro":
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    loader = get_model_loader("kokoro")()

    with pytest.raises(ServiceError, match="Kokoro TTS requires"):
        await loader.load({"language": "en", "device": "cpu"})
