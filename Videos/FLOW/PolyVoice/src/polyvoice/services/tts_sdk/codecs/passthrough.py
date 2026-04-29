"""Passthrough codec for models that already emit waveform audio."""

from __future__ import annotations

import numpy as np

from polyvoice.services.tts_sdk.codecs.base import BaseCodec
from polyvoice.services.tts_sdk.codecs.registry import register_codec


@register_codec("passthrough")
class PassthroughCodec(BaseCodec):
    """Return model output unchanged."""

    async def decode(self, data: np.ndarray) -> np.ndarray:
        return data

