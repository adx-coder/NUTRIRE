"""Audio sample and byte-format conversion helpers."""

from __future__ import annotations

import io
import wave

import numpy as np

from polyvoice.core.exceptions import AudioError

MU_LAW_MAX = 32635.0
MU = 255.0
A_LAW_MAX = 32767.0
A_LAW_A = 87.6


def float32_to_pcm16(audio: np.ndarray) -> np.ndarray:
    """Convert float audio in ``[-1.0, 1.0]`` to little-endian int16 samples."""

    return (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2")


def pcm16_to_float32(audio: np.ndarray) -> np.ndarray:
    """Convert int16 samples to float32 audio in approximately ``[-1.0, 1.0]``."""

    return audio.astype(np.float32) / 32768.0


def pcm16_bytes_to_float32(data: bytes) -> np.ndarray:
    """Decode raw little-endian PCM16 bytes into float32 samples."""

    if len(data) % 2:
        raise AudioError("PCM16 byte length must be even")
    return pcm16_to_float32(np.frombuffer(data, dtype="<i2"))


def float32_to_pcm16_bytes(audio: np.ndarray) -> bytes:
    """Encode float32 samples as raw little-endian PCM16 bytes."""

    return float32_to_pcm16(audio).tobytes()


def pcm16_bytes_to_mulaw(data: bytes) -> bytes:
    """Encode raw PCM16 bytes as 8-bit mu-law bytes."""

    samples = np.frombuffer(data, dtype="<i2").astype(np.float32)
    normalized = np.clip(samples / MU_LAW_MAX, -1.0, 1.0)
    magnitude = np.log1p(MU * np.abs(normalized)) / np.log1p(MU)
    encoded = np.sign(normalized) * magnitude
    return ((encoded + 1.0) * 127.5).astype(np.uint8).tobytes()


def mulaw_to_pcm16_bytes(data: bytes) -> bytes:
    """Decode 8-bit mu-law bytes into raw PCM16 bytes."""

    encoded = np.frombuffer(data, dtype=np.uint8).astype(np.float32) / 127.5 - 1.0
    magnitude = (np.expm1(np.abs(encoded) * np.log1p(MU)) / MU) * MU_LAW_MAX
    samples = np.sign(encoded) * magnitude
    return np.clip(samples, -32768, 32767).astype("<i2").tobytes()


def pcm16_bytes_to_alaw(data: bytes) -> bytes:
    """Encode raw PCM16 bytes as 8-bit A-law bytes."""

    samples = np.frombuffer(data, dtype="<i2").astype(np.float32)
    normalized = np.clip(samples / A_LAW_MAX, -1.0, 1.0)
    abs_x = np.abs(normalized)
    compressed = np.where(
        abs_x < (1.0 / A_LAW_A),
        (A_LAW_A * abs_x) / (1.0 + np.log(A_LAW_A)),
        (1.0 + np.log(A_LAW_A * abs_x)) / (1.0 + np.log(A_LAW_A)),
    )
    encoded = np.sign(normalized) * compressed
    return ((encoded + 1.0) * 127.5).astype(np.uint8).tobytes()


def alaw_to_pcm16_bytes(data: bytes) -> bytes:
    """Decode 8-bit A-law bytes into raw PCM16 bytes."""

    encoded = np.frombuffer(data, dtype=np.uint8).astype(np.float32) / 127.5 - 1.0
    abs_y = np.abs(encoded)
    expanded = np.where(
        abs_y < (1.0 / (1.0 + np.log(A_LAW_A))),
        abs_y * (1.0 + np.log(A_LAW_A)) / A_LAW_A,
        np.exp(abs_y * (1.0 + np.log(A_LAW_A)) - 1.0) / A_LAW_A,
    )
    samples = np.sign(encoded) * expanded * A_LAW_MAX
    return np.clip(samples, -32768, 32767).astype("<i2").tobytes()


def pcm16_bytes_to_wav(data: bytes, *, sample_rate: int, channels: int = 1) -> bytes:
    """Wrap raw PCM16 bytes in a WAV container."""

    if channels <= 0 or sample_rate <= 0:
        raise AudioError("WAV sample rate and channels must be positive")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(data)
    return buffer.getvalue()


def wav_to_pcm16_bytes(data: bytes) -> tuple[bytes, int, int]:
    """Extract raw PCM16 bytes, sample rate, and channels from a WAV payload."""

    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            if wav.getsampwidth() != 2:
                raise AudioError("Only 16-bit PCM WAV is supported")
            return wav.readframes(wav.getnframes()), wav.getframerate(), wav.getnchannels()
    except wave.Error as exc:
        raise AudioError("Invalid WAV payload") from exc

