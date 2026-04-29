"""Tests for audio resampling."""

import numpy as np
import pytest

from polyvoice.audio.codecs import float32_to_pcm16_bytes
from polyvoice.audio.frames import AudioFrame
from polyvoice.audio.resample import Resampler, resample_pcm16_frame


def test_resample_same_rate_returns_copy() -> None:
    audio = np.array([0.0, 0.5, 1.0], dtype=np.float32)

    result = Resampler.resample(audio, 16_000, 16_000)

    assert np.array_equal(result, audio)
    assert result is not audio


def test_resample_downsamples_length() -> None:
    audio = np.linspace(-1.0, 1.0, 16_000, dtype=np.float32)

    result = Resampler.resample(audio, 16_000, 8_000)

    assert len(result) == 8_000
    assert result.dtype == np.float32


def test_resample_rejects_multichannel_arrays() -> None:
    with pytest.raises(Exception):
        Resampler.resample(np.zeros((2, 2), dtype=np.float32), 16_000, 8_000)


def test_resample_pcm16_frame_updates_metadata() -> None:
    frame = AudioFrame(
        audio=float32_to_pcm16_bytes(np.linspace(-0.5, 0.5, 160, dtype=np.float32)),
        sample_rate=16_000,
    )

    result = resample_pcm16_frame(frame, 8_000)

    assert result.sample_rate == 8_000
    assert result.format == "pcm16"
    assert len(result.audio) == 80 * 2

