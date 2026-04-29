"""Core models for the PolyVoice TTS SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class AudioFormat(str, Enum):
    """Audio sample format."""

    F32 = "float32"
    S16 = "int16"
    PCM_BYTES = "pcm"
    WAV = "wav"


class TTSCapability(str, Enum):
    """Provider/loader capabilities."""

    BATCH = "batch"
    SENTENCE_STREAMING = "sentence_streaming"
    TOKEN_STREAMING = "token_streaming"
    VOICE_SELECT = "voice_select"
    SPEED_CONTROL = "speed_control"


@dataclass(slots=True)
class VoiceInfo:
    """Voice metadata exposed by providers/loaders."""

    voice_id: str
    name: str | None = None
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TTSRequest:
    """Input to a TTS SDK synthesis request."""

    text: str = ""
    provider: str = "default"
    voice: str | None = None
    language: str | None = None
    speed: float = 1.0
    output_sample_rate: int = 24_000
    output_format: AudioFormat = AudioFormat.PCM_BYTES
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SDKTTSChunk:
    """Audio chunk emitted by SDK providers."""

    audio: np.ndarray | bytes
    sample_rate: int
    format: AudioFormat = AudioFormat.F32
    chunk_index: int = 0
    is_final: bool = False
    is_segment_end: bool = False
    sentence_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

