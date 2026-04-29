"""OpenAI-compatible `/audio/speech` TTS service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal

import httpx

from polyvoice.core.exceptions import ServiceError
from polyvoice.services.base import TTSChunk, TTSService


class OpenAICompatibleTTS(TTSService):
    """TTS adapter for OpenAI-compatible speech endpoints."""

    name = "openai-compatible"

    def __init__(
        self,
        *,
        endpoint_url: str,
        model: str,
        api_key: str | None = None,
        voice: str = "alloy",
        response_format: Literal["pcm", "wav"] = "wav",
        sample_rate: int = 24_000,
        speed: float = 1.0,
        timeout_seconds: float = 30.0,
        extra_body: dict[str, Any] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.model = model
        self.api_key = api_key
        self.voice = voice
        self.response_format = response_format
        self.sample_rate = sample_rate
        self.speed = speed
        self.timeout_seconds = timeout_seconds
        self.extra_body = extra_body or {}
        self._client = client
        self._owns_client = client is None

    async def start(self) -> None:
        """Create an HTTP client if one was not injected."""

        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=self.timeout_seconds,
                    write=10.0,
                    pool=10.0,
                ),
            )

    async def stop(self) -> None:
        """Close the owned HTTP client."""

        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def synthesize_stream(
        self,
        text: AsyncIterator[str],
        *,
        voice: str | None = None,
        language: str | None = None,
    ) -> AsyncIterator[TTSChunk]:
        """Synthesize text chunks into audio chunks."""

        if self._client is None:
            await self.start()
        if self._client is None:
            raise ServiceError("HTTP client was not initialized")

        chunk_index = 0
        async for text_chunk in text:
            if not text_chunk:
                continue
            chunk_index += 1
            audio = await self._synthesize_once(text_chunk, voice=voice, language=language)
            yield TTSChunk(
                audio=audio,
                sample_rate=self.sample_rate,
                format="wav" if self.response_format == "wav" else "pcm16",
                chunk_index=chunk_index,
                is_final=True,
                metadata={
                    "model": self.model,
                    "voice": voice or self.voice,
                    "response_format": self.response_format,
                },
            )

    async def _synthesize_once(
        self,
        text: str,
        *,
        voice: str | None,
        language: str | None,
    ) -> bytes:
        body: dict[str, Any] = {
            "model": self.model,
            "input": text,
            "voice": voice or self.voice,
            "response_format": self.response_format,
        }
        if self.speed != 1.0:
            body["speed"] = self.speed
        if language:
            body["language"] = language
        body.update(self.extra_body)

        try:
            response = await self._client.post(self.endpoint_url, json=body)  # type: ignore[union-attr]
        except httpx.HTTPError as exc:
            raise ServiceError(f"TTS request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ServiceError(
                f"TTS endpoint returned {response.status_code}: {response.text}"
            )
        return response.content

