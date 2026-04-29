"""Compatibility loader for the older Voice-Agent YAML shape."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from polyvoice.config.models import PolyVoiceConfig, RuntimeConfig, ServiceConfig

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")
_OPENAI_COMPAT_BACKENDS = {"openai", "mistral", "vllm", "local", "ollama", "openrouter"}


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs from an env file if it exists."""

    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def substitute_env_vars(value: Any, *, secret_keys: set[str] | None = None) -> Any:
    """Recursively replace `${VAR}` strings with environment values."""

    secrets = secret_keys or {"api_key", "token", "secret", "password"}

    def replace_string(text: str, *, key: str | None = None) -> str | None:
        unresolved_secret = False

        def replace(match: re.Match[str]) -> str:
            nonlocal unresolved_secret
            env_name = match.group(1)
            env_value = os.environ.get(env_name)
            if env_value is None:
                unresolved_secret = bool(key and any(secret in key.lower() for secret in secrets))
                return match.group(0)
            return env_value

        replaced = _ENV_PATTERN.sub(replace, text)
        if unresolved_secret and replaced == text:
            return None
        return replaced

    def walk(obj: Any, *, key: str | None = None) -> Any:
        if isinstance(obj, str):
            return replace_string(obj, key=key)
        if isinstance(obj, dict):
            return {k: walk(v, key=str(k)) for k, v in obj.items()}
        if isinstance(obj, list):
            return [walk(item, key=key) for item in obj]
        return obj

    return walk(value)


def looks_like_legacy_config(data: dict[str, Any]) -> bool:
    """Return whether a raw config mapping looks like old Voice-Agent config."""

    if "runtime" in data or "stt" in data:
        return False
    return any(key in data for key in ("server", "asr", "voice_pipeline"))


def legacy_to_polyvoice_config(data: dict[str, Any]) -> PolyVoiceConfig:
    """Map older Voice-Agent config into the current PolyVoice config model."""

    warnings: list[str] = []

    server = _dict(data.get("server"))
    asr = _dict(data.get("asr"))
    llm = _dict(data.get("llm"))
    tts = _dict(data.get("tts"))

    runtime = RuntimeConfig(
        host=str(server.get("host", "127.0.0.1")),
        port=int(server.get("port", 8092)),
        log_level=str(_dict(asr.get("logging")).get("level", "info")).lower(),
    )

    stt_backend = _optional_str(asr.get("backend")) or "mock"
    stt = ServiceConfig(
        provider="mock",
        model=_optional_str(asr.get("model_name")) or stt_backend,
        params={
            "legacy_backend": stt_backend,
            "legacy_provider_unimplemented": stt_backend != "mock",
        },
    )
    if stt_backend != "mock":
        warnings.append(
            f"ASR backend '{stt_backend}' mapped to mock because the adapter is not implemented yet."
        )

    llm_backend = (_optional_str(llm.get("backend")) or "mock").lower()
    llm_provider = "openai-compatible" if llm_backend in _OPENAI_COMPAT_BACKENDS else "mock"
    llm_params: dict[str, Any] = {
        "legacy_backend": llm_backend,
    }
    if llm_provider == "openai-compatible":
        endpoint_url = _optional_str(llm.get("endpoint_url"))
        if endpoint_url:
            llm_params["endpoint_url"] = endpoint_url
        api_key = _optional_str(llm.get("api_key"))
        if api_key:
            llm_params["api_key"] = api_key
        if "default_temperature" in llm:
            llm_params["temperature"] = llm["default_temperature"]
        if "default_max_tokens" in llm:
            llm_params["max_tokens"] = llm["default_max_tokens"]
    else:
        warnings.append(
            f"LLM backend '{llm_backend}' mapped to mock because it is not OpenAI-compatible."
        )
    llm_config = ServiceConfig(
        provider=llm_provider,
        model=_optional_str(llm.get("model_name")) or llm_backend,
        params=llm_params,
    )

    tts_backend = _optional_str(tts.get("backend")) or "mock"
    tts_params: dict[str, Any] = {
        "legacy_backend": tts_backend,
        "legacy_provider_unimplemented": tts_backend != "mock",
    }
    voice = _optional_str(tts.get("voice")) or _nested_voice(tts, tts_backend)
    if voice:
        tts_params["voice"] = voice
    tts_config = ServiceConfig(
        provider="mock",
        model=tts_backend,
        params=tts_params,
    )
    if tts_backend != "mock":
        warnings.append(
            f"TTS backend '{tts_backend}' mapped to mock because the adapter is not implemented yet."
        )

    runtime_params = {
        "legacy_config": True,
        "compatibility_warnings": warnings,
        "model_recipes": extract_model_recipes(data),
    }

    return PolyVoiceConfig(
        runtime=runtime,
        stt=stt,
        llm=llm_config,
        tts=tts_config,
        params=runtime_params,
    )


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    if not value.strip():
        return None
    if _ENV_PATTERN.fullmatch(value.strip()):
        return None
    return value


def _nested_voice(tts: dict[str, Any], backend: str) -> str | None:
    nested = _dict(tts.get(backend))
    return _optional_str(nested.get("voice"))


def extract_model_recipes(data: dict[str, Any]) -> dict[str, Any]:
    """Preserve the model recipe registry from the old FLOW config."""

    asr = _dict(data.get("asr"))
    llm = _dict(data.get("llm"))
    tts = _dict(data.get("tts"))

    return {
        "asr": _extract_asr_recipes(asr),
        "llm": _extract_llm_recipes(llm),
        "tts": _extract_tts_recipes(tts),
        "voice_pipeline": _dict(data.get("voice_pipeline")),
    }


