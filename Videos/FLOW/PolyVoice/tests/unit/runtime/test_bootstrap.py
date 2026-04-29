"""Tests for config-driven runtime bootstrap."""

import pytest
from fastapi.testclient import TestClient

from polyvoice.config.models import PolyVoiceConfig, ServiceConfig
from polyvoice.core.exceptions import ConfigurationError
from polyvoice.runtime import create_app, create_llm_service, create_pipeline
from polyvoice.services.llm import OpenAICompatibleLLM
from polyvoice.services.mocks import MockLLMService, MockSTTService, MockTTSService


def test_create_pipeline_defaults_to_all_mocks() -> None:
    pipeline = create_pipeline()

    assert isinstance(pipeline.stt, MockSTTService)
    assert isinstance(pipeline.llm, MockLLMService)
    assert isinstance(pipeline.tts, MockTTSService)


def test_create_llm_service_supports_openai_compatible() -> None:
    service = create_llm_service(
        ServiceConfig(
            provider="openai-compatible",
            model="llama-test",
            params={
                "endpoint_url": "http://localhost:8000/v1/chat/completions",
                "api_key": "secret",
                "temperature": 0.1,
                "max_tokens": 64,
            },
        )
    )

    assert isinstance(service, OpenAICompatibleLLM)
    assert service.model == "llama-test"
    assert service.endpoint_url == "http://localhost:8000/v1/chat/completions"
    assert service.api_key == "secret"
    assert service.default_temperature == 0.1
    assert service.default_max_tokens == 64


def test_create_llm_service_requires_endpoint_url() -> None:
    with pytest.raises(ConfigurationError, match="endpoint_url"):
        create_llm_service(ServiceConfig(provider="openai-compatible", model="llama-test"))


def test_create_pipeline_rejects_unknown_provider() -> None:
    with pytest.raises(ConfigurationError, match="Unsupported LLM provider"):
        create_pipeline(
            PolyVoiceConfig(
                llm=ServiceConfig(provider="not-real", model="not-real"),
            )
        )


def test_create_app_accepts_config_dict_and_reports_status() -> None:
    app = create_app(
        config={
            "llm": {
                "provider": "openai-compatible",
                "model": "llama-test",
                "params": {
                    "endpoint_url": "http://localhost:8000/v1/chat/completions",
                },
            }
        }
    )

    with TestClient(app) as client:
        status = client.get("/config/status").json()

    assert status == {
        "stt": {"provider": "mock-stt"},
        "llm": {"provider": "openai-compatible", "model": "llama-test"},
        "tts": {"provider": "mock-tts"},
    }

