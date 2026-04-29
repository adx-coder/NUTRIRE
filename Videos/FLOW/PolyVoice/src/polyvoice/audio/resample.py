"""Numpy-only audio resampling helpers."""

from __future__ import annotations

import numpy as np

from polyvoice.audio.codecs import float32_to_pcm16_bytes, pcm16_bytes_to_float32
from polyvoice.audio.frames import AudioFrame
from polyvoice.core.exceptions import AudioError


class Resampler:
    """Resample mono audio between sample rates using linear interpolation."""

    @staticmethod
    def resample(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
        """Resample a one-dimensional audio array."""

        if from_rate <= 0 or to_rate <= 0:
            raise AudioError("Sample rates must be positive")
        if audio.ndim != 1:
            raise AudioError("Resampler only supports one-dimensional mono audio")
        if from_rate == to_rate or len(audio) == 0:
            return audio.copy()

        duration = len(audio) / from_rate
        new_length = int(round(duration * to_rate))
        if new_length <= 0:
            return np.array([], dtype=audio.dtype)

        old_indices = np.arange(len(audio))
        new_indices = np.linspace(0, len(audio) - 1, new_length)
        return np.interp(new_indices, old_indices, audio).astype(audio.dtype)


def resample_pcm16_frame(frame: AudioFrame, target_sample_rate: int) -> AudioFrame:
    """Return ``frame`` resampled to ``target_sample_rate``."""

    frame.require_pcm16_mono()
    audio = pcm16_bytes_to_float32(frame.audio)
    resampled = Resampler.resample(audio, frame.sample_rate, target_sample_rate)
    return frame.with_audio(
        float32_to_pcm16_bytes(resampled),
        sample_rate=target_sample_rate,
        format="pcm16",
    )

