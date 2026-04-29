"""Audio data structures and helpers."""

from polyvoice.audio.agc import AGCResult, AutomaticGainControl, apply_agc_to_pcm16_frame
from polyvoice.audio.codecs import (
    alaw_to_pcm16_bytes,
    float32_to_pcm16,
    float32_to_pcm16_bytes,
    mulaw_to_pcm16_bytes,
    pcm16_bytes_to_alaw,
    pcm16_bytes_to_float32,
    pcm16_bytes_to_mulaw,
    pcm16_bytes_to_wav,
    pcm16_to_float32,
    wav_to_pcm16_bytes,
)
from polyvoice.audio.frames import AudioFrame
from polyvoice.audio.resample import Resampler, resample_pcm16_frame

__all__ = [
    "AGCResult",
    "AudioFrame",
    "AutomaticGainControl",
    "Resampler",
    "alaw_to_pcm16_bytes",
    "apply_agc_to_pcm16_frame",
    "float32_to_pcm16",
    "float32_to_pcm16_bytes",
    "mulaw_to_pcm16_bytes",
    "pcm16_bytes_to_alaw",
    "pcm16_bytes_to_float32",
    "pcm16_bytes_to_mulaw",
    "pcm16_bytes_to_wav",
    "pcm16_to_float32",
    "resample_pcm16_frame",
    "wav_to_pcm16_bytes",
]
