"""Minimal service pipeline used by the first runtime slice."""

from __future__ import annotations

from collections.abc import AsyncIterator

from polyvoice.audio.frames import AudioFrame
from polyvoice.core.events import (
    LLMChunkEvent,
    TTSAudioEvent,
    TranscriptEvent,
    VoiceEvent,
    VoiceEventType,
)
from polyvoice.services.base import ChatMessage, LLMService, STTService, TTSService


async def _single_audio_chunk(audio: bytes) -> AsyncIterator[bytes]:
    yield audio


async def _single_text_chunk(text: str) -> AsyncIterator[str]:
    yield text


class VoicePipeline:
    """Small ASR -> LLM -> TTS pipeline for mock end-to-end runtime tests."""

    def __init__(self, stt: STTService, llm: LLMService, tts: TTSService) -> None:
        self.stt = stt
        self.llm = llm
        self.tts = tts

    async def start(self) -> None:
        """Start all services."""

        await self.stt.start()
        await self.llm.start()
        await self.tts.start()

    async def stop(self) -> None:
        """Stop all services in reverse order."""

        await self.tts.stop()
        await self.llm.stop()
        await self.stt.stop()

    async def process_audio_frame(
        self,
        session_id: str,
        frame: AudioFrame,
    ) -> AsyncIterator[VoiceEvent]:
        """Process one audio frame into transcript, LLM, and TTS events."""

        async for result in self.stt.transcribe_stream(
            _single_audio_chunk(frame.audio),
            sample_rate=frame.sample_rate,
        ):
            event_type = VoiceEventType.ASR_FINAL if result.is_final else VoiceEventType.ASR_PARTIAL
            yield TranscriptEvent(
                type=event_type,
                session_id=session_id,
                text=result.text,
                confidence=result.confidence,
                start_time=result.start_time,
                end_time=result.end_time,
            )

            if not result.is_final or not result.text.strip():
                continue

            messages = [ChatMessage(role="user", content=result.text)]
            complete_text = ""
            async for chunk in self.llm.stream_chat(messages):
                complete_text += chunk.text
                yield LLMChunkEvent(
                    type=VoiceEventType.LLM_COMPLETE
                    if chunk.is_final
                    else VoiceEventType.LLM_CHUNK,
                    session_id=session_id,
                    text=complete_text if chunk.is_final else chunk.text,
                    chunk_id=chunk.chunk_id,
                    is_sentence=chunk.is_sentence_boundary,
                )

            if complete_text:
                async for tts_chunk in self.tts.synthesize_stream(
                    _single_text_chunk(complete_text)
                ):
                    yield TTSAudioEvent(
                        type=VoiceEventType.TTS_AUDIO_CHUNK,
                        session_id=session_id,
                        audio=tts_chunk.audio,
                        sample_rate=tts_chunk.sample_rate,
                        chunk_index=tts_chunk.chunk_index,
                        turn_id=1,
                    )

