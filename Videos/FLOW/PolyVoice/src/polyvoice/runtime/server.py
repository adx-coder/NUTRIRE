"""FastAPI application factory for PolyVoice."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from polyvoice.config.loader import load_config
from polyvoice.config.models import PolyVoiceConfig
from polyvoice.runtime.bootstrap import create_pipeline
from polyvoice.runtime.health import health_payload, ready_payload
from polyvoice.runtime.pipeline import VoicePipeline
from polyvoice.transport.ws_voice import register_voice_ws


def create_app(
    pipeline: VoicePipeline | None = None,
    *,
    config: PolyVoiceConfig | dict[str, Any] | str | Path | None = None,
) -> FastAPI:
    """Create the PolyVoice FastAPI app."""

    loaded_config = config if isinstance(config, PolyVoiceConfig) else load_config(config)
    voice_pipeline = pipeline or create_pipeline(loaded_config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.voice_pipeline = voice_pipeline
        await voice_pipeline.start()
        try:
            yield
        finally:
            await voice_pipeline.stop()

    app = FastAPI(title="PolyVoice", version="0.1.0a0", lifespan=lifespan)
    app.state.voice_pipeline = voice_pipeline

    @app.get("/health")
    async def health() -> dict[str, object]:
        return health_payload()

    @app.get("/ready")
    async def ready() -> dict[str, object]:
        return ready_payload()

    @app.get("/config/status")
    async def config_status() -> dict[str, object]:
        return {
            "stt": {"provider": voice_pipeline.stt.name},
            "llm": {
                "provider": voice_pipeline.llm.name,
                "model": getattr(voice_pipeline.llm, "model", None),
            },
            "tts": {"provider": voice_pipeline.tts.name},
        }

    register_voice_ws(app)
    return app
