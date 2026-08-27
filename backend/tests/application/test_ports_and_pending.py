import dataclasses
from decimal import Decimal

import pytest

from app.application.messages import DENIAL_TEXTS
from app.application.pending import PendingAction
from app.application.permissions import DenialReason, ToolName
from app.domain.actions import OrderStatusChange
from app.domain.constants import OrderStatus
from app.domain.session import ConversationSession


def _change() -> OrderStatusChange:
    return OrderStatusChange(
        order_id=1,
        from_status=OrderStatus.PENDING,
        to_status=OrderStatus.IN_PROGRESS,
        reason="el taller lo recibio",
    )


def test_state_changed_since_consent_is_a_denial_reason() -> None:
    assert DenialReason.STATE_CHANGED_SINCE_CONSENT.value == "state_changed_since_consent"


def test_every_denial_reason_still_has_a_message() -> None:
    """The new code cannot ship without its Spanish text."""
    assert {reason.value for reason in DenialReason} == {r.value for r in DENIAL_TEXTS}


def test_pending_action_is_immutable() -> None:
    action = PendingAction(
        pending_id="abc",
        session_id="s-1",
        actor="u-1",
        role="supervisor",
        tool_name=ToolName.UPDATE_ORDER_STATUS,
        safe_args={"order_id": 1},
        change=_change(),
        displayed_summary="Cambiar la orden #1...",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        action.actor = "u-2"


def test_pending_action_carries_what_consent_was_given_for() -> None:
    """ADR 0009: consent is bound to the state, so the change travels with it."""
    action = PendingAction(
        pending_id="abc",
        session_id="s-1",
        actor="u-1",
        role="supervisor",
        tool_name=ToolName.UPDATE_ORDER_STATUS,
        safe_args={"order_id": 1},
        change=_change(),
        displayed_summary="Cambiar la orden #1...",
    )
    assert action.change.from_status is OrderStatus.PENDING
    assert action.displayed_summary


def test_conversation_session_starts_empty_and_free() -> None:
    session = ConversationSession(session_id="s-1")
    assert session.history == []
    assert session.accumulated_cost_usd == Decimal("0.00")


def test_conversation_session_accumulates_cost() -> None:
    session = ConversationSession(session_id="s-1")
    session.add_cost(Decimal("0.0012"))
    session.add_cost(Decimal("0.0008"))
    assert session.accumulated_cost_usd == Decimal("0.0020")
