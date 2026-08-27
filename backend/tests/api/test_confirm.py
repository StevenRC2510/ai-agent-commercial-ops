"""/confirm: single-use consent, bound to the exact state the user was shown (ADR 0009)."""

from sqlalchemy import update

from app.api.deps import get_llm
from app.application.permissions import DenialReason
from app.domain.constants import OrderStatus
from app.domain.models import AuditLog, Order
from app.infrastructure.llm.scripted import ScriptedClient
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


def test_every_confirm_response_carries_a_trace_id(client, db, seeded):
    pending_id = _propose_a_write(client, db)
    response = client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    assert response.headers["X-Trace-Id"]
    assert response.json()["trace_id"] == response.headers["X-Trace-Id"]
