"""Per-conversation state: what was said and what it has cost so far."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class ConversationSession:
    session_id: str
    history: list[dict[str, Any]] = field(default_factory=list)
    accumulated_cost_usd: Decimal = Decimal("0.00")

    def add_cost(self, amount: Decimal) -> None:
        self.accumulated_cost_usd += amount
