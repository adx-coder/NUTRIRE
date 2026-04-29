"""VAD registry."""

from __future__ import annotations

from polyvoice.core.exceptions import ConfigurationError
from polyvoice.services.asr_sdk.vad.base import BaseVAD

_VADS: dict[str, type[BaseVAD]] = {}


def register_vad(name: str):
    """Decorator registering a VAD class."""

    normalized = name.strip().lower()

    def decorator(cls: type[BaseVAD]):
        _VADS.setdefault(normalized, cls)
        return cls

    return decorator


def get_vad(name: str) -> type[BaseVAD]:
    """Return a registered VAD class."""

    normalized = name.strip().lower()
    try:
        return _VADS[normalized]
    except KeyError as exc:
        available = ", ".join(sorted(_VADS)) or "(none)"
        raise ConfigurationError(f"Unknown VAD '{normalized}'. Available: {available}") from exc
