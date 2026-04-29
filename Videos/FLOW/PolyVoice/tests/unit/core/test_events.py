"""Tests for typed voice events."""

from polyvoice.core.events import (
    TranscriptEvent,
    VoiceEventType,
    error_event,
    ready_event,
)


def test_ready_event_serializes_enum_value() -> None:
    event = ready_event("session-1")

    payload = event.model_dump(mode="json")

    assert payload["type"] == "ready"
    assert payload["session_id"] == "session-1"


def test_error_event_has_message_and_code() -> None:
    event = error_event("session-1", "bad audio", code="audio.invalid")

    assert event.message == "bad audio"
    assert event.code == "audio.invalid"


def test_transcript_event_accepts_partial_and_final_types() -> None:
    partial = TranscriptEvent(
        type=VoiceEventType.ASR_PARTIAL,
        session_id="session-1",
        text="hello",
    )
    final = TranscriptEvent(
        type=VoiceEventType.ASR_FINAL,
        session_id="session-1",
        text="hello there",
        confidence=0.92,
    )

    assert partial.text == "hello"
    assert final.confidence == 0.92

