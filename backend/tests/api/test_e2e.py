"""SPEC-2 §13: the acceptance flows end to end, HTTP request to database row.

Every assertion here is on something a user or an auditor can see: the response body
and the rows the request left behind. Nothing inspects the objects in between.
"""

import json
from decimal import Decimal

from app.api.deps import get_llm
from app.application.permissions import DenialReason, ToolName
from app.domain.constants import OrderStatus
from app.domain.models import AuditLog, Order
from app.infrastructure.llm.scripted import ScriptedClient
from app.main import app

from .conftest import read_proposal, text_response, write_proposal

_UNTRUSTED_OPEN = "<untrusted_data>"
_UNTRUSTED_CLOSE = "</untrusted_data>"


def _operator():
    return {"X-User-Id": "u-op", "X-User-Role": "operator"}


def _supervisor():
    return {"X-User-Id": "u-super", "X-User-Role": "supervisor"}


def _last_tool_result(messages):
    blocks = messages[-1]["content"]
    return "".join(block["content"] for block in blocks if block["type"] == "tool_result")


class GroundedModel:
    """Fake model that reads the orders tool, then answers with the tool result verbatim.

    Echoing is what makes the data the model actually received observable in the HTTP body.
    """

    def __init__(self) -> None:
        self._asked = False

    def create(self, *, system, messages, tools, model=None):
        if not self._asked:
            self._asked = True
            return read_proposal()
        return text_response(_last_tool_result(messages))


def _parse_grounding(text: str) -> dict:
    """Unwrap the untrusted-data envelope the answer echoed back."""
    assert text.startswith(_UNTRUSTED_OPEN) and text.endswith(_UNTRUSTED_CLOSE), text
    return json.loads(text[len(_UNTRUSTED_OPEN) : -len(_UNTRUSTED_CLOSE)])


def test_a_read_as_operator_answers_from_the_seeded_database(client, db, seeded):
    """SPEC-2 §13.2: the tool result reaches the model and returns grounded in real rows."""
    app.dependency_overrides[get_llm] = lambda: GroundedModel()

    response = client.post(
        "/chat",
        json={"message": "dame las ordenes", "session_id": "s-e2e-read"},
        headers=_operator(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "message"
    assert body["pending_id"] is None
    assert body["telemetry"]["iterations"] == 2

    grounding = _parse_grounding(body["text"])
    seeded_orders = {order.id: order for order in db.query(Order).all()}
    assert seeded_orders, "the seed produced no orders, so the assertions below prove nothing"
    assert grounding["count"] == len(seeded_orders)
    assert {row["id"] for row in grounding["orders"]} == set(seeded_orders)
    for row in grounding["orders"]:
        order = seeded_orders[row["id"]]
        assert row["status"] == order.status.value
        assert Decimal(row["total"]) == order.total
        assert row["client_id"] == order.client_id
    newest = db.query(Order).order_by(Order.created_at.desc(), Order.id.desc()).first()
    assert grounding["orders"][0]["id"] == newest.id


def test_a_supervisor_write_is_confirmed_persisted_and_audited_verbatim(client, db, seeded):
    """SPEC-2 §13.4: card, consent, the row changes, and the audit keeps the exact sentence."""
    order = db.query(Order).filter_by(status=OrderStatus.IN_PROGRESS).first()
    app.dependency_overrides[get_llm] = lambda: ScriptedClient(
        [write_proposal(order.id, OrderStatus.DELIVERED)]
    )

    proposal = client.post(
        "/chat",
        json={"message": "marca la orden como entregada", "session_id": "s-e2e-write"},
        headers=_supervisor(),
    )

    assert proposal.status_code == 200, proposal.text
    card = proposal.json()
    assert card["type"] == "confirmation_required"
    assert card["pending_id"]
    assert card["pending_summary"] and f"#{order.id}" in card["pending_summary"]
    db.expire_all()
    assert db.get(Order, order.id).status is OrderStatus.IN_PROGRESS

    confirmed = client.post(
        "/confirm",
        json={"pending_id": card["pending_id"], "approved": True},
        headers=_supervisor(),
    )

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["type"] == "message"
    db.expire_all()
    assert db.get(Order, order.id).status is OrderStatus.DELIVERED

    row = db.query(AuditLog).filter_by(outcome="executed").one()
    assert row.action == ToolName.UPDATE_ORDER_STATUS.value
    assert row.actor == "u-super"
    assert row.args["order_id"] == order.id
    assert row.displayed_summary == card["pending_summary"]


def test_an_operator_write_is_refused_by_the_policy_before_any_card(client, db, seeded):
    """SPEC-2 §13.3: the operator is denied by policy, so consent is never even offered."""
    order = db.query(Order).filter_by(status=OrderStatus.IN_PROGRESS).first()
    app.dependency_overrides[get_llm] = lambda: ScriptedClient(
        [
            write_proposal(order.id, OrderStatus.DELIVERED),
            text_response("No tienes permiso para esa operacion."),
        ]
    )

    response = client.post(
        "/chat",
        json={"message": "marca la orden como entregada", "session_id": "s-e2e-denied"},
        headers=_operator(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "message"
    assert body["pending_id"] is None
    assert body["pending_summary"] is None
    db.expire_all()
    assert db.get(Order, order.id).status is OrderStatus.IN_PROGRESS

    denial = db.query(AuditLog).filter_by(outcome="denied").one()
    assert denial.action == ToolName.UPDATE_ORDER_STATUS.value
    assert denial.reason_code == DenialReason.ROLE_LACKS_PERMISSION.value
    assert denial.displayed_summary is None
    assert db.query(AuditLog).filter_by(outcome="executed").count() == 0


def test_a_refusal_is_distinguishable_from_an_ordinary_answer_on_the_wire(client, db, seeded):
    """Both turns are type "message"; only reason_code tells a client which one was refused."""
    order = db.query(Order).filter_by(status=OrderStatus.IN_PROGRESS).first()
    app.dependency_overrides[get_llm] = lambda: ScriptedClient(
        [
            write_proposal(order.id, OrderStatus.DELIVERED),
            text_response("Tu rol no tiene permiso para esta operación."),
        ]
    )
    refused = client.post(
        "/chat",
        json={"message": "cambia la orden a entregada", "session_id": "s-e2e-reason"},
        headers=_operator(),
    )

    app.dependency_overrides[get_llm] = lambda: ScriptedClient(
        [read_proposal(), text_response("Hay órdenes pendientes.")]
    )
    answered = client.post(
        "/chat",
        json={"message": "dame las ordenes", "session_id": "s-e2e-reason-ok"},
        headers=_operator(),
    )

    assert refused.status_code == 200, refused.text
    assert answered.status_code == 200, answered.text
    assert refused.json()["type"] == answered.json()["type"] == "message"
    assert refused.json()["reason_code"] == DenialReason.ROLE_LACKS_PERMISSION.value
    assert answered.json()["reason_code"] is None
