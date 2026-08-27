"""FastAPI dependencies, and the singletons the HTTP surface wires into the use cases.

The pending store and the conversation store are module-level on purpose: /confirm has
to find what /chat proposed, and history has to outlive a single request.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.application.messages import UNAUTHENTICATED
from app.application.permissions import ROLE_VALUES
from app.application.ports import LLMClient, PendingActionStore
from app.config import settings
from app.domain.context import AuditContext
from app.infrastructure.db import SessionLocal
from app.infrastructure.llm.anthropic import AnthropicClient
from app.infrastructure.llm.demo import DemoClient
from app.infrastructure.pending.memory import InMemoryPendingActionStore
from app.infrastructure.session.memory import ConversationStore

_pending_store = InMemoryPendingActionStore(
    ttl_seconds=settings.pending_action_ttl_seconds,
    clock=lambda: datetime.now(UTC),
)
_sessions = ConversationStore(history_max_turns=settings.history_max_turns)


def get_db() -> Iterator[Session]:
    """Provide a session. Does not commit — use cases own their transaction."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_pending_store() -> PendingActionStore:
    return _pending_store


def get_sessions() -> ConversationStore:
    return _sessions


def get_context(
    request: Request,
    x_user_id: Annotated[str | None, Header()] = None,
    x_user_role: Annotated[str | None, Header()] = None,
) -> AuditContext:
    """Identity off the wire, refused without ever naming the roles it would accept."""
    if not x_user_id or x_user_role not in ROLE_VALUES:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=UNAUTHENTICATED)
    return AuditContext(actor=x_user_id, role=x_user_role, trace_id=request.state.trace_id)


@lru_cache(maxsize=1)
def _anthropic_client() -> AnthropicClient:
    """Built once and reused: every instance opens its own HTTP connection pool."""
    return AnthropicClient(
        api_key=settings.anthropic_api_key,
        model=settings.llm_model.value,
        temperature=settings.llm_temperature,
        timeout_seconds=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_tokens,
    )


def get_llm() -> LLMClient:
    if settings.demo_mode:
        return DemoClient(model=settings.llm_model)
    return _anthropic_client()


Context = Annotated[AuditContext, Depends(get_context)]
DbSession = Annotated[Session, Depends(get_db)]
Llm = Annotated[LLMClient, Depends(get_llm)]
PendingStore = Annotated[PendingActionStore, Depends(get_pending_store)]
Sessions = Annotated[ConversationStore, Depends(get_sessions)]
