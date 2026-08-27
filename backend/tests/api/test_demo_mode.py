"""SPEC-2 §13.1: with DEMO_MODE=true and no API key, the three flows work end to end.

Nothing here overrides the LLM dependency: the point is that the real wiring picks the
demo client, exactly as `docker compose up` does with DEMO_MODE=true.
"""

import pytest

from app.api.deps import get_llm
from app.config import settings
from app.domain.constants import OrderStatus
from app.domain.models import AuditLog, Client, Order
from app.infrastructure.llm.demo_constants import CAPABILITIES_REPLY
from app.main import app


def _operator():
    return {"X-User-Id": "u-op", "X-User-Role": "operator"}


def _supervisor():
    return {"X-User-Id": "u-super", "X-User-Role": "supervisor"}


@pytest.fixture
def demo(client, monkeypatch):
    """DEMO_MODE on, LLM override off: get_llm resolves the demo client on its own."""
    monkeypatch.setattr(settings, "demo_mode", True)
    del app.dependency_overrides[get_llm]
    return client


def test_the_read_flow_answers_with_rows_from_the_seeded_database(demo, db, seeded):
    pending = (
        db.query(Order)
        .filter_by(status=OrderStatus.PENDING)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .all()
    )

    response = demo.post(
        "/chat",
        json={"message": "¿cuántas órdenes pendientes hay?", "session_id": "s-demo-read"},
        headers=_operator(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "message"
    assert body["telemetry"]["iterations"] == 2
    assert str(len(pending)) in body["text"]
    assert f"#{pending[0].id}" in body["text"]


def test_the_balance_flow_answers_with_the_clients_real_totals(demo, db, seeded):
    client_row = db.query(Client).order_by(Client.id).first()

    response = demo.post(
        "/chat",
        json={
            "message": f"¿cuál es el saldo del cliente {client_row.id}?",
            "session_id": "s-demo-balance",
        },
        headers=_operator(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "message"
    assert body["telemetry"]["iterations"] == 2
    assert client_row.name in body["text"]


def test_the_write_flow_reaches_the_card_and_confirm_executes_it(demo, db, seeded):
    """The behaviour DEMO_MODE existed to show and could not: consent, then the write."""
    order = db.query(Order).filter_by(status=OrderStatus.IN_PROGRESS).first()

    proposal = demo.post(
        "/chat",
        json={
            "message": f"marca la orden #{order.id} como entregada",
            "session_id": "s-demo-write",
        },
        headers=_supervisor(),
    )

    assert proposal.status_code == 200, proposal.text
    card = proposal.json()
    assert card["type"] == "confirmation_required"
    assert card["pending_id"]
    assert f"#{order.id}" in card["pending_summary"]
    db.expire_all()
    assert db.get(Order, order.id).status is OrderStatus.IN_PROGRESS

    confirmed = demo.post(
        "/confirm",
        json={"pending_id": card["pending_id"], "approved": True},
        headers=_supervisor(),
    )

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["type"] == "message"
    db.expire_all()
    assert db.get(Order, order.id).status is OrderStatus.DELIVERED
    assert db.query(AuditLog).filter_by(outcome="executed").count() == 1


def test_an_operator_write_is_denied_and_the_agent_explains_it(demo, db, seeded):
    order = db.query(Order).filter_by(status=OrderStatus.IN_PROGRESS).first()

    response = demo.post(
        "/chat",
        json={"message": f"cancela la orden {order.id}", "session_id": "s-demo-denied"},
        headers=_operator(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "message"
    assert body["pending_id"] is None
    assert "permiso" in body["text"]
    db.expire_all()
    assert db.get(Order, order.id).status is OrderStatus.IN_PROGRESS


def test_an_unrecognised_message_answers_without_calling_a_tool(demo, seeded):
    response = demo.post(
        "/chat",
        json={"message": "hola, ¿qué tal?", "session_id": "s-demo-hello"},
        headers=_operator(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["text"] == CAPABILITIES_REPLY
    assert body["telemetry"]["iterations"] == 1


def test_a_second_question_in_the_same_session_still_calls_a_tool(demo, db, seeded):
    """History from the first turn must not look like a loop to the guard."""
    first = demo.post(
        "/chat",
        json={"message": "dame las ordenes pendientes", "session_id": "s-demo-multi"},
        headers=_operator(),
    )
    assert first.json()["telemetry"]["iterations"] == 2

    client_row = db.query(Client).order_by(Client.id).first()
    second = demo.post(
        "/chat",
        json={
            "message": f"¿cuál es el saldo del cliente {client_row.id}?",
            "session_id": "s-demo-multi",
        },
        headers=_operator(),
    )

    assert second.status_code == 200, second.text
    body = second.json()
    assert body["type"] == "message"
    assert body["telemetry"]["iterations"] == 2
    assert client_row.name in body["text"]
