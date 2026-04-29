"""SDK audio post-processing."""

from __future__ import annotations

import numpy as np

from polyvoice.audio.codecs import float32_to_pcm16_bytes, pcm16_bytes_to_float32
from polyvoice.audio.resample import Resampler
from polyvoice.services.tts_sdk.models import AudioFormat, SDKTTSChunk, TTSRequest


class AudioPipeline:
    """Normalize provider chunks to the requested output format."""

    def process_chunk(self, chunk: SDKTTSChunk, request: TTSRequest) -> SDKTTSChunk:
        """Process one provider chunk."""

        if isinstance(chunk.audio, bytes):
            if chunk.format in {AudioFormat.WAV, AudioFormat.PCM_BYTES}:
                return chunk
            audio = pcm16_bytes_to_float32(chunk.audio)
        else:
            audio = chunk.audio.astype(np.float32, copy=False)

        if len(audio) > 0 and not np.isfinite(audio).all():
            audio = np.zeros_like(audio)

        if chunk.sample_rate != request.output_sample_rate:
            audio = Resampler.resample(audio, chunk.sample_rate, request.output_sample_rate)

        if request.output_format == AudioFormat.F32:
            processed_audio: np.ndarray | bytes = audio
        elif request.output_format == AudioFormat.S16:
            processed_audio = np.frombuffer(float32_to_pcm16_bytes(audio), dtype="<i2")
        else:
            processed_audio = float32_to_pcm16_bytes(audio)

        return SDKTTSChunk(
            audio=processed_audio,
            sample_rate=request.output_sample_rate,
            format=request.output_format,
            chunk_index=chunk.chunk_index,
            is_final=chunk.is_final,
            is_segment_end=chunk.is_segment_end,
            sentence_text=chunk.sentence_text,
            metadata=dict(chunk.metadata),
        )

