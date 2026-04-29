"""Pydantic configuration models for the first PolyVoice runtime slice."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ServiceConfig(BaseModel):
    """Configuration for one model-backed service."""

    provider: str = "mock"
    model: str = "mock"
    params: dict[str, Any] = Field(default_factory=dict)


class RuntimeConfig(BaseModel):
    """HTTP/WebSocket runtime settings."""

    host: str = "127.0.0.1"
    port: int = 8092
    log_level: Literal["debug", "info", "warning", "error"] = "info"


class PolyVoiceConfig(BaseModel):
    """Root PolyVoice configuration."""

    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    stt: ServiceConfig = Field(default_factory=ServiceConfig)
    llm: ServiceConfig = Field(default_factory=ServiceConfig)
    tts: ServiceConfig = Field(default_factory=ServiceConfig)
    params: dict[str, Any] = Field(default_factory=dict)
