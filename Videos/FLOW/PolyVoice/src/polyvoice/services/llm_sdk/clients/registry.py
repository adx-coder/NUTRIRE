"""LLM client registry."""

from __future__ import annotations

from polyvoice.core.exceptions import ConfigurationError
from polyvoice.services.llm_sdk.clients.base import BaseLLMClient

_CLIENTS: dict[str, type[BaseLLMClient]] = {}


def register_llm_client(name: str):
    """Decorator registering an LLM client class."""

    normalized = name.strip().lower()

    def decorator(cls: type[BaseLLMClient]):
        _CLIENTS.setdefault(normalized, cls)
        return cls

    return decorator


def get_llm_client(name: str) -> type[BaseLLMClient]:
    """Return a registered LLM client class."""

    normalized = name.strip().lower()
    try:
        return _CLIENTS[normalized]
    except KeyError as exc:
        available = ", ".join(sorted(_CLIENTS)) or "(none)"
        raise ConfigurationError(f"Unknown LLM client '{normalized}'. Available: {available}") from exc
