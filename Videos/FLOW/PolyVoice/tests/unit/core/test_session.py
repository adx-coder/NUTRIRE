"""Tests for session state containers."""

from polyvoice.core.session import VoiceSessionState


def test_session_starts_and_completes_turn() -> None:
    state = VoiceSessionState(session_id="session-1")

    turn = state.start_turn()
    turn.user_speech = "hello"
    turn.assistant_response = "hi"
    completed = state.complete_turn()

    assert completed is turn
    assert state.current_turn is None
    assert state.conversation_history == [turn]


def test_interrupted_turn_is_recorded() -> None:
    state = VoiceSessionState(session_id="session-1")

    turn = state.start_turn(was_barge_in=True)
    turn.llm_interrupted = True
    state.complete_turn()

    assert state.interrupted_turns == [turn]

