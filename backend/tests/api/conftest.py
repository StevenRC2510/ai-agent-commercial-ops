"""Fixtures for the HTTP surface.

The TestClient is wired to the savepoint-isolated `db` and to a scripted LLM, so no
request ever reaches the application database or the network.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db, get_llm, get_pending_store, get_sessions
from app.application.constants import Model
from app.application.permissions import ToolName
from app.application.ports import LLMResponse
from app.config import settings
from app.domain.constants import OrderStatus
from app.infrastructure.llm.scripted import ScriptedClient
from app.infrastructure.pending.memory import InMemoryPendingActionStore
from app.infrastructure.session.memory import ConversationStore
from app.main import app

DEFAULT_REPLY = "Hay 10 ordenes pendientes."
WRITE_REASON = "el cliente confirmo el cambio"


def text_response(text: str) -> LLMResponse:
    return LLMResponse(
        stop_reason="end_turn",
        content=[{"type": "text", "text": text}],
        input_tokens=10,
        output_tokens=5,
        model=Model.HAIKU_4_5,
    )


def write_proposal(
    order_id: int, new_status: OrderStatus, input_tokens: int = 10, output_tokens: int = 5
) -> LLMResponse:
    return LLMResponse(
        stop_reason="tool_use",
        content=[
            {
                "type": "tool_use",
                "id": "tu-1",
                "name": ToolName.UPDATE_ORDER_STATUS.value,
                "input": {
                    "order_id": order_id,
                    "new_status": new_status.value,
                    "reason": WRITE_REASON,
                },
            }
        ],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=Model.HAIKU_4_5,
    )


def read_proposal(input_tokens: int = 10) -> LLMResponse:
    """A tool_use the loop will execute and come back from, so the turn keeps iterating."""
    return LLMResponse(
        stop_reason="tool_use",
        content=[
            {
                "type": "tool_use",
                "id": "tu-1",
                "name": ToolName.GET_SALES_ORDERS.value,
                "input": {},
            }
        ],
        input_tokens=input_tokens,
        output_tokens=0,
        model=Model.HAIKU_4_5,
    )


@pytest.fixture
def pending_store():
    """One store per test, shared by /chat and /confirm exactly as the singleton is."""
    return InMemoryPendingActionStore(ttl_seconds=300, clock=lambda: datetime.now(UTC))


@pytest.fixture
def sessions():
    return ConversationStore(history_max_turns=settings.history_max_turns)


@pytest.fixture
def client(db, pending_store, sessions):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_llm] = lambda: ScriptedClient([text_response(DEFAULT_REPLY)])
    app.dependency_overrides[get_pending_store] = lambda: pending_store
    app.dependency_overrides[get_sessions] = lambda: sessions
    try:
        # raise_server_exceptions=False so the global handler's response is observable.
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()
