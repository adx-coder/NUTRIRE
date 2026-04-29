"""Tests for automatic gain control."""

import numpy as np

from polyvoice.audio.agc import AutomaticGainControl, apply_agc_to_pcm16_frame
from polyvoice.audio.codecs import float32_to_pcm16_bytes, pcm16_bytes_to_float32
from polyvoice.audio.frames import AudioFrame


def test_agc_increases_quiet_voice_gain() -> None:
    agc = AutomaticGainControl()
    audio = np.full(160, 0.02, dtype=np.float32)

    result = agc.process(audio)

    assert result.rms_db < -20.0
    assert result.gain_db > 0.0
    assert np.max(np.abs(result.audio)) > np.max(np.abs(audio))


def test_agc_leaves_silence_stable() -> None:
    agc = AutomaticGainControl()

    result = agc.process(np.zeros(160, dtype=np.float32))

    assert result.rms_db == -60.0
    assert result.gain_db == 0.0
    assert np.all(result.audio == 0.0)


def test_apply_agc_to_pcm16_frame_returns_frame_and_metrics() -> None:
    agc = AutomaticGainControl()
    frame = AudioFrame(
        audio=float32_to_pcm16_bytes(np.full(160, 0.02, dtype=np.float32)),
        sample_rate=16_000,
    )

    updated, metrics = apply_agc_to_pcm16_frame(frame, agc)

    assert updated.sample_rate == 16_000
    assert updated.format == "pcm16"
    assert metrics.gain_db > 0.0
    assert np.max(np.abs(pcm16_bytes_to_float32(updated.audio))) > 0.02

