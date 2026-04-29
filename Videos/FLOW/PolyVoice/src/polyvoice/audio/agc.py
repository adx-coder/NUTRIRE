"""Lightweight automatic gain control for voice audio."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from polyvoice.audio.codecs import float32_to_pcm16_bytes, pcm16_bytes_to_float32
from polyvoice.audio.frames import AudioFrame


@dataclass(slots=True)
class AGCResult:
    """Output of automatic gain control."""

    audio: np.ndarray
    rms_db: float
    gain_db: float


class AutomaticGainControl:
    """Stateful AGC tuned for streaming voice chunks."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        target_dbfs: float = -20.0,
        min_rms_dbfs: float = -65.0,
        min_gain_db: float = -15.0,
        max_gain_db: float = 25.0,
        attack: float = 0.15,
        release: float = 0.008,
    ) -> None:
        self.enabled = enabled
        self.target_dbfs = target_dbfs
        self.min_rms_dbfs = min_rms_dbfs
        self.min_gain_db = min_gain_db
        self.max_gain_db = max_gain_db
        self.attack = attack
        self.release = release
        self.current_gain_db = 0.0

    def process(self, audio: np.ndarray) -> AGCResult:
        """Apply AGC to float audio in ``[-1.0, 1.0]``."""

        if len(audio) == 0:
            return AGCResult(audio=audio.astype(np.float32), rms_db=-60.0, gain_db=self.current_gain_db)

        working = audio.astype(np.float32, copy=True)
        if not np.isfinite(working).all():
            return AGCResult(audio=working, rms_db=-60.0, gain_db=self.current_gain_db)

        working = np.clip(working, -1.0, 1.0)
        if np.all(working == 0):
            return AGCResult(audio=working, rms_db=-60.0, gain_db=self.current_gain_db)

        rms = float(np.sqrt(np.mean(working**2)))
        rms = max(rms, 1e-10)
        rms_db = float(20.0 * np.log10(rms))

        if not self.enabled or rms_db < self.min_rms_dbfs:
            return AGCResult(audio=working, rms_db=rms_db, gain_db=self.current_gain_db)

        target_gain = float(np.clip(self.target_dbfs - rms_db, self.min_gain_db, self.max_gain_db))
        smoothing = self.attack if target_gain > self.current_gain_db else self.release
        self.current_gain_db += (target_gain - self.current_gain_db) * smoothing

        gain_linear = 10.0 ** (self.current_gain_db / 20.0)
        processed = np.tanh(working * gain_linear * 0.95)
        processed = np.clip(processed, -1.0, 1.0).astype(np.float32)
        return AGCResult(audio=processed, rms_db=rms_db, gain_db=self.current_gain_db)


def apply_agc_to_pcm16_frame(frame: AudioFrame, agc: AutomaticGainControl) -> tuple[AudioFrame, AGCResult]:
    """Apply AGC to a canonical PCM16 frame and return the updated frame plus metrics."""

    frame.require_pcm16_mono()
    result = agc.process(pcm16_bytes_to_float32(frame.audio))
    return frame.with_audio(float32_to_pcm16_bytes(result.audio), format="pcm16"), result

