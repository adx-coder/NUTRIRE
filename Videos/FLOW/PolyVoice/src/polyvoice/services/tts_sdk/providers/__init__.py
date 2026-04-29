"""TTS provider registry exports."""

from polyvoice.services.tts_sdk.providers.base import BaseTTSProvider
from polyvoice.services.tts_sdk.providers.local_model import LocalModelProvider
from polyvoice.services.tts_sdk.providers.openai_compatible import OpenAICompatibleProvider
from polyvoice.services.tts_sdk.providers.registry import (
    get_provider,
    list_providers,
    register_provider,
)

__all__ = [
    "BaseTTSProvider",
    "LocalModelProvider",
    "OpenAICompatibleProvider",
    "get_provider",
    "list_providers",
    "register_provider",
]

