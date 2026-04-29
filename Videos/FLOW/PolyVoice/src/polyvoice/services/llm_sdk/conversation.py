"""Small conversation manager matching the old SDK boundary."""

from __future__ import annotations

from collections.abc import Sequence

from polyvoice.services.base import ChatMessage


class ConversationManager:
    """Tracks rolling conversation history."""

    def __init__(self, *, max_turns: int = 20, system_prompt: str | None = None) -> None:
        self.max_turns = max_turns
        self.system_prompt = system_prompt
        self.history: list[ChatMessage] = []

    def build_messages(self, messages: Sequence[ChatMessage]) -> list[ChatMessage]:
        """Return system prompt, history, and current messages."""

        built: list[ChatMessage] = []
        if self.system_prompt:
            built.append(ChatMessage(role="system", content=self.system_prompt))
        built.extend(self.history)
        built.extend(messages)
        return built

    def record_turn(self, user_text: str, assistant_text: str) -> None:
        """Append one user/assistant turn."""

        self.history.extend(
            [
                ChatMessage(role="user", content=user_text),
                ChatMessage(role="assistant", content=assistant_text),
            ]
        )
        max_messages = max(0, self.max_turns * 2)
        if max_messages:
            self.history = self.history[-max_messages:]

    def set_system_prompt(self, prompt: str | None) -> None:
        """Set the active system prompt."""

        self.system_prompt = prompt

    def clear(self) -> None:
        """Clear conversation history."""

        self.history.clear()

    def summary(self) -> dict[str, int | str | None]:
        """Return lightweight history metadata."""

        return {"turns": len(self.history) // 2, "system_prompt": self.system_prompt}
