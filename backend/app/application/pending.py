"""A write awaiting consent, and the exact state it was shown against (ADR 0009)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.application.permissions import ToolName
from app.domain.actions import OrderStatusChange


@dataclass(frozen=True)
class PendingAction:
    """Carries the proposed change and what the user was shown, so consent binds to it.

    Expiry is not this type's concern: it is the pending action store's policy, kept
    alongside the action in the store, not a property of what was proposed.
    """

    pending_id: str
    session_id: str
    actor: str
    role: str
    tool_name: ToolName
    safe_args: Mapping[str, Any]
    change: OrderStatusChange
    displayed_summary: str