def _extract_asr_recipes(asr: dict[str, Any]) -> dict[str, Any]:
    active_backend = _optional_str(asr.get("backend")) or "mock"
    recipes: dict[str, Any] = {}

    active_recipe = {
        "backend": active_backend,
        "model_name": asr.get("model_name"),
        "device": asr.get("device"),
        "sample_rate": asr.get("sample_rate"),
        "chunk_size_sec": asr.get("chunk_size_sec"),
        "max_buffer_sec": asr.get("max_buffer_sec"),
        "overlap_sec": asr.get("overlap_sec"),
        "cache_aware_streaming": asr.get("cache_aware_streaming"),
        "final_padding_sec": asr.get("final_padding_sec"),
        "asr_window_sec": asr.get("asr_window_sec"),
        "asr_stride_sec": asr.get("asr_stride_sec"),
        "asr_throttle_sec": asr.get("asr_throttle_sec"),
        "min_finalization_confidence": asr.get("min_finalization_confidence"),
        "min_partial_confidence": asr.get("min_partial_confidence"),
        "enable_punctuation": asr.get("enable_punctuation"),
        "enable_agc": asr.get("enable_agc"),
        "enable_vad": asr.get("enable_vad"),
        "enable_volume_barge_in": asr.get("enable_volume_barge_in"),
        "use_smart_turn_endpointing": asr.get("use_smart_turn_endpointing"),
        "reproducible": asr.get("reproducible"),
        "seed": asr.get("seed"),
        "agc": _dict(asr.get("agc")),
        "vad": _dict(asr.get("vad")),
        "volume_barge_in": _dict(asr.get("volume_barge_in")),
        "smart_turn": _dict(asr.get("smart_turn")),
        "punctuation": _dict(asr.get("punctuation")),
    }
    recipes[active_backend] = _drop_none(active_recipe)

    for key in ("qwen3",):
        nested = _dict(asr.get(key))
        if nested:
            recipe = {**_drop_none(active_recipe), **nested}
            recipe["backend"] = key
            recipes[key] = recipe

    return {
        "active": active_backend,
        "recipes": recipes,
        "feature_toggles": {
            key: asr.get(key)
            for key in (
                "enable_punctuation",
                "enable_agc",
                "enable_vad",
                "enable_volume_barge_in",
                "use_smart_turn_endpointing",
                "reproducible",
            )
            if key in asr
        },
    }


def _extract_llm_recipes(llm: dict[str, Any]) -> dict[str, Any]:
    active_backend = _optional_str(llm.get("backend")) or "mock"
    available = {
        key: dict(value)
        for key, value in _dict(llm.get("available_models")).items()
        if isinstance(value, dict)
    }

    active = _drop_none(
        {
            "backend": active_backend,
            "endpoint_url": llm.get("endpoint_url"),
            "model_name": llm.get("model_name"),
            "api_key": llm.get("api_key"),
            "request_timeout_seconds": llm.get("request_timeout_seconds"),
            "target_ttft_ms": llm.get("target_ttft_ms"),
            "target_tokens_per_second": llm.get("target_tokens_per_second"),
            "target_interrupt_response_ms": llm.get("target_interrupt_response_ms"),
            "chunk_size_tokens": llm.get("chunk_size_tokens"),
            "enable_sentence_detection": llm.get("enable_sentence_detection"),
            "minimum_chunk_delay_ms": llm.get("minimum_chunk_delay_ms"),
            "output_buffer_max_size": llm.get("output_buffer_max_size"),
            "backpressure_strategy": llm.get("backpressure_strategy"),
            "max_conversation_turns": llm.get("max_conversation_turns"),
            "max_context_tokens": llm.get("max_context_tokens"),
            "system_prompt": llm.get("system_prompt"),
            "enable_adaptive_chunking": llm.get("enable_adaptive_chunking"),
            "enable_thinking_filter": llm.get("enable_thinking_filter"),
            "enable_prompt_caching": llm.get("enable_prompt_caching"),
            "circuit_breaker_threshold": llm.get("circuit_breaker_threshold"),
            "circuit_breaker_timeout": llm.get("circuit_breaker_timeout"),
            "enable_circuit_breaker": llm.get("enable_circuit_breaker"),
            "default_temperature": llm.get("default_temperature"),
            "default_max_tokens": llm.get("default_max_tokens"),
            "default_top_p": llm.get("default_top_p"),
            "default_frequency_penalty": llm.get("default_frequency_penalty"),
            "default_presence_penalty": llm.get("default_presence_penalty"),
            "metrics_history_size": llm.get("metrics_history_size"),
            "enable_detailed_metrics": llm.get("enable_detailed_metrics"),
            "device": llm.get("device"),
        }
    )

    return {
        "active": active,
        "available_models": available,
    }


def _extract_tts_recipes(tts: dict[str, Any]) -> dict[str, Any]:
    active_backend = _optional_str(tts.get("backend")) or "mock"
    model_keys = (
        "magpie",
        "soprano",
        "kokoro",
        "chatterbox",
        "chatterbox_mtl",
        "maya1",
    )
    recipes = {
        key: dict(value)
        for key in model_keys
        if isinstance((value := tts.get(key)), dict)
    }

    active = _drop_none(
        {
            "backend": active_backend,
            "voice": tts.get("voice"),
            "device": tts.get("device"),
        }
    )

    return {
        "active": active,
        "recipes": recipes,
    }


def _drop_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}
