"""Tests for FLOW-style LLM SDK skeleton."""

from collections.abc import AsyncIterator, Sequence
from typing import Any

from polyvoice.config.legacy import legacy_to_polyvoice_config
from polyvoice.config.recipes import select_llm_recipe
from polyvoice.services.base import ChatMessage, LLMChunk
from polyvoice.services.llm_sdk import LLMConfig, LLMStreamingSDK, SDKLLMService
from polyvoice.services.llm_sdk.clients import BaseLLMClient, register_llm_client
from polyvoice.services.llm_sdk.response_processor import ResponseProcessor
from polyvoice.services.llm_sdk.turn_coordinator import RequestPriority, TurnCoordinator


@register_llm_client("fake_llm")
class FakeLLMClient(BaseLLMClient):
    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        del tools, temperature, max_tokens
        user_text = messages[-1].content
        yield LLMChunk(text=f"Echo: {user_text}.", chunk_id=1)
        yield LLMChunk(text="", is_final=True, chunk_id=2)

    @property
    def model_name(self) -> str:
        return "fake_llm"


async def test_sdk_loads_registered_llm_client_without_core_changes() -> None:
    sdk = LLMStreamingSDK()
    await sdk.initialize(
        LLMConfig(
            clients=[
                {
                    "client": "fake_llm",
                    "name": "fake",
                }
            ],
            response_processing={"enable_sentence_detection": True},
        )
    )

    chunks = [
        chunk
        async for chunk in sdk.generate_response(
            "hello",
            client="fake",
        )
    ]
    await sdk.shutdown()

    assert chunks[0].text == "Echo: hello."
    assert chunks[0].is_sentence_boundary is True
    assert sdk.get_metrics()["requests"] == 1


async def test_sdk_llm_service_wraps_sdk_for_polyvoice_runtime() -> None:
    service = SDKLLMService(
        config=LLMConfig(
            clients=[
                {
                    "client": "fake_llm",
                    "name": "fake",
                }
            ]
        ),
        client="fake",
    )
    await service.start()

    chunks = [
        chunk
        async for chunk in service.stream_chat(
            [ChatMessage(role="user", content="hello")]
        )
    ]
    await service.stop()

    assert chunks[0].text == "Echo: hello."
    assert chunks[-1].is_final is True


def test_select_llm_recipe_activates_sdk_config() -> None:
    config = legacy_to_polyvoice_config(
        {
            "asr": {"backend": "mock"},
            "llm": {
                "backend": "mistral",
                "default_temperature": 0.3,
                "default_max_tokens": 99,
                "enable_sentence_detection": True,
                "system_prompt": "You are FLOW.",
                "available_models": {
                    "mistral_large": {
                        "backend": "mistral",
                        "endpoint_url": "https://api.mistral.ai/v1/chat/completions",
                        "model_name": "mistral-large-2411",
                    }
                },
            },
            "tts": {"backend": "mock"},
        }
    )

    selected = select_llm_recipe(config, "mistral_large")

    assert selected.llm.provider == "llm-sdk"
    assert selected.llm.model == "mistral-large-2411"
    assert selected.llm.params["client_name"] == "mistral_large"
    client = selected.llm.params["sdk_config"]["clients"][0]
    assert client["client"] == "openai_compatible"
    assert client["endpoint_url"] == "https://api.mistral.ai/v1/chat/completions"
    assert client["temperature"] == 0.3
    assert client["max_tokens"] == 99


async def test_response_processor_handles_abbreviations_and_flush() -> None:
    processor = ResponseProcessor(enable_sentence_detection=True)

    emitted = []
    async for chunk in processor.process_token("I met Dr. Smith today."):
        emitted.append(chunk)
    async for chunk in processor.flush():
        emitted.append(chunk)

    assert [chunk.text for chunk in emitted] == ["I met Dr. Smith today."]
    assert emitted[0].is_sentence_boundary is True


async def test_response_processor_filters_split_thinking_tags() -> None:
    processor = ResponseProcessor(enable_thinking_filter=True)

    emitted = []
    for token in ("<thi", "nk>hidden</think>Hello."):
        async for chunk in processor.process_token(token):
            emitted.append(chunk)

    assert [chunk.text for chunk in emitted] == ["Hello."]


def test_turn_coordinator_priority_and_partials() -> None:
    coordinator = TurnCoordinator(min_confidence=0.7)

    partial = coordinator.process_asr_transcript("hel", is_final=False, confidence=0.5)
    low = coordinator.process_asr_transcript("hello", is_final=True, confidence=0.4)
    command = coordinator.process_asr_transcript(
        "stop",
        is_final=True,
        confidence=0.9,
        metadata={"is_command": True},
    )

    assert partial.should_respond is False
    assert partial.reason == "partial"
    assert low.reason == "low_confidence"
    assert command.priority == int(RequestPriority.HIGH)
