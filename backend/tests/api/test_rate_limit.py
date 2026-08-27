"""Per-user rate limiting on /chat: the budget, its reset, its isolation, and what it spares.

/confirm is deliberately outside the limit — see the tests at the bottom of this module.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.api.deps import get_llm
from app.application.messages import DENIAL_TEXTS
from app.application.permissions import DenialReason
from app.config import settings
from app.domain.constants import OrderStatus
from app.domain.models import Order
from app.infrastructure.llm.scripted import ScriptedClient
from app.infrastructure.ratelimit.memory import InMemoryRateLimiter
from app.main import app

from .conftest import write_proposal

_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
_BUDGET = 3
_WINDOW_SECONDS = 60


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(_NOW)


@pytest.fixture
def rate_limiter(clock):
    """Overrides the conftest limiter with a budget small enough to cross inside a test."""
    return InMemoryRateLimiter(max_requests=_BUDGET, window_seconds=_WINDOW_SECONDS, clock=clock)


def _operator(user_id: str = "u-op"):
    return {"X-User-Id": user_id, "X-User-Role": "operator"}


def _supervisor():
    return {"X-User-Id": "u-super", "X-User-Role": "supervisor"}


def _chat(client, headers, session_id: str = "s-1"):
    return client.post("/chat", json={"message": "hola", "session_id": session_id}, headers=headers)


def test_every_request_inside_the_budget_is_served(client, seeded):
    codes = [_chat(client, _operator()).status_code for _ in range(_BUDGET)]
    assert codes == [200] * _BUDGET


def test_the_request_over_the_budget_is_refused_with_429(client, seeded):
    for _ in range(_BUDGET):
        _chat(client, _operator())
    assert _chat(client, _operator()).status_code == 429


def test_the_429_body_is_the_standard_error_envelope(client, seeded):
    for _ in range(_BUDGET):
        _chat(client, _operator())
    response = _chat(client, _operator())
    body = response.json()
    assert body["type"] == "error"
    assert body["text"] == DENIAL_TEXTS[DenialReason.RATE_LIMITED]
    assert body["reason_code"] == DenialReason.RATE_LIMITED.value
    assert body["trace_id"] == response.headers["X-Trace-Id"]


def test_the_429_never_names_the_caller_it_throttled(client, seeded):
    """Consistent with the 401 and the denial texts: a refusal is never an oracle."""
    for _ in range(_BUDGET):
        _chat(client, _operator("u-secret"))
    response = _chat(client, _operator("u-secret"))
    assert "u-secret" not in response.text


def test_the_same_caller_is_served_again_once_the_window_elapses(client, seeded, clock):
    for _ in range(_BUDGET + 1):
        _chat(client, _operator())
    clock.now = _NOW + timedelta(seconds=_WINDOW_SECONDS)
    assert _chat(client, _operator()).status_code == 200


def test_two_callers_have_independent_budgets(client, seeded):
    """One caller must not be able to starve another out of the service."""
    for _ in range(_BUDGET + 1):
        _chat(client, _operator("u-noisy"))
    assert _chat(client, _operator("u-quiet")).status_code == 200


def test_a_new_session_id_does_not_buy_a_fresh_budget(client, seeded):
    """The hole being closed: the cost cap is per session, so the limit must not be."""
    for index in range(_BUDGET):
        _chat(client, _operator(), session_id=f"s-{index}")
    assert _chat(client, _operator(), session_id="s-fresh").status_code == 429


def test_an_unauthenticated_request_never_spends_anyone_budget(client, seeded):
    """Identity is resolved first, so an anonymous flood cannot lock a real caller out."""
    for _ in range(_BUDGET + 1):
        client.post("/chat", json={"message": "hola", "session_id": "s-1"})
    assert _chat(client, _operator()).status_code == 200


def test_the_limit_can_be_turned_off_without_editing_code(client, seeded, monkeypatch):
    monkeypatch.setattr(settings, "chat_rate_limit_enabled", False)
    codes = [_chat(client, _operator()).status_code for _ in range(_BUDGET + 2)]
    assert codes == [200] * (_BUDGET + 2)


def test_confirm_is_not_rate_limited(client, db):
    """It burns no tokens and needs a token only /chat can mint, so throttling it buys nothing."""
    codes = [
        client.post(
            "/confirm", json={"pending_id": "nope", "approved": True}, headers=_supervisor()
        ).status_code
        for _ in range(_BUDGET + 2)
    ]
    assert 429 not in codes


def test_a_throttled_caller_can_still_approve_the_card_it_was_already_shown(client, db, seeded):
    """Blocking this would strand a legitimate consent until it expired — worse than the abuse."""
    order = db.query(Order).filter_by(status=OrderStatus.IN_PROGRESS).first()
    app.dependency_overrides[get_llm] = lambda: ScriptedClient(
        [write_proposal(order.id, OrderStatus.DELIVERED)]
    )
    pending_id = _chat(client, _supervisor()).json()["pending_id"]
    for _ in range(_BUDGET - 1):
        _chat(client, _supervisor())
    assert _chat(client, _supervisor()).status_code == 429

    approved = client.post(
        "/confirm", json={"pending_id": pending_id, "approved": True}, headers=_supervisor()
    )
    assert approved.status_code == 200, approved.text
    db.expire_all()
    assert db.get(Order, order.id).status is OrderStatus.DELIVERED
