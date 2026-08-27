"""An LLMClient that answers exactly like the one it wraps, and remembers what happened.

The orchestrator logs policy decisions but not the arguments a model proposed, and tool
selection is the thing the suite measures. This is where that evidence comes from.
"""

from collections.abc import Iterator
from typing import Any

from app.application.constants import Model
from app.application.ports import LLMClient, LLMResponse
from evals.scoring import ProposedCall


def _tool_result_texts(messages: list[dict[str, Any]]) -> Iterator[str]:
    """Only what the system fed back to the model: the user's own text is not delivery."""
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                yield str(block.get("content", ""))


class RecordingClient:
    """Decorator over the LLMClient port. Adds observation, changes nothing."""

    def __init__(self, inner: LLMClient) -> None:
        self._inner = inner
        self._proposed: list[ProposedCall] = []
        self._delivered: list[str] = []
        self.input_tokens = 0
        self.output_tokens = 0
        self.model: Model | None = None

    @property
    def proposed_calls(self) -> tuple[ProposedCall, ...]:
        return tuple(self._proposed)

    def saw_in_prompt(self, needle: str) -> bool:
        return any(needle in text for text in self._delivered)

    def create(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str | None = None,
    ) -> LLMResponse:
        self._delivered.extend(_tool_result_texts(messages))
        response = self._inner.create(system=system, messages=messages, tools=tools, model=model)
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        self.model = response.model
        self._proposed.extend(
            ProposedCall(tool=block["name"], arguments=dict(block.get("input") or {}))
            for block in response.content
            if block.get("type") == "tool_use"
        )
        return response
