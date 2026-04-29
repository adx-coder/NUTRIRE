"""VAD extension points."""

from polyvoice.services.asr_sdk.vad.base import BaseVAD
from polyvoice.services.asr_sdk.vad.energy import EnergyVAD
from polyvoice.services.asr_sdk.vad.registry import get_vad, list_vads, register_vad
from polyvoice.services.asr_sdk.vad.silero import SileroVAD

__all__ = ["BaseVAD", "EnergyVAD", "SileroVAD", "get_vad", "list_vads", "register_vad"]
