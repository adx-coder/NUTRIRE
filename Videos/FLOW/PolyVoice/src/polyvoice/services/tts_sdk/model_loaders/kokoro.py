"""Kokoro TTS model loader.

Kokoro is an 82M parameter TTS model that emits 24 kHz float audio.
The dependency is imported lazily so the core package remains lightweight.
"""

from __future__ import annotations

import asyncio
import gc
from collections.abc import AsyncIterator
from typing import Any

import numpy as np

from polyvoice.core.exceptions import ServiceError
from polyvoice.services.tts_sdk.model_loaders.base import BaseModelLoader
from polyvoice.services.tts_sdk.model_loaders.registry import register_model_loader
from polyvoice.services.tts_sdk.models import TTSCapability, TTSRequest, VoiceInfo

_SENTINEL = object()

_LANG_MAP: dict[str, str] = {
    "en": "a",
    "en-us": "a",
    "en-gb": "b",
    "es": "e",
    "fr": "f",
    "hi": "h",
    "it": "i",
    "ja": "j",
    "pt": "p",
    "pt-br": "p",
    "zh": "z",
}

_DEFAULT_VOICES: dict[str, str] = {
    "a": "af_heart",
    "b": "bf_emma",
    "e": "ef_dora",
    "f": "ff_siwis",
    "h": "hf_alpha",
    "i": "if_sara",
    "j": "jf_alpha",
    "p": "pf_dora",
    "z": "zf_xiaobei",
}


def _next_or_sentinel(iterator: Any) -> Any:
    """Return next item, or a sentinel when the sync generator is exhausted."""

    try:
        return next(iterator)
    except StopIteration:
        return _SENTINEL


@register_model_loader("kokoro")
class KokoroLoader(BaseModelLoader):
    """Loads Kokoro TTS for local in-process inference."""

    CAPABILITIES = {
        TTSCapability.SENTENCE_STREAMING,
        TTSCapability.BATCH,
        TTSCapability.VOICE_SELECT,
        TTSCapability.SPEED_CONTROL,
    }

    def __init__(self) -> None:
        self._pipeline: Any = None
        self._lang_code = "a"

    async def load(self, config: dict) -> None:
        """Load Kokoro's KPipeline lazily."""

        try:
            from kokoro import KPipeline
        except ImportError as exc:
            raise ServiceError(
                "Kokoro TTS requires optional dependency kokoro. "
                "Install with `pip install kokoro soundfile` or the kokoro extra."
            ) from exc

        language = str(config.get("language", config.get("default_language", "en")))
        self._lang_code = _LANG_MAP.get(language.lower(), language)
        device = str(config.get("device", "cuda"))
        repo_id = str(config.get("repo_id", "hexgrad/Kokoro-82M"))

        if device == "cuda":
            await self._sync_cuda_before_load()

        self._pipeline = await asyncio.to_thread(
            KPipeline,
            lang_code=self._lang_code,
            device=device,
            repo_id=repo_id,
        )

    async def synthesize(self, text: str, request: TTSRequest) -> tuple[np.ndarray, int]:
        """Synthesize complete text into one audio array."""

        chunks = [chunk async for chunk in self.synthesize_stream(text, request)]
        if not chunks:
            return np.array([], dtype=np.float32), self.native_sample_rate
        audio = np.concatenate([chunk for chunk, _sample_rate in chunks])
        return audio.astype(np.float32, copy=False), self.native_sample_rate

    async def synthesize_stream(
        self,
        text: str,
        request: TTSRequest,
    ) -> AsyncIterator[tuple[np.ndarray, int]]:
        """Stream audio chunks from Kokoro's sync generator."""

        if self._pipeline is None:
            raise ServiceError("Kokoro TTS model is not loaded")

        voice = self._resolve_voice(request)
        gen = await asyncio.to_thread(
            self._pipeline.__call__,
            text,
            voice=voice,
            speed=request.speed,
        )

        while True:
            result = await asyncio.to_thread(_next_or_sentinel, gen)
            if result is _SENTINEL:
                break

            _graphemes, _phonemes, audio = result
            if audio is None or len(audio) == 0:
                continue
            if not isinstance(audio, np.ndarray):
                audio = np.array(audio, dtype=np.float32)
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
            yield audio, self.native_sample_rate

    async def unload(self) -> None:
        """Release model resources."""

        if self._pipeline is not None:
            pipeline = self._pipeline
            self._pipeline = None
            del pipeline
            gc.collect()
            gc.collect()
            await asyncio.sleep(0.1)

    @property
    def native_sample_rate(self) -> int:
        return 24_000

    @property
    def loader_name(self) -> str:
        return "kokoro"

    def get_voices(self) -> list[VoiceInfo]:
        """Return Kokoro default voices by language code."""

        return [
            VoiceInfo(
                voice_id=voice_id,
                name=voice_id,
                language=lang_code,
                metadata={"description": f"Kokoro default voice for lang={lang_code}"},
            )
            for lang_code, voice_id in _DEFAULT_VOICES.items()
        ]

    def _resolve_voice(self, request: TTSRequest) -> str:
        if request.voice:
            return request.voice
        lang = (request.language or self._lang_code).lower()
        lang_code = _LANG_MAP.get(lang, self._lang_code)
        return _DEFAULT_VOICES.get(lang_code, "af_heart")

    async def _sync_cuda_before_load(self) -> None:
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.synchronize()
                await asyncio.sleep(0.2)
        except Exception:
            return
