"""Tests for audio frame helpers."""

import pytest

from polyvoice.audio.frames import AudioFrame


def test_pcm16_duration_helpers() -> None:
    frame = AudioFrame(audio=b"\x00\x00" * 160, sample_rate=16_000)

    assert frame.duration_seconds == pytest.approx(0.01)
    assert frame.duration_ms == pytest.approx(10.0)
    assert not frame.is_empty


def test_with_audio_preserves_metadata() -> None:
    frame = AudioFrame(
        audio=b"old",
        sample_rate=8_000,
        format="mulaw",
        sequence=7,
        metadata={"source": "twilio"},
    )

    updated = frame.with_audio(b"new", sample_rate=16_000, format="pcm16")

    assert updated.audio == b"new"
    assert updated.sample_rate == 16_000
    assert updated.sequence == 7
    assert updated.metadata == {"source": "twilio"}


def test_require_pcm16_mono_rejects_wrong_format() -> None:
    with pytest.raises(ValueError):
        AudioFrame(audio=b"x", format="mulaw").require_pcm16_mono()

