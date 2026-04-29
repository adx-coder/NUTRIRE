"""Canonical audio frame shape used inside PolyVoice."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


AudioFormat = Literal["pcm16", "mulaw", "alaw", "opus", "wav"]


@dataclass(frozen=True, slots=True)
class AudioFrame:
    """One chunk of audio plus enough metadata to normalize or route it."""

    audio: bytes
    sample_rate: int = 16_000
    channels: int = 1
    format: AudioFormat = "pcm16"
    sequence: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """Return whether this frame contains no audio bytes."""

        return len(self.audio) == 0

    @property
    def duration_seconds(self) -> float:
        """Return approximate duration for PCM16-style mono frames."""

        if self.sample_rate <= 0 or self.channels <= 0:
            return 0.0
        if self.format != "pcm16":
            return 0.0
        bytes_per_sample = 2
        samples = len(self.audio) / bytes_per_sample / self.channels
        return samples / self.sample_rate

    @property
    def duration_ms(self) -> float:
        """Return approximate duration in milliseconds."""

        return self.duration_seconds * 1000.0

    def with_audio(
        self,
        audio: bytes,
        *,
        sample_rate: int | None = None,
        channels: int | None = None,
        format: AudioFormat | None = None,
    ) -> AudioFrame:
        """Return a copy with replaced audio and optional audio metadata."""

        return AudioFrame(
            audio=audio,
            sample_rate=self.sample_rate if sample_rate is None else sample_rate,
            channels=self.channels if channels is None else channels,
            format=self.format if format is None else format,
            sequence=self.sequence,
            metadata=dict(self.metadata),
        )

    def require_pcm16_mono(self) -> None:
        """Raise ``ValueError`` unless this frame is canonical PCM16 mono."""

        if self.format != "pcm16":
            raise ValueError(f"Expected pcm16 frame, got {self.format}")
        if self.channels != 1:
            raise ValueError(f"Expected mono frame, got {self.channels} channels")
        if self.sample_rate <= 0:
            raise ValueError("Sample rate must be positive")
