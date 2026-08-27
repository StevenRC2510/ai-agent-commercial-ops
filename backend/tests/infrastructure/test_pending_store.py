from datetime import UTC, datetime, timedelta

import pytest

from app.application.pending import PendingAction
from app.application.permissions import ToolName
from app.domain.actions import OrderStatusChange
from app.domain.constants import OrderStatus
from app.infrastructure.pending.memory import (
    InMemoryPendingActionStore,
    PendingActorMismatchError,
    PendingAlreadyUsedError,
    PendingExpiredError,
    PendingNotFoundError,
)

_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _store(clock: FakeClock) -> InMemoryPendingActionStore:
    return InMemoryPendingActionStore(ttl_seconds=300, clock=clock)


def _action(store: InMemoryPendingActionStore, actor: str = "u-1") -> str:
    return store.create(
        PendingAction(
            pending_id="",
            session_id="s-1",
            actor=actor,
            role="supervisor",
            tool_name=ToolName.UPDATE_ORDER_STATUS,
            safe_args={"order_id": 1},
            change=OrderStatusChange(
                order_id=1,
                from_status=OrderStatus.PENDING,
                to_status=OrderStatus.IN_PROGRESS,
                reason="motivo valido",
            ),
            displayed_summary="Cambiar la orden #1...",
        )
    )


def test_a_created_action_can_be_consumed_once() -> None:
    clock = FakeClock(_NOW)
    store = _store(clock)
    pending_id = _action(store)
    action = store.consume(pending_id, actor="u-1", role="supervisor")
    assert action.change.to_status is OrderStatus.IN_PROGRESS


def test_the_identifier_is_opaque_and_unguessable() -> None:
    clock = FakeClock(_NOW)
    store = _store(clock)
    first = _action(store)
    second = _action(store)
    assert first != second
    assert len(first) >= 20


def test_a_second_consume_is_refused() -> None:
    """Single use: a replayed confirmation must not execute twice."""
    clock = FakeClock(_NOW)
    store = _store(clock)
    pending_id = _action(store)
    store.consume(pending_id, actor="u-1", role="supervisor")
    with pytest.raises(PendingAlreadyUsedError):
        store.consume(pending_id, actor="u-1", role="supervisor")


def test_expiry_is_tested_with_a_fake_clock_not_by_sleeping() -> None:
    clock = FakeClock(_NOW)
    store = _store(clock)
    pending_id = _action(store)
    clock.now = _NOW + timedelta(seconds=301)
    with pytest.raises(PendingExpiredError):
        store.consume(pending_id, actor="u-1", role="supervisor")


def test_an_action_survives_right_up_to_its_deadline() -> None:
    clock = FakeClock(_NOW)
    store = _store(clock)
    pending_id = _action(store)
    clock.now = _NOW + timedelta(seconds=299)
    assert store.consume(pending_id, actor="u-1", role="supervisor")


def test_another_actor_cannot_consume_it() -> None:
    clock = FakeClock(_NOW)
    store = _store(clock)
    pending_id = _action(store)
    with pytest.raises(PendingActorMismatchError):
        store.consume(pending_id, actor="u-2", role="supervisor")


def test_a_role_change_between_proposal_and_consent_is_refused() -> None:
    clock = FakeClock(_NOW)
    store = _store(clock)
    pending_id = _action(store)
    with pytest.raises(PendingActorMismatchError):
        store.consume(pending_id, actor="u-1", role="operator")


def test_an_unknown_identifier_is_refused() -> None:
    clock = FakeClock(_NOW)
    with pytest.raises(PendingNotFoundError):
        _store(clock).consume("nope", actor="u-1", role="supervisor")


def test_a_failed_consume_does_not_burn_the_action() -> None:
    """A wrong actor must not let someone destroy a pending action they do not own."""
    clock = FakeClock(_NOW)
    store = _store(clock)
    pending_id = _action(store)
    with pytest.raises(PendingActorMismatchError):
        store.consume(pending_id, actor="u-2", role="supervisor")
    assert store.consume(pending_id, actor="u-1", role="supervisor")
