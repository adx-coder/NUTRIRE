"""Tests for preserved FLOW recipe activation."""

from pathlib import Path

import pytest

from polyvoice.config.loader import load_config
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


def test_select_qwen3_recipe_preserves_old_gpu_tested_config() -> None:
    config = legacy_to_polyvoice_config(
        {
            "asr": {
                "backend": "nemotron",
                "model_name": "nvidia/nemotron",
                "device": "cuda",
                "sample_rate": 16_000,
                "chunk_size_sec": 0.032,
                "max_buffer_sec": 60.0,
                "overlap_sec": 0.09,
                "cache_aware_streaming": True,
                "final_padding_sec": 0.08,
                "asr_window_sec": 1.0,
                "asr_stride_sec": 0.5,
                "asr_throttle_sec": 0.2,
                "min_finalization_confidence": 0.50,
                "min_partial_confidence": 0.40,
                "enable_punctuation": True,
                "enable_agc": True,
                "enable_vad": True,
                "enable_volume_barge_in": True,
                "use_smart_turn_endpointing": True,
                "reproducible": True,
                "seed": 42,
                "vad": {
                    "backend": "silero",
                    "threshold": 0.45,
                    "onset_frames": 2,
                    "offset_frames": 8,
                    "hangover_frames": 15,
                    "pre_roll_chunks": 15,
                },
                "qwen3": {
                    "model_name": "Qwen/Qwen3-ASR-0.6B",
                    "gpu_memory_utilization": 0.08,
                    "max_model_len": 4096,
                    "max_inference_batch_size": 32,
                    "max_new_tokens": 256,
                    "enable_forced_aligner": False,
                    "forced_aligner_model": "Qwen/Qwen3-ForcedAligner-0.6B",
                },
            },
            "llm": {"backend": "mock"},
            "tts": {"backend": "mock"},
        }
    )

    selected = select_asr_recipe(config, "qwen3")
    sdk_config = selected.stt.params["sdk_config"]
    model = sdk_config["models"][0]

    assert selected.stt.provider == "asr-sdk"
    assert selected.stt.model == "qwen3"
    assert selected.stt.params["sample_rate"] == 16_000
    assert model["model_loader"] == "qwen3"
    assert model["model_name"] == "Qwen/Qwen3-ASR-0.6B"
    assert model["device"] == "cuda"
    assert model["chunk_size_sec"] == 0.032
    assert model["final_padding_sec"] == 0.08
    assert model["gpu_memory_utilization"] == 0.08
    assert model["max_model_len"] == 4096
    assert model["max_inference_batch_size"] == 32
    assert model["max_new_tokens"] == 256
    assert model["enable_forced_aligner"] is False
    assert sdk_config["vad"]["provider"] == "silero"
    assert sdk_config["vad"]["threshold"] == 0.45
    assert sdk_config["vad"]["onset_frames"] == 2
    assert sdk_config["processing"]["min_finalization_confidence"] == 0.50
    assert sdk_config["processing"]["min_partial_confidence"] == 0.40


def test_actual_voice_agent_qwen3_recipe_preserves_gpu_tested_values() -> None:
    legacy_path = Path(__file__).resolve().parents[4] / "Voice-Agent" / "config.yaml"
    if not legacy_path.exists():
        return

    selected = select_asr_recipe(load_config(legacy_path), "qwen3")
    sdk_config = selected.stt.params["sdk_config"]
    model = sdk_config["models"][0]

    assert model["model_name"] == "Qwen/Qwen3-ASR-0.6B"
    assert model["device"] == "cuda"
    assert model["gpu_memory_utilization"] == 0.08
    assert model["max_model_len"] == 4096
    assert model["max_inference_batch_size"] == 32
    assert model["max_new_tokens"] == 256
    assert model["chunk_size_sec"] == 0.032
    assert model["asr_throttle_sec"] == 0.2
    assert sdk_config["vad"]["provider"] == "silero"
    assert sdk_config["vad"]["threshold"] == 0.45
