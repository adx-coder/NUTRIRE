"""Tiny dependency-free VAD used for tests and local plumbing."""

from __future__ import annotations

from polyvoice.services.asr_sdk.vad.base import BaseVAD
from polyvoice.services.asr_sdk.vad.registry import register_vad


@register_vad("energy")
class EnergyVAD(BaseVAD):
    """Simple non-zero-byte VAD placeholder."""

    async def is_speech(self, audio: bytes, *, sample_rate: int) -> bool:
        del sample_rate
        threshold = int(self.config.get("byte_threshold", 0))
        return any(byte > threshold for byte in audio)
