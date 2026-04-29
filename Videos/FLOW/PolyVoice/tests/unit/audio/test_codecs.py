"""Tests for audio codec helpers."""

import numpy as np
import pytest

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


def test_float32_pcm16_round_trip_shape_and_range() -> None:
    audio = np.array([-1.0, -0.5, 0.0, 0.5, 1.0], dtype=np.float32)

    pcm = float32_to_pcm16(audio)
    restored = pcm16_to_float32(pcm)

    assert pcm.dtype == np.dtype("<i2")
    assert restored.dtype == np.float32
    assert np.all(restored >= -1.0)
    assert np.all(restored <= 1.0)
    assert restored[2] == pytest.approx(0.0)


def test_pcm16_bytes_reject_odd_length() -> None:
    with pytest.raises(Exception):
        pcm16_bytes_to_float32(b"abc")


def test_mulaw_round_trip_preserves_length() -> None:
    samples = np.linspace(-0.8, 0.8, 64, dtype=np.float32)
    pcm = float32_to_pcm16_bytes(samples)

    encoded = pcm16_bytes_to_mulaw(pcm)
    decoded = mulaw_to_pcm16_bytes(encoded)

    assert len(encoded) == 64
    assert len(decoded) == len(pcm)


def test_alaw_round_trip_preserves_length() -> None:
    samples = np.linspace(-0.8, 0.8, 64, dtype=np.float32)
    pcm = float32_to_pcm16_bytes(samples)

    encoded = pcm16_bytes_to_alaw(pcm)
    decoded = alaw_to_pcm16_bytes(encoded)

    assert len(encoded) == 64
    assert len(decoded) == len(pcm)


def test_wav_wrap_and_extract() -> None:
    pcm = b"\x00\x00\x01\x00" * 10

    wav = pcm16_bytes_to_wav(pcm, sample_rate=16_000, channels=1)
    restored, sample_rate, channels = wav_to_pcm16_bytes(wav)

    assert restored == pcm
    assert sample_rate == 16_000
    assert channels == 1

