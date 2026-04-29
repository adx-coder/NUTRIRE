"""Model loader registry."""

from __future__ import annotations

from polyvoice.core.exceptions import ConfigurationError
from polyvoice.services.tts_sdk.model_loaders.base import BaseModelLoader

_LOADERS: dict[str, type[BaseModelLoader]] = {}


def register_model_loader(name: str):
    """Decorator registering a model loader class."""

    normalized = name.strip().lower()

    def decorator(cls: type[BaseModelLoader]):
        _LOADERS.setdefault(normalized, cls)
        return cls

    return decorator


def get_model_loader(name: str) -> type[BaseModelLoader]:
    """Return a registered loader class."""

    normalized = name.strip().lower()
    try:
        return _LOADERS[normalized]
    except KeyError as exc:
        available = ", ".join(sorted(_LOADERS)) or "(none)"
        raise ConfigurationError(
            f"Unknown TTS model loader '{normalized}'. Available: {available}"
        ) from exc


def list_model_loaders() -> list[str]:
    """Return registered loader names."""

    return sorted(_LOADERS)

