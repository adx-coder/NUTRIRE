"""Tests for the PolyVoice CLI."""

from pathlib import Path

from fastapi import FastAPI

from polyvoice.cli import build_parser, create_app_from_args


def test_serve_parser_accepts_config_and_overrides() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "serve",
            "--config",
            "examples/mock-runtime/config.yaml",
            "--host",
            "0.0.0.0",
            "--port",
            "9001",
            "--log-level",
            "debug",
            "--llm-model",
            "mistral_large",
            "--asr-model",
            "qwen3",
            "--tts-model",
            "kokoro",
        ]
    )

    assert args.command == "serve"
    assert args.config == Path("examples/mock-runtime/config.yaml")
    assert args.host == "0.0.0.0"
    assert args.port == 9001
    assert args.log_level == "debug"
    assert args.llm_model == "mistral_large"
    assert args.asr_model == "qwen3"
    assert args.tts_model == "kokoro"


def test_create_app_from_args_uses_config_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args(["serve", "--config", "examples/mock-runtime/config.yaml"])

    app, host, port, log_level = create_app_from_args(args)

    assert isinstance(app, FastAPI)
    assert host == "127.0.0.1"
    assert port == 8092
    assert log_level == "info"


def test_create_app_from_args_applies_cli_overrides() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "serve",
            "--config",
            "examples/mock-runtime/config.yaml",
            "--host",
            "0.0.0.0",
            "--port",
            "9001",
            "--log-level",
            "warning",
        ]
    )

    _, host, port, log_level = create_app_from_args(args)

    assert host == "0.0.0.0"
    assert port == 9001
    assert log_level == "warning"


def test_create_app_from_args_selects_legacy_llm_recipe_when_available() -> None:
    legacy_config = Path("../Voice-Agent/config.yaml")
    if not legacy_config.exists():
        return

    parser = build_parser()
    args = parser.parse_args(
        [
            "serve",
            "--config",
            str(legacy_config),
            "--llm-model",
            "mistral_large",
        ]
    )

    app, host, port, log_level = create_app_from_args(args)
    pipeline = app.state.voice_pipeline

    assert host == "0.0.0.0"
    assert port == 8092
    assert log_level == "info"
    assert pipeline.llm.name == "llm-sdk"
    assert pipeline.llm.model == "mistral-large-2411"
