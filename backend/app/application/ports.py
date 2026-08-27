"""The two ports SPEC 2 introduces. Each has a second implementation from day one."""

from dataclasses import dataclass
from typing import Any, Protocol

from app.application.constants import Model
from app.application.pending import PendingAction


@dataclass(frozen=True)
class LLMResponse:
    stop_reason: str
    content: list[dict[str, Any]]
    input_tokens: int
    output_tokens: int
    model: Model
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


class LLMClient(Protocol):
    def create(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str | None = None,
    ) -> LLMResponse: ...


class PendingActionStore(Protocol):
    def create(self, action: PendingAction) -> str: ...
    def consume(self, pending_id: str, *, actor: str, role: str) -> PendingAction: ...
