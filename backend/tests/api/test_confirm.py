"""/confirm: single-use consent, bound to the exact state the user was shown (ADR 0009)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.api.deps import get_llm, get_pending_store
from app.application.messages import DENIAL_TEXTS
from app.application.permissions import DenialReason
from app.domain.constants import OrderStatus
from app.domain.models import AuditLog, Order
from app.infrastructure.llm.scripted import ScriptedClient
from app.infrastructure.pending.memory import InMemoryPendingActionStore
from app.main import app

from .conftest import write_proposal


def _supervisor():
    return {"X-User-Id": "u-super", "X-User-Role": "supervisor"}


def _propose(client, db, *, from_status: OrderStatus, to_status: OrderStatus):
    """Drives a real /chat turn to the confirmation card, returning the order and its token."""
    order = db.query(Order).filter_by(status=from_status).first()
    app.dependency_overrides[get_llm] = lambda: ScriptedClient(
        [write_proposal(order.id, to_status)]
    )
    response = client.post(
        "/chat", json={"message": "cambia el estado", "session_id": "s-1"}, headers=_supervisor()
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "confirmation_required"
    return order.id, body


def _propose_a_write_returning_order(client, db):
    order_id, body = _propose(
        client, db, from_status=OrderStatus.IN_PROGRESS, to_status=OrderStatus.DELIVERED
    )
    return order_id, body["pending_id"]


def _propose_a_write(client, db):
    return _propose_a_write_returning_order(client, db)[1]


def _change_status_by_another_route(db, order_id: int, new_status: OrderStatus) -> None:
    db.execute(update(Order).where(Order.id == order_id).values(status=new_status))
    db.commit()


def _executed_rows(db):
    return db.query(AuditLog).filter_by(outcome="executed").count()


def _event(logged, name):
    """The fields of the first event with this name, so a missing one fails loudly."""
    return next(fields for event, fields in logged if event == name)


def test_approving_executes_and_audits_exactly_once(client, db, seeded):
    pending_id = _propose_a_write(client, db)
    response = client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    assert response.status_code == 200
    assert db.query(AuditLog).filter_by(outcome="executed").count() == 1


def test_approving_persists_the_new_status(client, db, seeded):
    order_id, pending_id = _propose_a_write_returning_order(client, db)
    client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    db.expire_all()
    assert db.get(Order, order_id).status is OrderStatus.DELIVERED


def test_the_audit_row_records_the_exact_sentence_consented_to(client, db, seeded):
    order_id, body = _propose(
        client, db, from_status=OrderStatus.IN_PROGRESS, to_status=OrderStatus.DELIVERED
    )
    client.post(
        "/confirm",
        json={"pending_id": body["pending_id"], "approved": True},
        headers=_supervisor(),
    )
    row = db.query(AuditLog).filter_by(outcome="executed").one()
    assert row.displayed_summary == body["pending_summary"]


def test_cancelling_changes_nothing(client, db, seeded):
    order_id, pending_id = _propose_a_write_returning_order(client, db)
    before = db.get(Order, order_id).status
    client.post(
        "/confirm", json={"pending_id": pending_id, "approved": False}, headers=_supervisor()
    )
    db.expire_all()
    assert db.get(Order, order_id).status is before
    assert db.query(AuditLog).filter_by(outcome="executed").count() == 0


def test_a_replayed_confirmation_does_not_execute_twice(client, db, seeded):
    pending_id = _propose_a_write(client, db)
    client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    second = client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    assert second.status_code in (400, 409)
    assert db.query(AuditLog).filter_by(outcome="executed").count() == 1


def test_a_cancelled_token_cannot_be_replayed_into_an_execution(client, db, seeded):
    pending_id = _propose_a_write(client, db)
    client.post(
        "/confirm", json={"pending_id": pending_id, "approved": False}, headers=_supervisor()
    )
    second = client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    assert second.status_code in (400, 409)
    assert _executed_rows(db) == 0


def test_a_state_change_between_proposal_and_consent_is_refused(client, db, seeded):
    """ADR 0009: the user approved a specific transition, not merely a legal one."""
    order_id, pending_id = _propose_a_write_returning_order(client, db)
    _change_status_by_another_route(db, order_id, OrderStatus.CANCELLED)
    response = client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    assert response.status_code in (400, 409)
    body = response.json()
    assert "state_changed_since_consent" in str(body) or "cambió de estado" in str(body)
    assert db.query(AuditLog).filter_by(outcome="executed").count() == 0


def test_a_still_legal_transition_from_another_state_is_refused_all_the_same(client, db, seeded):
    """The guard must bite where re-running policy.evaluate alone would allow the write."""
    order_id, body = _propose(
        client, db, from_status=OrderStatus.PENDING, to_status=OrderStatus.CANCELLED
    )
    _change_status_by_another_route(db, order_id, OrderStatus.IN_PROGRESS)
    response = client.post(
        "/confirm",
        json={"pending_id": body["pending_id"], "approved": True},
        headers=_supervisor(),
    )
    assert response.status_code == 409
    assert response.json()["reason_code"] == DenialReason.STATE_CHANGED_SINCE_CONSENT.value
    db.expire_all()
    assert db.get(Order, order_id).status is OrderStatus.IN_PROGRESS
    assert _executed_rows(db) == 0


def test_a_refused_consent_is_audited_as_denied(client, db, seeded):
    order_id, pending_id = _propose_a_write_returning_order(client, db)
    _change_status_by_another_route(db, order_id, OrderStatus.CANCELLED)
    client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    denied = db.query(AuditLog).filter_by(
        outcome="denied", reason_code=DenialReason.STATE_CHANGED_SINCE_CONSENT.value
    )
    assert denied.count() == 1


def test_a_confirmation_from_another_actor_is_refused(client, db, seeded):
    pending_id = _propose_a_write(client, db)
    response = client.post(
        "/confirm",
        json={"pending_id": pending_id, "approved": True},
        headers={"X-User-Id": "u-other", "X-User-Role": "supervisor"},
    )
    assert response.status_code == 409
    assert _executed_rows(db) == 0


def test_an_unknown_pending_id_is_refused_without_a_stacktrace(client, db, seeded):
    response = client.post(
        "/confirm", json={"pending_id": "does-not-exist", "approved": True}, headers=_supervisor()
    )
    assert response.status_code == 409
    assert "Traceback" not in response.text
    assert _executed_rows(db) == 0


def test_confirming_without_a_role_header_is_rejected(client, db, seeded):
    pending_id = _propose_a_write(client, db)
    response = client.post("/confirm", json={"pending_id": pending_id, "approved": True})
    assert response.status_code == 401
    assert _executed_rows(db) == 0


def test_an_unusable_consent_is_refused_with_a_machine_readable_code(client, db, seeded):
    """A client must never have to branch on Spanish prose to tell why it was refused."""
    pending_id = _propose_a_write(client, db)
    client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    replay = client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    assert replay.status_code == 409
    assert replay.json()["reason_code"] == DenialReason.CONSENT_UNUSABLE.value
    assert replay.json()["text"] == DENIAL_TEXTS[DenialReason.CONSENT_UNUSABLE]


def test_an_unknown_an_expired_and_a_replayed_consent_are_indistinguishable(client, db, seeded):
    """Telling them apart would reveal whether an opaque identifier ever existed."""
    now = [datetime(2026, 6, 15, tzinfo=UTC)]
    store = InMemoryPendingActionStore(ttl_seconds=300, clock=lambda: now[0])
    app.dependency_overrides[get_pending_store] = lambda: store

    expired_id = _propose_a_write(client, db)
    replayed_id = _propose_a_write(client, db)
    client.post(
        "/confirm", json={"pending_id": replayed_id, "approved": True}, headers=_supervisor()
    )
    now[0] += timedelta(seconds=301)

    answers = [
        client.post(
            "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
        )
        for pending_id in (expired_id, replayed_id, "this-id-was-never-issued")
    ]
    shapes = {(r.status_code, r.json()["reason_code"], r.json()["text"]) for r in answers}
    assert shapes == {
        (
            409,
            DenialReason.CONSENT_UNUSABLE.value,
            DENIAL_TEXTS[DenialReason.CONSENT_UNUSABLE],
        )
    }


def test_the_pending_id_joins_the_proposal_trace_to_the_execution_trace(client, db, seeded, logged):
    """Each HTTP request mints its own trace_id, so the pending_id is the only clean join."""
    pending_id = _propose_a_write(client, db)
    client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    proposal = _event(logged, "confirmation_required")
    execution = _event(logged, "action_executed")
    assert proposal["pending_id"] == execution["pending_id"] == pending_id
    assert proposal["trace_id"] != execution["trace_id"]


def test_a_cancellation_logs_the_pending_id_it_cancelled(client, db, seeded, logged):
    pending_id = _propose_a_write(client, db)
    client.post(
        "/confirm", json={"pending_id": pending_id, "approved": False}, headers=_supervisor()
    )
    assert _event(logged, "action_cancelled")["pending_id"] == pending_id


def test_a_denied_confirmation_logs_the_pending_id_it_denied(client, db, seeded, logged):
    order_id, pending_id = _propose_a_write_returning_order(client, db)
    _change_status_by_another_route(db, order_id, OrderStatus.CANCELLED)
    client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    assert _event(logged, "confirmation_denied")["pending_id"] == pending_id


def test_an_unusable_consent_logs_the_identifier_that_was_offered(client, db, seeded, logged):
    """The operator gets the precise cause and the id; the caller gets neither."""
    client.post(
        "/confirm", json={"pending_id": "does-not-exist", "approved": True}, headers=_supervisor()
    )
    event = _event(logged, "consent_unusable")
    assert event["pending_id"] == "does-not-exist"
    assert event["failure"] == "PendingNotFoundError"


@pytest.mark.parametrize("approved", [True, False])
def test_a_confirm_turn_reports_telemetry_with_no_model_tokens(client, db, seeded, approved):
    """Latency is real; the token counts are zero because no model call happened."""
    pending_id = _propose_a_write(client, db)
    telemetry = client.post(
        "/confirm", json={"pending_id": pending_id, "approved": approved}, headers=_supervisor()
    ).json()["telemetry"]
    assert telemetry["input_tokens"] == 0
    assert telemetry["output_tokens"] == 0
    assert telemetry["iterations"] == 0
    assert telemetry["latency_ms"] >= 0


def test_a_refused_confirmation_reports_telemetry_too(client, db, seeded):
    order_id, pending_id = _propose_a_write_returning_order(client, db)
    _change_status_by_another_route(db, order_id, OrderStatus.CANCELLED)
    refused = client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    assert refused.json()["telemetry"]["iterations"] == 0


def test_an_unusable_consent_reports_telemetry_too(client, db, seeded):
    refused = client.post(
        "/confirm", json={"pending_id": "does-not-exist", "approved": True}, headers=_supervisor()
    )
    assert refused.json()["telemetry"]["iterations"] == 0


def test_every_confirm_response_carries_a_trace_id(client, db, seeded):
    pending_id = _propose_a_write(client, db)
    response = client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    assert response.headers["X-Trace-Id"]
    assert response.json()["trace_id"] == response.headers["X-Trace-Id"]
