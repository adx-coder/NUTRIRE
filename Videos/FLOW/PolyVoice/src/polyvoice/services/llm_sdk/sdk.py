"""FLOW-style streaming LLM SDK for PolyVoice."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

from polyvoice.core.exceptions import ServiceError
from polyvoice.services.base import ChatMessage, LLMChunk
from polyvoice.services.llm_sdk.clients import BaseLLMClient, get_llm_client
from polyvoice.services.llm_sdk.config import LLMConfig
from polyvoice.services.llm_sdk.conversation import ConversationManager
from polyvoice.services.llm_sdk.metrics import LLMMetrics
from polyvoice.services.llm_sdk.response_processor import ResponseProcessor
from polyvoice.services.llm_sdk.turn_coordinator import TurnCoordinator, TurnDecision


class LLMStreamingSDK:
    """Client/processor-pattern LLM SDK preserving the FLOW extension model."""

    def __init__(self) -> None:
        self.clients: dict[str, BaseLLMClient] = {}
        self.response_processor = ResponseProcessor()
        self.conversation = ConversationManager()
        self.turn_coordinator = TurnCoordinator()
        self.metrics = LLMMetrics()
        self.interrupted = False
        self.initialized = False

    async def initialize(self, config: LLMConfig | None = None) -> None:
        """Initialize configured LLM clients and processing components."""

        cfg = config or LLMConfig()
        processing = cfg.response_processing
        conversation = cfg.conversation
        turn = cfg.turn_coordinator
        self.response_processor = ResponseProcessor(
            chunk_size_tokens=int(processing.get("chunk_size_tokens", 8)),
            enable_sentence_detection=bool(
                processing.get("enable_sentence_detection", True)
            ),
            enable_thinking_filter=bool(processing.get("enable_thinking_filter", True)),
            enable_adaptive_chunking=bool(processing.get("enable_adaptive_chunking", True)),
        )
        self.conversation = ConversationManager(
            max_turns=int(conversation.get("max_conversation_turns", 20)),
            system_prompt=conversation.get("system_prompt"),
        )
        self.turn_coordinator = TurnCoordinator(
            min_confidence=float(turn.get("min_confidence", 0.0))
        )

        errors: list[str] = []
        for client_cfg in cfg.clients:
            client_type = str(client_cfg.get("client") or client_cfg.get("provider"))
            name = str(client_cfg.get("name") or client_cfg.get("model") or client_type)
            try:
                client_cls = get_llm_client(client_type)
                client = client_cls(client_cfg)
                await client.start()
                self.clients[name] = client
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        self.initialized = True
        if errors and not self.clients:
            raise ServiceError(f"All LLM SDK clients failed: {errors}")

    async def add_client(self, name: str, client: BaseLLMClient) -> None:
        """Add a pre-initialized client."""

        self.clients[name] = client
        self.initialized = True

    async def generate_response(
        self,
        user_input: str,
        *,
        client: str,
        session_id: str | None = None,
        priority: int = 0,
        print_output: bool = False,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Generate a response for one user input."""

        del session_id, priority, print_output
        self._check_initialized()
        llm_client = self._get_client(client)
        messages = self.conversation.build_messages([ChatMessage(role="user", content=user_input)])
        full_text = ""
        self.metrics.requests += 1
        self.interrupted = False
        async for chunk in llm_client.stream_chat(
            messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if self.interrupted:
                break
            async for processed in self.response_processor.process_chunk(chunk):
                full_text += processed.text
                self.metrics.chunks += 1
                yield processed
        if full_text:
            self.conversation.record_turn(user_input, full_text)

    def process_asr_transcript(
        self,
        transcript: str,
        *,
        is_final: bool = True,
        confidence: float | None = None,
        priority: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> TurnDecision:
        """Process one ASR transcript into a turn decision."""

        return self.turn_coordinator.process_asr_transcript(
            transcript,
            is_final=is_final,
            confidence=confidence,
            priority=priority,
            metadata=metadata,
        )

    def interrupt(self) -> None:
        """Request interruption of the active response."""

        self.interrupted = True
        self.metrics.interruptions += 1

    def set_system_prompt(self, prompt: str | None) -> None:
        """Set the active system prompt."""

        self.conversation.set_system_prompt(prompt)

    def clear_conversation_history(self) -> None:
        """Clear conversation history."""

        self.conversation.clear()

    def register_tts_feedback(self, feedback: dict[str, Any]) -> None:
        """Accept TTS feedback for API compatibility."""

        del feedback

    def get_metrics(self) -> dict[str, int]:
        """Return metrics."""

        return self.metrics.report()

    def reset_metrics(self) -> None:
        """Reset metrics."""

        self.metrics.reset()

    def get_circuit_breaker_state(self) -> dict[str, str]:
        """Return circuit-breaker placeholder state."""

        return {"state": "closed"}

    def get_conversation_summary(self) -> dict[str, int | str | None]:
        """Return conversation metadata."""

        return self.conversation.summary()

    async def shutdown(self) -> None:
        """Shutdown all clients."""

        for client in self.clients.values():
            await client.stop()
        self.clients.clear()
        self.initialized = False

    @property
    def available_clients(self) -> list[str]:
        """Return loaded client names."""

        return sorted(self.clients)

    def _check_initialized(self) -> None:
        if not self.initialized:
            raise ServiceError("LLM SDK is not initialized")

    def _get_client(self, name: str) -> BaseLLMClient:
        try:
            return self.clients[name]
        except KeyError as exc:
            available = ", ".join(sorted(self.clients)) or "(none)"
            raise ServiceError(f"LLM client '{name}' not loaded. Available: {available}") from exc
