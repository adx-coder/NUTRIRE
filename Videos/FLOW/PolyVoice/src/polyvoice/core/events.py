"""Typed voice events used by PolyVoice transports and processors."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class VoiceEventType(str, Enum):
    """Canonical event names on the PolyVoice event bus and WebSocket wire."""

    READY = "ready"
    AUDIO_CHUNK = "audio_chunk"
    ASR_PARTIAL = "asr_partial"
    ASR_FINAL = "asr_final"
    LLM_CHUNK = "llm_chunk"
    LLM_COMPLETE = "llm_complete"
    TTS_AUDIO_CHUNK = "tts_audio_chunk"
    TTS_STOP = "tts_stop"
    TTS_FLUSH = "tts_flush"
    INTERRUPTION = "interruption"
    ERROR = "error"


class VoiceEvent(BaseModel):
    """Base event shared by all PolyVoice runtime messages."""

    model_config = ConfigDict(use_enum_values=True)

    type: VoiceEventType
    session_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReadyEvent(VoiceEvent):
    """Emitted when a voice session is ready to receive audio."""

    type: Literal[VoiceEventType.READY] = VoiceEventType.READY
    message: str = "Voice orchestrator ready"


class AudioChunkEvent(VoiceEvent):
    """Carries normalized PCM audio through the internal pipeline."""

    type: Literal[VoiceEventType.AUDIO_CHUNK] = VoiceEventType.AUDIO_CHUNK
    audio: bytes
    sample_rate: int = 16_000
    channels: int = 1
    sequence: int | None = None


class TranscriptEvent(VoiceEvent):
    """Carries ASR partial and final transcript text."""

    type: Literal[VoiceEventType.ASR_PARTIAL, VoiceEventType.ASR_FINAL]
    text: str
    confidence: float | None = None
    start_time: float | None = None
    end_time: float | None = None
    interrupted: bool = False
    interruption_type: str | None = None


class LLMChunkEvent(VoiceEvent):
    """Carries streamed LLM output."""

    type: Literal[VoiceEventType.LLM_CHUNK, VoiceEventType.LLM_COMPLETE]
    text: str
    chunk_id: str | int | None = None
    is_sentence: bool = False


class TTSAudioEvent(VoiceEvent):
    """Carries synthesized audio destined for the caller."""

    type: Literal[
        VoiceEventType.TTS_AUDIO_CHUNK,
        VoiceEventType.TTS_STOP,
        VoiceEventType.TTS_FLUSH,
    ]
    audio: bytes | None = None
    sample_rate: int | None = None
    chunk_index: int | None = None
    turn_id: int | None = None
    stop_generation: int | None = None
    reason: str | None = None


class ErrorEvent(VoiceEvent):
    """Carries a recoverable or fatal runtime error."""

    type: Literal[VoiceEventType.ERROR] = VoiceEventType.ERROR
    message: str
    code: str | None = None


def ready_event(session_id: str, message: str = "Voice orchestrator ready") -> ReadyEvent:
    """Build a ready event."""

    return ReadyEvent(session_id=session_id, message=message)


def error_event(session_id: str, message: str, code: str | None = None) -> ErrorEvent:
    """Build an error event."""

    return ErrorEvent(session_id=session_id, message=message, code=code)

