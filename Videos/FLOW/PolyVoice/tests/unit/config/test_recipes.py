"""Tests for preserved FLOW recipe activation."""

import pytest

from polyvoice.config.legacy import legacy_to_polyvoice_config
from polyvoice.config.recipes import (
    select_asr_recipe,
    select_llm_recipe,
)
from polyvoice.core.exceptions import ConfigurationError


def _config_with_recipes():
    return legacy_to_polyvoice_config(
        {
            "server": {"host": "127.0.0.1", "port": 8092},
            "asr": {"backend": "nemotron", "model_name": "nvidia/nemotron"},
            "llm": {
                "backend": "mistral",
                "model_name": "mistral-large-2411",
                "default_temperature": 0.3,
                "default_max_tokens": 99,
                "available_models": {
                    "mistral_large": {
                        "label": "Mistral Large",
                        "backend": "mistral",
                        "endpoint_url": "https://api.mistral.ai/v1/chat/completions",
                        "model_name": "mistral-large-2411",
                    },
                    "llama_3_1_8b": {
                        "label": "Llama 3.1 8B",
                        "backend": "vllm",
                        "endpoint_url": "http://localhost:8000/v1/chat/completions",
                        "model_name": "meta-llama/Llama-3.1-8B-Instruct",
                    },
                },
            },
            "tts": {"backend": "kokoro"},
        }
    )


def test_select_llm_recipe_activates_mistral_recipe() -> None:
    config = select_llm_recipe(_config_with_recipes(), "mistral_large")

    assert config.llm.provider == "llm-sdk"
    assert config.llm.model == "mistral-large-2411"
    assert config.llm.params["client_name"] == "mistral_large"
    assert config.llm.params["legacy_backend"] == "mistral"
    client = config.llm.params["sdk_config"]["clients"][0]
    assert client["endpoint_url"] == "https://api.mistral.ai/v1/chat/completions"
    assert client["temperature"] == 0.3
    assert client["max_tokens"] == 99
    assert config.params["selected_recipes"]["llm"] == "mistral_large"


def test_select_llm_recipe_activates_local_vllm_recipe() -> None:
    config = select_llm_recipe(_config_with_recipes(), "llama_3_1_8b")

    assert config.llm.provider == "llm-sdk"
    assert config.llm.model == "meta-llama/Llama-3.1-8B-Instruct"
    client = config.llm.params["sdk_config"]["clients"][0]
    assert client["endpoint_url"] == "http://localhost:8000/v1/chat/completions"
    assert config.llm.params["legacy_backend"] == "vllm"


def test_select_llm_recipe_rejects_unknown_key() -> None:
    with pytest.raises(ConfigurationError, match="Unknown LLM recipe"):
        select_llm_recipe(_config_with_recipes(), "missing")


def test_select_asr_recipe_activates_sdk_config() -> None:
    config = select_asr_recipe(_config_with_recipes(), "nemotron")

    assert config.stt.provider == "asr-sdk"
    assert config.stt.model == "nemotron"
    assert config.stt.params["sdk_config"]["models"][0]["model_loader"] == "nemotron"
    assert config.params["selected_recipes"]["asr"] == "nemotron"
