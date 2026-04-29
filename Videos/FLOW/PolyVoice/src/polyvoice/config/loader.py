"""Load PolyVoice configuration from YAML files or dictionaries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from polyvoice.config.legacy import (
    legacy_to_polyvoice_config,
    load_env_file,
    looks_like_legacy_config,
    substitute_env_vars,
)
from polyvoice.config.models import PolyVoiceConfig
from polyvoice.core.exceptions import ConfigurationError


def load_config(source: str | Path | dict[str, Any] | None = None) -> PolyVoiceConfig:
    """Load a ``PolyVoiceConfig`` from a path, mapping, or defaults."""

    if source is None:
        return PolyVoiceConfig()

    if isinstance(source, dict):
        data = substitute_env_vars(source)
        if looks_like_legacy_config(data):
            return legacy_to_polyvoice_config(data)
        return PolyVoiceConfig.model_validate(data)

    path = Path(source)
    if not path.exists():
        raise ConfigurationError(f"Config file does not exist: {path}")
    load_env_file(path.parent / ".env")

    try:
        data = substitute_env_vars(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in config file: {path}") from exc

    if not isinstance(data, dict):
        raise ConfigurationError("Config file must contain a mapping at the top level")
    if looks_like_legacy_config(data):
        return legacy_to_polyvoice_config(data)
    return PolyVoiceConfig.model_validate(data)
