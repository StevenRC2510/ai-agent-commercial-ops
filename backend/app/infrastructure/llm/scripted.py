"""A fake LLMClient driven by a fixed script, for behaviour tests and DEMO_MODE."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.application.ports import LLMResponse


@dataclass(frozen=True)
class RecordedCall:
    system: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    model: str | None


class ScriptExhaustedError(RuntimeError):
    """Raised when a test calls the client more times than the script has entries."""


class ScriptedClient:
    """Plays back a fixed list of responses (or exceptions) in order, and records every call."""

    def __init__(self, responses: Sequence[LLMResponse | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[RecordedCall] = []

    def create(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str | None = None,
    ) -> LLMResponse:
        self.calls.append(RecordedCall(system=system, messages=messages, tools=tools, model=model))
        if not self._responses:
            raise ScriptExhaustedError("script ran out of responses — the caller looped too far")
        entry = self._responses.pop(0)
        if isinstance(entry, Exception):
            raise entry
        return entry
