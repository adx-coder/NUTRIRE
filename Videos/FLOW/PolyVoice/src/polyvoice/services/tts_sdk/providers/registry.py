"""Provider registry."""

from __future__ import annotations

from polyvoice.core.exceptions import ConfigurationError
from polyvoice.services.tts_sdk.providers.base import BaseTTSProvider

_PROVIDERS: dict[str, type[BaseTTSProvider]] = {}


def register_provider(name: str):
    """Decorator registering a provider class."""

    normalized = name.strip().lower()

    def decorator(cls: type[BaseTTSProvider]):
        _PROVIDERS.setdefault(normalized, cls)
        return cls

    return decorator


def get_provider(name: str) -> type[BaseTTSProvider]:
    """Return a registered provider class."""

    normalized = name.strip().lower()
    try:
        return _PROVIDERS[normalized]
    except KeyError as exc:
        available = ", ".join(sorted(_PROVIDERS)) or "(none)"
        raise ConfigurationError(f"Unknown TTS provider '{normalized}'. Available: {available}") from exc


def list_providers() -> list[str]:
    """Return registered provider names."""

    return sorted(_PROVIDERS)

