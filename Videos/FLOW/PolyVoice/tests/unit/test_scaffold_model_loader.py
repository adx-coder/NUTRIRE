"""Tests for the model extension scaffold script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "scaffold_model_loader.py"


def load_scaffold_module():
    """Load the scaffold script as a module for direct testing."""

    spec = importlib.util.spec_from_file_location("scaffold_model_loader", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_slugify_normalizes_model_names() -> None:
    module = load_scaffold_module()

    assert module.slugify("Qwen3 ASR 0.6B") == "qwen3_asr_0_6b"
    assert module.slugify("123 Voice") == "model_123_voice"


def test_scaffold_writes_source_and_test_files(tmp_path: Path) -> None:
    module = load_scaffold_module()

    target = module.scaffold(tmp_path, "tts", "Demo Voice", force=False)

    assert target.source_path == (
        tmp_path / "src/polyvoice/services/tts_sdk/model_loaders/demo_voice.py"
    )
    assert target.test_path == tmp_path / "tests/unit/services/tts_sdk/test_demo_voice.py"
    assert '@register_model_loader("demo_voice")' in target.source_path.read_text()
    assert "polyvoice.services.tts_sdk.model_loaders.demo_voice" in (
        target.test_path.read_text()
    )


def test_scaffold_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    module = load_scaffold_module()

    module.scaffold(tmp_path, "llm", "Demo LLM", force=False)

    with pytest.raises(FileExistsError, match="already exists"):
        module.scaffold(tmp_path, "llm", "Demo LLM", force=False)
