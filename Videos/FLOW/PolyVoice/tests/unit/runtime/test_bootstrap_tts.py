"""Tests for TTS bootstrap wiring."""

import pytest

from polyvoice.config.models import ServiceConfig
from polyvoice.core.exceptions import ConfigurationError
from polyvoice.runtime.bootstrap import create_tts_service
from polyvoice.services.tts import OpenAICompatibleTTS


def test_create_tts_service_supports_openai_compatible() -> None:
    service = create_tts_service(
        ServiceConfig(
            provider="openai-compatible",
            model="tts-test",
            params={
                "endpoint_url": "http://tts.local/v1/audio/speech",
                "voice": "verse",
                "response_format": "pcm",
                "sample_rate": 16000,
                "speed": 1.1,
                "extra_body": {"task_type": "Base"},
            },
        )
    )

    assert isinstance(service, OpenAICompatibleTTS)
    assert service.model == "tts-test"
    assert service.endpoint_url == "http://tts.local/v1/audio/speech"
    assert service.voice == "verse"
    assert service.response_format == "pcm"
    assert service.sample_rate == 16000
    assert service.speed == 1.1
    assert service.extra_body == {"task_type": "Base"}


def test_create_tts_service_requires_endpoint_url() -> None:
    with pytest.raises(ConfigurationError, match="endpoint_url"):
        create_tts_service(ServiceConfig(provider="openai-compatible", model="tts-test"))

