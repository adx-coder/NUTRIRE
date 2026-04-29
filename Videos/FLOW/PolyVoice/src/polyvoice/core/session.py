"""Session and turn state for PolyVoice orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class VoiceTurn:
    """Represents one user-assistant voice turn."""

    turn_id: int
    session_id: str
    user_speech: str = ""
    assistant_response: str = ""
    asr_start_time: float = 0.0
    asr_end_time: float = 0.0
    llm_start_time: float = 0.0
    llm_end_time: float = 0.0
    asr_interrupted: bool = False
    llm_interrupted: bool = False
    was_barge_in: bool = False
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def complete(self) -> None:
        """Mark this turn as completed now."""

        self.completed_at = time.time()


@dataclass(slots=True)
class VoiceSessionState:
    """Mutable state for a single voice session."""

    session_id: str
    current_turn_id: int = 0
    current_turn: VoiceTurn | None = None
    conversation_history: list[VoiceTurn] = field(default_factory=list)
    interrupted_turns: list[VoiceTurn] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def start_turn(self, *, was_barge_in: bool = False) -> VoiceTurn:
        """Create and set the next active turn."""

        self.current_turn_id += 1
        self.current_turn = VoiceTurn(
            turn_id=self.current_turn_id,
            session_id=self.session_id,
            was_barge_in=was_barge_in,
        )
        return self.current_turn

    def complete_turn(self) -> VoiceTurn | None:
        """Complete and archive the active turn if one exists."""

        if self.current_turn is None:
            return None
        self.current_turn.complete()
        if self.current_turn.llm_interrupted or self.current_turn.asr_interrupted:
            self.interrupted_turns.append(self.current_turn)
        self.conversation_history.append(self.current_turn)
        completed = self.current_turn
        self.current_turn = None
        return completed

    def reset(self) -> None:
        """Clear turn state and conversation history."""

        self.current_turn_id = 0
        self.current_turn = None
        self.conversation_history.clear()
        self.interrupted_turns.clear()

