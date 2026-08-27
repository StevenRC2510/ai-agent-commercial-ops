"""SPEC-2 §13.1: with DEMO_MODE=true and no API key, the three flows work end to end.

Nothing here overrides the LLM dependency: the point is that the real wiring picks the
demo client, exactly as `docker compose up` does with DEMO_MODE=true.
"""

import re

import pytest

from app.api.deps import get_llm
from app.application.message_contract import enforce_message_contract
from app.config import settings
from app.domain.constants import ALLOWED_TRANSITIONS, OrderStatus
from app.domain.models import AuditLog, Client, Order
from app.infrastructure.llm.demo_constants import (
    CANDIDATES_QUESTION,
    CANDIDATES_SAMPLE_SIZE,
    CAPABILITIES_REPLY,
    MISSING_SLOT_ASKS,
    WriteSlot,
)
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


def test_a_session_that_showed_a_card_and_kept_talking_stays_a_valid_conversation(
    demo, db, seeded, sessions
):
    """DemoClient ignores message shape, so only the persisted history can prove this."""
    order = db.query(Order).filter_by(status=OrderStatus.IN_PROGRESS).first()
    demo.post(
        "/chat",
        json={"message": f"marca la orden #{order.id} como entregada", "session_id": "s-demo-mix"},
        headers=_supervisor(),
    )
    demo.post(
        "/chat",
        json={"message": "¿cuántas órdenes pendientes hay?", "session_id": "s-demo-mix"},
        headers=_supervisor(),
    )

    enforce_message_contract(sessions.get_or_create("s-demo-mix").history)


def test_a_session_longer_than_the_trim_window_stays_a_valid_conversation(demo, seeded, sessions):
    """Every turn calls a tool, so the trimmed turns are the ones that used to orphan ids."""
    for _ in range(settings.history_max_turns + 3):
        demo.post(
            "/chat",
            json={"message": "dame las ordenes pendientes", "session_id": "s-demo-long"},
            headers=_operator(),
        )

    history = sessions.get_or_create("s-demo-long").history
    # Without this the contract check below would pass on an untrimmed conversation.
    assert "tool_use" not in str(history[:2])
    enforce_message_contract(history)


def _candidate_ids(text):
    return [int(number) for number in re.findall(r"#(\d+)", text)]


def test_an_ambiguous_write_is_answered_with_orders_the_user_can_actually_choose(demo, db, seeded):
    """A bare "dime el número" asks the user to guess; the agent may look this up itself."""
    response = demo.post(
        "/chat",
        json={"message": "Cambia una orden a entregada", "session_id": "s-demo-offer"},
        headers=_supervisor(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "message"
    assert body["text"].startswith(CANDIDATES_QUESTION)
    # Two iterations: the turn really called get_sales_orders before answering.
    assert body["telemetry"]["iterations"] == 2
    offered = _candidate_ids(body["text"])
    assert 0 < len(offered) <= CANDIDATES_SAMPLE_SIZE
    for order_id in offered:
        allowed = ALLOWED_TRANSITIONS[db.get(Order, order_id).status]
        assert OrderStatus.DELIVERED in allowed


def test_the_offered_orders_are_never_ones_the_policy_would_refuse_to_change(demo, db, seeded):
    """Offering a delivered order would walk the user straight into an illegal transition."""
    settled = {order.id for order in db.query(Order).all() if not ALLOWED_TRANSITIONS[order.status]}
    assert settled, "the seed must contain settled orders for this test to discriminate"

    body = demo.post(
        "/chat",
        json={"message": "quiero cambiar una orden", "session_id": "s-demo-legal"},
        headers=_supervisor(),
    ).json()

    assert not settled & set(_candidate_ids(body["text"]))


def test_an_ambiguous_write_is_finished_by_a_bare_number_and_reaches_the_card(demo, db, seeded):
    """The demo's dead end: the model asked which order and could not read the answer."""
    asked = demo.post(
        "/chat",
        json={"message": "Cambia una orden a entregada", "session_id": "s-demo-clarify"},
        headers=_supervisor(),
    )
    assert asked.status_code == 200, asked.text
    assert asked.json()["type"] == "message"
    assert asked.json()["text"].startswith(CANDIDATES_QUESTION)
    # Answering with an offered id proves the list is a real choice, not a dead end.
    chosen = _candidate_ids(asked.json()["text"])[0]

    completed = demo.post(
        "/chat",
        json={"message": f"la {chosen}", "session_id": "s-demo-clarify"},
        headers=_supervisor(),
    )

    assert completed.status_code == 200, completed.text
    card = completed.json()
    assert card["type"] == "confirmation_required"
    assert f"#{chosen}" in card["pending_summary"]
    assert "entregada" in card["pending_summary"]
    db.expire_all()
    assert db.get(Order, chosen).status is OrderStatus.IN_PROGRESS


def test_a_follow_up_without_the_status_asks_again_instead_of_assuming_one(demo, db, seeded):
    order = db.query(Order).filter_by(status=OrderStatus.IN_PROGRESS).first()
    demo.post(
        "/chat",
        json={"message": "quiero cambiar una orden", "session_id": "s-demo-half"},
        headers=_supervisor(),
    )

    response = demo.post(
        "/chat",
        json={"message": f"la {order.id}", "session_id": "s-demo-half"},
        headers=_supervisor(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "message"
    assert body["pending_id"] is None
    assert body["text"] == MISSING_SLOT_ASKS[WriteSlot.NEW_STATUS]


def test_an_unrelated_question_after_a_clarification_still_calls_its_own_tool(demo, db, seeded):
    demo.post(
        "/chat",
        json={"message": "quiero cambiar una orden", "session_id": "s-demo-switch"},
        headers=_supervisor(),
    )
    client_row = db.query(Client).order_by(Client.id).first()

    response = demo.post(
        "/chat",
        json={
            "message": f"¿cuál es el saldo del cliente {client_row.id}?",
            "session_id": "s-demo-switch",
        },
        headers=_supervisor(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "message"
    assert client_row.name in body["text"]


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
