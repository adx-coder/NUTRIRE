"""Lazy Silero VAD provider."""

from __future__ import annotations

import numpy as np

from polyvoice.core.exceptions import ServiceError
from polyvoice.services.asr_sdk.models.utils import pcm16_bytes_to_float32
from polyvoice.services.asr_sdk.vad.base import BaseVAD
from polyvoice.services.asr_sdk.vad.registry import register_vad


@register_vad("silero")
class SileroVAD(BaseVAD):
    """Silero VAD integration with the old FLOW watchdog behavior."""

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.model = None
        self.sample_rate = int(config.get("sample_rate", 16_000))
        self.device = str(config.get("device", "cpu"))
        self.threshold = float(config.get("threshold", 0.5))
        self._consecutive_near_zero = 0
        self._near_zero_threshold = float(config.get("near_zero_threshold", 0.05))
        self._near_zero_max_frames = int(config.get("near_zero_max_frames", 200))

    async def load(self, config: dict) -> None:
        del config
        try:
            import torch
            import torch.hub
        except ImportError as exc:
            raise ServiceError(
                "Silero VAD requires torch. Install the ASR VAD optional dependencies."
            ) from exc
        self._torch = torch
        self.model, _utils = torch.hub.load(
            "snakers4/silero-vad",
            "silero_vad",
            trust_repo=True,
        )
        self.model = self.model.to(self.device)
        self.model.eval()

    async def is_speech(self, audio: bytes, *, sample_rate: int) -> bool:
        if self.model is None:
            raise ServiceError("Silero VAD is not loaded")
        samples = pcm16_bytes_to_float32(audio)
        if samples.size == 0:
            return False
        prob = self._infer(samples, sample_rate)
        self._watchdog(prob)
        return prob >= self.threshold

    async def reset(self) -> None:
        self.reset_state()

    def reset_state(self) -> None:
        if self.model is not None and hasattr(self.model, "reset_states"):
            self.model.reset_states()

    def _infer(self, samples: np.ndarray, sample_rate: int) -> float:
        with self._torch.inference_mode():
            audio_tensor = self._torch.from_numpy(samples).float().unsqueeze(0).to(self.device)
            return float(self.model(audio_tensor, sample_rate or self.sample_rate).item())

    def _watchdog(self, prob: float) -> None:
        if prob < self._near_zero_threshold:
            self._consecutive_near_zero += 1
            if self._consecutive_near_zero >= self._near_zero_max_frames:
                self.reset_state()
                self._consecutive_near_zero = 0
        else:
            self._consecutive_near_zero = 0
