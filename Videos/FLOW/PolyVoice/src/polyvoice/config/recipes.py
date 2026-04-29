"""Helpers for activating preserved FLOW model recipes."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from polyvoice.config.models import PolyVoiceConfig, ServiceConfig
from polyvoice.core.exceptions import ConfigurationError

_OPENAI_COMPAT_BACKENDS = {"openai", "mistral", "vllm", "local", "ollama", "openrouter"}


def select_llm_recipe(config: PolyVoiceConfig, key: str) -> PolyVoiceConfig:
    """Return a config copy with a preserved LLM recipe activated through the SDK."""

    recipes = _model_recipes(config)
    available = _dict(_dict(recipes.get("llm")).get("available_models"))
    recipe = _dict(available.get(key))
    if not recipe:
        choices = ", ".join(sorted(available)) or "(none)"
        raise ConfigurationError(f"Unknown LLM recipe '{key}'. Available: {choices}")

    backend = str(recipe.get("backend", "mock")).lower()
    if backend not in _OPENAI_COMPAT_BACKENDS:
        raise ConfigurationError(
            f"LLM recipe '{key}' uses unsupported backend '{backend}'"
        )

    endpoint_url = recipe.get("endpoint_url")
    if not isinstance(endpoint_url, str) or not endpoint_url.strip():
        raise ConfigurationError(f"LLM recipe '{key}' requires endpoint_url")

    updated = config.model_copy(deep=True)
    client_config: dict[str, Any] = {
        "client": "openai_compatible",
        "name": key,
        "endpoint_url": endpoint_url,
        "model": str(recipe.get("model_name") or key),
        "legacy_backend": backend,
        "recipe_key": key,
    }
    api_key = _api_key_from_recipe(recipe)
    if api_key:
        client_config["api_key"] = api_key

    llm_active = _dict(_dict(recipes.get("llm")).get("active"))
    for source_key, target_key in (
        ("default_temperature", "temperature"),
        ("default_max_tokens", "max_tokens"),
        ("request_timeout_seconds", "timeout_seconds"),
    ):
        if source_key in llm_active:
            client_config[target_key] = llm_active[source_key]

    response_processing = {
        target: llm_active[source]
        for source, target in (
            ("enable_sentence_detection", "enable_sentence_detection"),
            ("enable_thinking_filter", "enable_thinking_filter"),
            ("enable_adaptive_chunking", "enable_adaptive_chunking"),
            ("chunk_size_tokens", "chunk_size_tokens"),
            ("minimum_chunk_delay_ms", "minimum_chunk_delay_ms"),
        )
        if source in llm_active
    }
    conversation = {
        target: llm_active[source]
        for source, target in (
            ("max_conversation_turns", "max_conversation_turns"),
            ("max_context_tokens", "max_context_tokens"),
            ("system_prompt", "system_prompt"),
        )
        if source in llm_active
    }

    updated.llm = ServiceConfig(
        provider="llm-sdk",
        model=str(recipe.get("model_name") or key),
        params={
            "client_name": key,
            "legacy_backend": backend,
            "sdk_config": {
                "clients": [client_config],
                "response_processing": response_processing,
                "conversation": conversation,
            },
        },
    )
    updated.params.setdefault("selected_recipes", {})["llm"] = key
    return updated


def select_asr_recipe(config: PolyVoiceConfig, key: str) -> PolyVoiceConfig:
    """Return a config copy with a preserved ASR recipe activated through the SDK."""

    recipes = _model_recipes(config)
    asr_recipes = _dict(_dict(recipes.get("asr")).get("recipes"))
    recipe = _dict(asr_recipes.get(key))
    if not recipe:
        choices = ", ".join(sorted(asr_recipes)) or "(none)"
        raise ConfigurationError(f"Unknown ASR recipe '{key}'. Available: {choices}")

    updated = config.model_copy(deep=True)
    model_config = dict(recipe)
    model_config.setdefault("name", key)
    model_config.setdefault("model_loader", recipe.get("backend", key))
    model_config.setdefault("backend", recipe.get("backend", key))

    processing = {
        target: recipe[source]
        for source, target in (
            ("min_finalization_confidence", "min_finalization_confidence"),
            ("min_partial_confidence", "min_partial_confidence"),
            ("enable_punctuation", "enable_punctuation"),
            ("enable_agc", "enable_agc"),
            ("use_smart_turn_endpointing", "use_smart_turn_endpointing"),
        )
        if source in recipe
    }
    vad = _dict(recipe.get("vad"))
    if recipe.get("enable_vad", bool(vad)):
        vad.setdefault("provider", vad.get("backend") or vad.get("type") or "energy")

    updated.stt = ServiceConfig(
        provider="asr-sdk",
        model=key,
        params={
            "model_name": key,
            "sample_rate": recipe.get("sample_rate", 16_000),
            "legacy_backend": recipe.get("backend", key),
            "sdk_config": {
                "models": [model_config],
                "vad": vad,
                "processing": processing,
            },
        },
    )
    updated.params.setdefault("selected_recipes", {})["asr"] = key
    return updated


def select_tts_recipe(config: PolyVoiceConfig, key: str) -> PolyVoiceConfig:
    """Return a config copy with a preserved TTS recipe activated through the SDK."""

    recipes = _model_recipes(config)
    tts_recipes = _dict(_dict(recipes.get("tts")).get("recipes"))
    recipe = _dict(tts_recipes.get(key))
    if not recipe:
        choices = ", ".join(sorted(tts_recipes)) or "(none)"
        raise ConfigurationError(f"Unknown TTS recipe '{key}'. Available: {choices}")

    updated = config.model_copy(deep=True)
    provider_config = _tts_provider_config_from_recipe(key, recipe)
    provider_name = str(provider_config.get("name") or provider_config.get("model_loader") or key)
    updated.tts = ServiceConfig(
        provider="tts-sdk",
        model=key,
        params={
            "provider_name": provider_name,
            "voice": recipe.get("voice"),
            "speed": recipe.get("speed", 1.0),
            "sample_rate": recipe.get("sample_rate", 24_000),
            "sdk_config": {
                "providers": [provider_config],
                "audio_pipeline": {"target_sample_rate": recipe.get("sample_rate", 24_000)},
            },
        },
    )
    updated.params.setdefault("selected_recipes", {})["tts"] = key
    return updated


def _model_recipes(config: PolyVoiceConfig) -> dict[str, Any]:
    recipes = config.params.get("model_recipes")
    if not isinstance(recipes, dict):
        raise ConfigurationError("Config does not contain preserved model_recipes")
    return recipes


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _api_key_from_recipe(recipe: dict[str, Any]) -> str | None:
    api_key = recipe.get("api_key")
    if isinstance(api_key, str) and api_key.strip():
        return api_key
    return None


def _tts_provider_config_from_recipe(key: str, recipe: dict[str, Any]) -> dict[str, Any]:
    if key in {"kokoro", "soprano", "chatterbox", "chatterbox_mtl", "maya1", "magpie"}:
        provider_config = dict(recipe)
        provider_config.setdefault("provider", "local_model")
        provider_config.setdefault("model_loader", key)
        provider_config.setdefault("name", key)
        return provider_config
    if key in {"openai", "openai_compatible", "openai-compatible", "vllm_tts"}:
        provider_config = dict(recipe)
        provider_config.setdefault("provider", "openai_compatible")
        provider_config.setdefault("name", key)
        return provider_config
    provider_config = dict(recipe)
    provider_config.setdefault("provider", "local_model")
    provider_config.setdefault("model_loader", key)
    provider_config.setdefault("name", key)
    return provider_config
