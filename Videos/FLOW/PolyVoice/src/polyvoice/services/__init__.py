"""Service interfaces, registries, and built-in implementations."""

from polyvoice.services.base import (
    ChatMessage,
    LLMChunk,
    LLMService,
    STTResult,
    STTService,
    TTSChunk,
    TTSService,
)
from polyvoice.services.llm import OpenAICompatibleLLM
from polyvoice.services.mocks import MockLLMService, MockSTTService, MockTTSService
from polyvoice.services.tts import OpenAICompatibleTTS
from polyvoice.services.tts_sdk import SDKTTSService, StreamingTTSSDK, TTSConfig

__all__ = [
    "ChatMessage",
    "LLMChunk",
    "LLMService",
    "MockLLMService",
    "MockSTTService",
    "MockTTSService",
    "OpenAICompatibleLLM",
    "OpenAICompatibleTTS",
    "SDKTTSService",
    "STTResult",
    "STTService",
    "StreamingTTSSDK",
    "TTSChunk",
    "TTSConfig",
    "TTSService",
]
