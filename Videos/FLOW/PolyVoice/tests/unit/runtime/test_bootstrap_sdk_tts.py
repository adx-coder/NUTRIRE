"""Tests for SDK TTS bootstrap wiring."""

from polyvoice.config.models import ServiceConfig
from polyvoice.runtime.bootstrap import create_tts_service
from polyvoice.services.tts_sdk import SDKTTSService


def test_create_tts_service_supports_sdk_speed_and_voice() -> None:
    service = create_tts_service(
        ServiceConfig(
            provider="tts-sdk",
            model="kokoro",
            params={
                "provider_name": "kokoro",
                "voice": "af_heart",
                "speed": 1.2,
                "sample_rate": 24000,
                "sdk_config": {
                    "providers": [
                        {
                            "provider": "local_model",
                            "model_loader": "kokoro",
                            "name": "kokoro",
                        }
                    ]
                },
            },
        )
    )

    assert isinstance(service, SDKTTSService)
    assert service.provider == "kokoro"
    assert service.voice == "af_heart"
    assert service.speed == 1.2
    assert service.sample_rate == 24000
