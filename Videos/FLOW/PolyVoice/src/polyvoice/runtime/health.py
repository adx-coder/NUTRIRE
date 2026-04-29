"""Health payload helpers."""

from __future__ import annotations

from typing import Any


def health_payload() -> dict[str, Any]:
    """Return a minimal liveness payload."""

    return {"status": "ok", "service": "polyvoice"}


def ready_payload() -> dict[str, Any]:
    """Return a minimal readiness payload."""

    return {"status": "ready"}

