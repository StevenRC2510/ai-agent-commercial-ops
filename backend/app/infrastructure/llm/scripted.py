"""A fake LLMClient driven by a fixed script, for behaviour tests and DEMO_MODE."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.application.message_contract import enforce_message_contract
from app.application.ports import LLMResponse


@dataclass(frozen=True)
class RecordedCall:
    system: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]


class ScriptExhaustedError(RuntimeError):
    """Raised when a test calls the client more times than the script has entries."""


class ScriptedClient:
    """Plays back a fixed list of responses (or exceptions) in order, and records every call.

    It refuses a conversation the Messages API would refuse: a double that accepts more
    than the real client turns a production 400 into a test that passes.
    """

    def __init__(self, responses: Sequence[LLMResponse | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[RecordedCall] = []

    def create(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        self.calls.append(RecordedCall(system=system, messages=messages, tools=tools))
        enforce_message_contract(messages)
        if not self._responses:
            raise ScriptExhaustedError("script ran out of responses — the caller looped too far")
        entry = self._responses.pop(0)
        if isinstance(entry, Exception):
            raise entry
        return entry
