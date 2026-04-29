"""Runtime dependency wiring."""

from __future__ import annotations

from typing import Any

from polyvoice.config.models import PolyVoiceConfig, ServiceConfig
from polyvoice.core.exceptions import ConfigurationError
from polyvoice.runtime.pipeline import VoicePipeline
from polyvoice.services.base import LLMService, STTService, TTSService
from polyvoice.services.asr_sdk import ASRConfig, SDKSTTService
from polyvoice.services.llm import OpenAICompatibleLLM
from polyvoice.services.llm_sdk import LLMConfig, SDKLLMService
from polyvoice.services.mocks import MockLLMService, MockSTTService, MockTTSService
from polyvoice.services.tts import OpenAICompatibleTTS
from polyvoice.services.tts_sdk import SDKTTSService, TTSConfig


def create_mock_pipeline() -> VoicePipeline:
    """Create a complete in-process mock voice pipeline."""

    return VoicePipeline(
        stt=MockSTTService(),
        llm=MockLLMService(),
        tts=MockTTSService(),
    )


def create_pipeline(config: PolyVoiceConfig | None = None) -> VoicePipeline:
    """Create a pipeline from configuration."""

    cfg = config or PolyVoiceConfig()
    return VoicePipeline(
        stt=create_stt_service(cfg.stt),
        llm=create_llm_service(cfg.llm),
        tts=create_tts_service(cfg.tts),
    )


def create_stt_service(config: ServiceConfig) -> STTService:
    """Create an STT service from configuration."""

    provider = _provider(config)
    if provider == "mock":
        return MockSTTService()
    if provider in {"asr-sdk", "stt-sdk", "sdk"}:
        sdk_config = _dict_param(config.params.get("sdk_config"))
        return SDKSTTService(
            config=ASRConfig.from_dict(sdk_config),
            model=_required_param(config, "model_name"),
            sample_rate=int(config.params.get("sample_rate", 16_000)),
        )
    raise ConfigurationError(f"Unsupported STT provider: {config.provider}")


def create_llm_service(config: ServiceConfig) -> LLMService:
    """Create an LLM service from configuration."""

    provider = _provider(config)
    if provider == "mock":
        return MockLLMService()
    if provider in {"openai-compatible", "openai_compatible", "openai-compat"}:
        endpoint_url = _required_param(config, "endpoint_url")
        return OpenAICompatibleLLM(
            endpoint_url=endpoint_url,
            model=config.model,
            api_key=_optional_str(config.params.get("api_key")),
            timeout_seconds=float(config.params.get("timeout_seconds", 30.0)),
            default_temperature=float(config.params.get("temperature", 0.7)),
            default_max_tokens=int(config.params.get("max_tokens", 200)),
        )
    if provider in {"llm-sdk", "sdk"}:
        sdk_config = _dict_param(config.params.get("sdk_config"))
        return SDKLLMService(
            config=LLMConfig.from_dict(sdk_config),
            client=_required_param(config, "client_name"),
            model_name=config.model,
        )
    raise ConfigurationError(f"Unsupported LLM provider: {config.provider}")


def create_tts_service(config: ServiceConfig) -> TTSService:
    """Create a TTS service from configuration."""

    provider = _provider(config)
    if provider == "mock":
        return MockTTSService()
    if provider in {"openai-compatible", "openai_compatible", "openai-compat"}:
        endpoint_url = _required_param(config, "endpoint_url")
        return OpenAICompatibleTTS(
            endpoint_url=endpoint_url,
            model=config.model,
            api_key=_optional_str(config.params.get("api_key")),
            voice=_optional_str(config.params.get("voice")) or "alloy",
            response_format=_optional_str(config.params.get("response_format")) or "wav",
            sample_rate=int(config.params.get("sample_rate", 24_000)),
            speed=float(config.params.get("speed", 1.0)),
            timeout_seconds=float(config.params.get("timeout_seconds", 30.0)),
            extra_body=_dict_param(config.params.get("extra_body")),
        )
    if provider in {"tts-sdk", "sdk"}:
        sdk_config = _dict_param(config.params.get("sdk_config"))
        return SDKTTSService(
            config=TTSConfig.from_dict(sdk_config),
            provider=_required_param(config, "provider_name"),
            voice=_optional_str(config.params.get("voice")),
            speed=float(config.params.get("speed", 1.0)),
            output_sample_rate=int(config.params.get("sample_rate", 24_000)),
        )
    raise ConfigurationError(f"Unsupported TTS provider: {config.provider}")


def _provider(config: ServiceConfig) -> str:
    return config.provider.strip().lower()


def _required_param(config: ServiceConfig, name: str) -> str:
    value = config.params.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(
            f"Service provider '{config.provider}' requires params.{name}"
        )
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigurationError("Optional string parameter must be a string")
    return value


def _dict_param(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigurationError("Dictionary parameter must be a mapping")
    return value
