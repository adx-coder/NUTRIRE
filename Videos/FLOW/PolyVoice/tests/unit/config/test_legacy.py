"""Tests for legacy Voice-Agent config compatibility."""

from pathlib import Path

import pytest

from polyvoice.config.legacy import (
    extract_model_recipes,
    legacy_to_polyvoice_config,
    looks_like_legacy_config,
)
from polyvoice.config.loader import load_config


@pytest.fixture
def local_tmp_path() -> Path:
    path = Path(__file__).resolve().parents[3] / ".pytest-local" / "legacy-config"
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_file():
            child.unlink()
    return path


def test_looks_like_legacy_config_detects_old_shape() -> None:
    assert looks_like_legacy_config({"server": {}, "asr": {}, "llm": {}, "tts": {}})
    assert not looks_like_legacy_config({"runtime": {}, "stt": {}, "llm": {}, "tts": {}})


def test_legacy_to_polyvoice_maps_runtime_and_llm() -> None:
    config = legacy_to_polyvoice_config(
        {
            "server": {"host": "0.0.0.0", "port": 8092},
            "asr": {
                "backend": "nemotron",
                "model_name": "nvidia/nemotron",
                "logging": {"level": "INFO"},
            },
            "llm": {
                "backend": "mistral",
                "endpoint_url": "https://api.mistral.ai/v1/chat/completions",
                "model_name": "mistral-large",
                "api_key": "secret",
                "default_temperature": 0.2,
                "default_max_tokens": 64,
            },
            "tts": {"backend": "kokoro", "kokoro": {"voice": "af_heart"}},
        }
    )

    assert config.runtime.host == "0.0.0.0"
    assert config.runtime.port == 8092
    assert config.runtime.log_level == "info"
    assert config.stt.provider == "mock"
    assert config.stt.model == "nvidia/nemotron"
    assert config.stt.params["legacy_backend"] == "nemotron"
    assert config.llm.provider == "openai-compatible"
    assert config.llm.model == "mistral-large"
    assert config.llm.params["endpoint_url"] == "https://api.mistral.ai/v1/chat/completions"
    assert config.llm.params["api_key"] == "secret"
    assert config.llm.params["temperature"] == 0.2
    assert config.llm.params["max_tokens"] == 64
    assert config.tts.provider == "mock"
    assert config.tts.params["legacy_backend"] == "kokoro"
    assert config.tts.params["voice"] == "af_heart"
    assert len(config.params["compatibility_warnings"]) == 2
    assert config.params["model_recipes"]["llm"]["active"]["model_name"] == "mistral-large"
    assert config.params["model_recipes"]["tts"]["recipes"]["kokoro"]["voice"] == "af_heart"


def test_extract_model_recipes_preserves_registries() -> None:
    recipes = extract_model_recipes(
        {
            "asr": {
                "backend": "nemotron",
                "model_name": "nvidia/nemotron",
                "qwen3": {"model_name": "Qwen/Qwen3-ASR-0.6B"},
                "vad": {"backend": "silero"},
                "smart_turn": {"enabled": True},
            },
            "llm": {
                "backend": "mistral",
                "model_name": "mistral-large",
                "available_models": {
                    "mistral_large": {
                        "backend": "mistral",
                        "endpoint_url": "https://api.mistral.ai/v1/chat/completions",
                        "model_name": "mistral-large-2411",
                    },
                    "llama_3_1_8b": {
                        "backend": "vllm",
                        "endpoint_url": "http://localhost:8000/v1/chat/completions",
                        "model_name": "meta-llama/Llama-3.1-8B-Instruct",
                    },
                },
            },
            "tts": {
                "backend": "kokoro",
                "kokoro": {"voice": "af_heart", "repo_id": "hexgrad/Kokoro-82M"},
                "maya1": {"model_path": "~/tts/maya1", "voice": "agent-marcus"},
            },
            "voice_pipeline": {"mode": "synchronous"},
        }
    )

    assert recipes["asr"]["recipes"]["nemotron"]["model_name"] == "nvidia/nemotron"
    assert recipes["asr"]["recipes"]["qwen3"]["model_name"] == "Qwen/Qwen3-ASR-0.6B"
    assert set(recipes["llm"]["available_models"]) == {"mistral_large", "llama_3_1_8b"}
    assert recipes["tts"]["recipes"]["kokoro"]["repo_id"] == "hexgrad/Kokoro-82M"
    assert recipes["tts"]["recipes"]["maya1"]["voice"] == "agent-marcus"
    assert recipes["voice_pipeline"]["mode"] == "synchronous"


def test_load_config_substitutes_env_file(local_tmp_path: Path) -> None:
    (local_tmp_path / ".env").write_text("TEST_API_KEY=from-env\n", encoding="utf-8")
    config_path = local_tmp_path / "config.yaml"
    config_path.write_text(
        """
server:
  host: 127.0.0.1
  port: 8093
asr:
  backend: mock
llm:
  backend: openai
  endpoint_url: http://localhost:8000/v1/chat/completions
  model_name: test-model
  api_key: ${TEST_API_KEY}
tts:
  backend: mock
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.runtime.port == 8093
    assert config.llm.params["api_key"] == "from-env"


def test_load_config_drops_unresolved_secret_env_var(local_tmp_path: Path) -> None:
    config_path = local_tmp_path / "config.yaml"
    config_path.write_text(
        """
server:
  host: 127.0.0.1
asr:
  backend: mock
llm:
  backend: openai
  endpoint_url: http://localhost:8000/v1/chat/completions
  model_name: test-model
  api_key: ${MISSING_API_KEY}
tts:
  backend: mock
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert "api_key" not in config.llm.params


def test_actual_voice_agent_config_smoke_loads_when_present() -> None:
    legacy_path = Path(__file__).resolve().parents[4] / "Voice-Agent" / "config.yaml"
    if not legacy_path.exists():
        return

    config = load_config(legacy_path)

    assert config.runtime.port == 8092
    assert config.llm.provider == "openai-compatible"
    assert config.stt.provider == "mock"
    assert config.tts.provider == "mock"
    assert config.params["legacy_config"] is True
    recipes = config.params["model_recipes"]
    assert "qwen3" in recipes["asr"]["recipes"]
    assert {
        "mistral_large",
        "mistral_small",
        "gpt4o",
        "gpt4o_mini",
        "llama_3_1_8b",
        "llama_3_3_70b",
        "qwen_2_5_7b",
        "deepseek_r1",
    }.issubset(recipes["llm"]["available_models"])
    assert {
        "magpie",
        "soprano",
        "kokoro",
        "chatterbox",
        "chatterbox_mtl",
        "maya1",
    }.issubset(recipes["tts"]["recipes"])
