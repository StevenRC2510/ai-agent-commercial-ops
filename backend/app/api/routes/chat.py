"""POST /chat — one conversational turn. Thin by design: the reasoning lives in run_turn."""

from dataclasses import asdict

from fastapi import APIRouter

from app.api.deps import Context, DbSession, Llm, PendingStore, Sessions
from app.api.schemas import ChatRequest, TurnResponse
from app.application.agent.orchestrator import run_turn
from app.application.session_memory import trim_history
from app.infrastructure import obs

router = APIRouter(tags=["agent"])


@router.post("/chat", response_model=TurnResponse)
def chat(
    payload: ChatRequest,
    ctx: Context,
    db: DbSession,
    llm: Llm,
    pending_store: PendingStore,
    sessions: Sessions,
) -> TurnResponse:
    """Load the conversation, run the turn, save what it appended."""
    session = sessions.get_or_create(payload.session_id)
    history = trim_history(session.history, sessions.history_max_turns)
    result = run_turn(
        user_message=payload.message,
        role=ctx.role,
        actor=ctx.actor,
        session_id=payload.session_id,
        db=db,
        llm=llm,
        trace_id=ctx.trace_id,
        pending_store=pending_store,
        log=obs.log,
        history=history,
        already_spent=session.accumulated_cost_usd,
    )
    # run_turn appends to the list it was handed, so `history` is the updated conversation.
    session.history = history
    # Billed on every turn, whatever its type: a confirmation burns tokens like any other.
    session.add_cost(result.cost_usd)
    sessions.save(session)
    fields = asdict(result)
    # Spend is server-side accounting, not part of the published response shape.
    fields.pop("cost_usd")
    return TurnResponse(**fields)
