"""Command-line interface for PolyVoice."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import uvicorn

from polyvoice.config.loader import load_config
from polyvoice.config.recipes import (
    select_asr_recipe,
    select_llm_recipe,
    select_tts_recipe,
)
from polyvoice.runtime.server import create_app


def build_parser() -> argparse.ArgumentParser:
    """Build the PolyVoice CLI parser."""

    parser = argparse.ArgumentParser(prog="polyvoice", description="Run PolyVoice services.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    serve = subcommands.add_parser("serve", help="Run the PolyVoice HTTP/WebSocket server.")
    serve.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to a PolyVoice YAML config file.",
    )
    serve.add_argument("--host", default=None, help="Host to bind. Overrides config runtime.host.")
    serve.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind. Overrides config runtime.port.",
    )
    serve.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default=None,
        help="Uvicorn log level. Overrides config runtime.log_level.",
    )
    serve.add_argument(
        "--llm-model",
        default=None,
        help="LLM recipe key from preserved FLOW config, e.g. mistral_large.",
    )
    serve.add_argument(
        "--asr-model",
        default=None,
        help="ASR recipe key from preserved FLOW config, e.g. qwen3.",
    )
    serve.add_argument(
        "--tts-model",
        default=None,
        help="TTS recipe key from preserved FLOW config, e.g. kokoro.",
    )
    return parser


def create_app_from_args(args: argparse.Namespace):
    """Create an app and resolved runtime settings from parsed CLI args."""

    config = load_config(args.config)
    if args.llm_model:
        config = select_llm_recipe(config, args.llm_model)
    if args.asr_model:
        config = select_asr_recipe(config, args.asr_model)
    if args.tts_model:
        config = select_tts_recipe(config, args.tts_model)
    host = args.host or config.runtime.host
    port = args.port or config.runtime.port
    log_level = args.log_level or config.runtime.log_level
    return create_app(config=config), host, port, log_level


def main(argv: Sequence[str] | None = None) -> int:
    """Run the PolyVoice CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "serve":
        app, host, port, log_level = create_app_from_args(args)
        uvicorn.run(app, host=host, port=port, log_level=log_level)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
