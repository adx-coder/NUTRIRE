"""Codec registry."""

from __future__ import annotations

from polyvoice.core.exceptions import ConfigurationError
from polyvoice.services.tts_sdk.codecs.base import BaseCodec

_CODECS: dict[str, type[BaseCodec]] = {}


def register_codec(name: str):
    """Decorator registering a codec class."""

    normalized = name.strip().lower()

    def decorator(cls: type[BaseCodec]):
        _CODECS.setdefault(normalized, cls)
        return cls

    return decorator


def get_codec(name: str) -> type[BaseCodec]:
    """Return a registered codec class."""

    normalized = name.strip().lower()
    try:
        return _CODECS[normalized]
    except KeyError as exc:
        available = ", ".join(sorted(_CODECS)) or "(none)"
        raise ConfigurationError(f"Unknown codec '{normalized}'. Available: {available}") from exc


def list_codecs() -> list[str]:
    """Return registered codec names."""

    return sorted(_CODECS)

