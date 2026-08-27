"""/chat: the conversational surface, its authentication edge and its failure envelope."""

from decimal import Decimal

from app.api.deps import get_llm
from app.application.messages import FALLBACK_BUDGET_EXCEEDED, FALLBACK_MAX_ITERATIONS
from app.config import settings
from app.domain.constants import OrderStatus
from app.domain.models import Order
from app.infrastructure.llm.scripted import ScriptedClient
from app.main import app

from .conftest import DEFAULT_REPLY, read_proposal, text_response, write_proposal

# claude-haiku-4-5 bills input at $1/M, so 500k input tokens is exactly $0.50 of one call.
_HALF_DOLLAR_TOKENS = 500_000
_HALF_DOLLAR = Decimal("0.50")
# Small enough that five of them stay under the $1 cap and the turn dies of iterations instead.
_DIME_TOKENS = 100_000
_DIME = Decimal("0.10")


def _operator():
    return {"X-User-Id": "u-op", "X-User-Role": "operator"}


def _supervisor():
    return {"X-User-Id": "u-super", "X-User-Role": "supervisor"}


def _raise(*args, **kwargs):
    raise RuntimeError("something internal broke")


def test_a_read_turn_answers_with_a_message(client, seeded):
    response = client.post(
        "/chat", json={"message": "hola", "session_id": "s-1"}, headers=_operator()
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "message"
    assert body["text"] == DEFAULT_REPLY
    assert body["pending_id"] is None


def test_a_missing_role_header_is_rejected_without_leaking_anything(client):
    response = client.post("/chat", json={"message": "hola", "session_id": "s-1"})
    assert response.status_code == 401
    assert "operator" not in response.text and "supervisor" not in response.text


def test_an_unknown_role_is_rejected_without_naming_the_valid_ones(client):
    response = client.post(
        "/chat",
        json={"message": "hola", "session_id": "s-1"},
        headers={"X-User-Id": "u-x", "X-User-Role": "admin"},
    )
    assert response.status_code == 401
    assert "operator" not in response.text and "supervisor" not in response.text


def test_a_missing_user_id_is_rejected_too(client):
    """Without an actor there is nobody to bind a future consent to."""
    response = client.post(
        "/chat", json={"message": "hola", "session_id": "s-1"}, headers={"X-User-Role": "operator"}
    )
    assert response.status_code == 401


def test_every_response_carries_a_trace_id(client, seeded):
    response = client.post(
        "/chat", json={"message": "hola", "session_id": "s-1"}, headers=_operator()
    )
    assert response.headers["X-Trace-Id"]
    assert response.json()["trace_id"] == response.headers["X-Trace-Id"]


def test_a_rejected_request_also_carries_a_trace_id(client):
    response = client.post("/chat", json={"message": "hola", "session_id": "s-1"})
    assert response.headers["X-Trace-Id"]


def test_an_unhandled_error_returns_a_generic_body_not_a_stacktrace(client, monkeypatch, seeded):
    monkeypatch.setattr("app.api.routes.chat.run_turn", _raise)
    response = client.post(
        "/chat", json={"message": "hola", "session_id": "s-1"}, headers=_operator()
    )
    assert response.status_code == 500
    assert "Traceback" not in response.text
    assert "something internal broke" not in response.text
    assert response.headers["X-Trace-Id"]


def test_the_conversation_history_survives_between_turns(client, seeded, sessions):
    app.dependency_overrides[get_llm] = lambda: ScriptedClient(
        [text_response("primera"), text_response("segunda")]
    )
    client.post("/chat", json={"message": "uno", "session_id": "s-1"}, headers=_operator())
    client.post("/chat", json={"message": "dos", "session_id": "s-1"}, headers=_operator())
    history = sessions.get_or_create("s-1").history
    assert [message["role"] for message in history] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


def test_a_turn_that_costs_money_accumulates_it_on_the_session(client, seeded, sessions):
    client.post("/chat", json={"message": "hola", "session_id": "s-1"}, headers=_operator())
    assert sessions.get_or_create("s-1").accumulated_cost_usd > 0


def test_a_confirmation_turn_bills_the_session_for_what_it_spent(client, db, seeded, sessions):
    """The write path reports no telemetry, and used to be billed as if it were free."""
    order = db.query(Order).filter_by(status=OrderStatus.IN_PROGRESS).first()
    app.dependency_overrides[get_llm] = lambda: ScriptedClient(
        [
            write_proposal(
                order.id,
                OrderStatus.DELIVERED,
                input_tokens=_HALF_DOLLAR_TOKENS,
                output_tokens=0,
            )
        ]
    )
    response = client.post(
        "/chat", json={"message": "cambia la orden", "session_id": "s-1"}, headers=_supervisor()
    )
    assert response.json()["type"] == "confirmation_required"
    assert sessions.get_or_create("s-1").accumulated_cost_usd == _HALF_DOLLAR


def test_an_error_turn_bills_the_session_for_what_it_spent(client, seeded, sessions):
    """Hitting the iteration cap still burned every call it made."""
    calls = settings.llm_max_iterations
    app.dependency_overrides[get_llm] = lambda: ScriptedClient(
        [read_proposal(input_tokens=_DIME_TOKENS)] * calls
    )
    response = client.post(
        "/chat", json={"message": "dame ordenes", "session_id": "s-1"}, headers=_operator()
    )
    body = response.json()
    assert body["type"] == "error"
    assert body["text"] == FALLBACK_MAX_ITERATIONS
    assert sessions.get_or_create("s-1").accumulated_cost_usd == _DIME * calls


def test_confirmation_only_turns_eventually_hit_the_budget_ceiling(client, db, seeded):
    """A session of nothing but confirmations must still run out of money."""
    order = db.query(Order).filter_by(status=OrderStatus.IN_PROGRESS).first()
    app.dependency_overrides[get_llm] = lambda: ScriptedClient(
        [write_proposal(order.id, OrderStatus.DELIVERED, input_tokens=_HALF_DOLLAR_TOKENS)]
    )
    texts = [
        client.post(
            "/chat", json={"message": "cambia la orden", "session_id": "s-1"}, headers=_supervisor()
        ).json()["text"]
        for _ in range(5)
    ]
    assert FALLBACK_BUDGET_EXCEEDED in texts


def test_an_operator_write_proposal_never_reaches_the_database(client, db, seeded):
    """The operator has no write tool, so the model's proposal must die in the policy."""
    order = db.query(Order).filter_by(status=OrderStatus.IN_PROGRESS).first()
    before = order.status
    app.dependency_overrides[get_llm] = lambda: ScriptedClient(
        [
            write_proposal(order.id, OrderStatus.DELIVERED),
            text_response("No tienes permiso para esa operacion."),
        ]
    )
    response = client.post(
        "/chat", json={"message": "cambia la orden", "session_id": "s-1"}, headers=_operator()
    )
    assert response.status_code == 200, response.text
    assert response.json()["type"] == "message"
    db.expire_all()
    assert db.get(Order, order.id).status is before
