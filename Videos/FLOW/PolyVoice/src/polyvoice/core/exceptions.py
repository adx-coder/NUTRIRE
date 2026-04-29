"""Exception hierarchy for PolyVoice."""

from __future__ import annotations


class PolyVoiceError(Exception):
    """Base class for all PolyVoice-specific errors."""


class ConfigurationError(PolyVoiceError):
    """Raised when configuration is missing, invalid, or internally inconsistent."""


class ServiceError(PolyVoiceError):
    """Raised when an ASR, LLM, TTS, or VAD service fails."""


class TelephonyError(PolyVoiceError):
    """Raised when a telephony adapter or call-control operation fails."""


class OrchestrationError(PolyVoiceError):
    """Raised when turn coordination, barge-in, or tool orchestration fails."""


class AudioError(PolyVoiceError):
    """Raised when audio framing, decoding, encoding, or resampling fails."""


class TransportError(PolyVoiceError):
    """Raised when WebSocket or HTTP transport fails."""

