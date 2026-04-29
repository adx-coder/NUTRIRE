"""TTS model loader registry exports."""

from polyvoice.services.tts_sdk.model_loaders.base import BaseModelLoader
from polyvoice.services.tts_sdk.model_loaders.kokoro import KokoroLoader
from polyvoice.services.tts_sdk.model_loaders.registry import (
    get_model_loader,
    list_model_loaders,
    register_model_loader,
)

__all__ = [
    "BaseModelLoader",
    "KokoroLoader",
    "get_model_loader",
    "list_model_loaders",
    "register_model_loader",
]
