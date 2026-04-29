"""Small in-process registry for PolyVoice service plugins."""

from __future__ import annotations

from typing import Generic, TypeVar

from polyvoice.core.exceptions import ConfigurationError

ServiceT = TypeVar("ServiceT")


class ServiceRegistry(Generic[ServiceT]):
    """Register and retrieve service classes by name."""

    def __init__(self) -> None:
        self._services: dict[str, type[ServiceT]] = {}

    def register(self, name: str, service_cls: type[ServiceT]) -> None:
        """Register a service class under ``name``."""

        normalized = name.strip().lower()
        if not normalized:
            raise ConfigurationError("Service name cannot be empty")
        if normalized in self._services:
            raise ConfigurationError(f"Service '{normalized}' is already registered")
        self._services[normalized] = service_cls

    def get(self, name: str) -> type[ServiceT]:
        """Return a registered service class."""

        normalized = name.strip().lower()
        try:
            return self._services[normalized]
        except KeyError as exc:
            available = ", ".join(sorted(self._services)) or "(none)"
            raise ConfigurationError(
                f"Unknown service '{normalized}'. Available: {available}"
            ) from exc

    def names(self) -> list[str]:
        """Return registered service names."""

        return sorted(self._services)


stt_services: ServiceRegistry[object] = ServiceRegistry()
llm_services: ServiceRegistry[object] = ServiceRegistry()
tts_services: ServiceRegistry[object] = ServiceRegistry()
