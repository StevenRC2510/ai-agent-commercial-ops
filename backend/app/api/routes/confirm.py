"""POST /confirm — consent, spent once, checked against the state it was given for.

The order of the checks is SPEC-2 §8/§8.1 and ADR 0009, and it is not interchangeable.
"""

import time

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Context, DbSession, PendingStore
from app.api.schemas import ConfirmRequest, Telemetry, TurnResponse
from app.application import policy, presentation, tools
from app.application.messages import CONFIRMATION_CANCELLED, CONFIRMATION_EXECUTED
from app.application.pending import PendingAction
from app.application.permissions import DenialReason
from app.domain.context import AuditContext
from app.domain.models import Order
from app.infrastructure import obs
from app.infrastructure.pending.memory import PendingActionError

router = APIRouter(tags=["agent"])


def _telemetry(started: float) -> Telemetry:
    """This turn calls no model, so the token and iteration counts are zero, not unknown."""
    return Telemetry(
        latency_ms=int((time.monotonic() - started) * 1000),
        input_tokens=0,
        output_tokens=0,
        iterations=0,
    )


def _refuse(
    db: Session,
    response: Response,
    *,
    ctx: AuditContext,
    action: PendingAction,
    reason: str,
    started: float,
) -> TurnResponse:
    """Audit the refusal and answer with its code. Nothing is executed on this path."""
    tools.record_audit(
        db,
        ctx=ctx,
        action=action.tool_name.value,
        args=dict(action.safe_args),
        outcome="denied",
        reason_code=reason,
        displayed_summary=action.displayed_summary,
    )
    db.commit()
    obs.log(
        ctx.trace_id,
        "confirmation_denied",
        pending_id=action.pending_id,
        tool=action.tool_name.value,
        denial=reason,
    )
    response.status_code = status.HTTP_409_CONFLICT
    return TurnResponse(
        type="error",
        text=presentation.render_denial(reason),
        trace_id=ctx.trace_id,
        reason_code=reason,
        telemetry=_telemetry(started),
    )


@router.post("/confirm", response_model=TurnResponse)
def confirm(
    payload: ConfirmRequest,
    response: Response,
    ctx: Context,
    db: DbSession,
    pending_store: PendingStore,
) -> TurnResponse:
    """Consume the consent, verify the state it was given for, re-evaluate, then execute."""
    started = time.monotonic()
    try:
        action = pending_store.consume(payload.pending_id, actor=ctx.actor, role=ctx.role)
    except PendingActionError as exc:
        # The precise cause is for operators only: on the wire every unusable consent is one code.
        obs.log(
            ctx.trace_id,
            "consent_unusable",
            pending_id=payload.pending_id,
            failure=type(exc).__name__,
        )
        response.status_code = status.HTTP_409_CONFLICT
        return TurnResponse(
            type="error",
            text=presentation.render_denial(DenialReason.CONSENT_UNUSABLE.value),
            trace_id=ctx.trace_id,
            reason_code=DenialReason.CONSENT_UNUSABLE.value,
            telemetry=_telemetry(started),
        )

    if not payload.approved:
        obs.log(
            ctx.trace_id,
            "action_cancelled",
            pending_id=action.pending_id,
            tool=action.tool_name.value,
        )
        return TurnResponse(
            type="message",
            text=CONFIRMATION_CANCELLED,
            trace_id=ctx.trace_id,
            telemetry=_telemetry(started),
        )

    # ADR 0009: the user approved one transition, not merely a legal one.
    change = action.change
    current_status = db.execute(
        # Locked here, not just in the write: nothing may move the row between check and use.
        select(Order.status).where(Order.id == change.order_id).with_for_update()
    ).scalar_one_or_none()
    if current_status != change.from_status:
        return _refuse(
            db,
            response,
            ctx=ctx,
            action=action,
            reason=DenialReason.STATE_CHANGED_SINCE_CONSENT.value,
            started=started,
        )

    decision = policy.evaluate(action.tool_name.value, dict(action.safe_args), ctx.role, db)
    if not decision.allowed:
        return _refuse(
            db, response, ctx=ctx, action=action, reason=decision.reason, started=started
        )

    result = tools.update_order_status(
        db,
        change.order_id,
        change.to_status,
        change.reason,
        ctx=ctx,
        displayed_summary=action.displayed_summary,
    )
    obs.log(
        ctx.trace_id,
        "action_executed",
        pending_id=action.pending_id,
        tool=action.tool_name.value,
        **result,
    )
    return TurnResponse(
        type="message",
        text=CONFIRMATION_EXECUTED.format(summary=action.displayed_summary),
        trace_id=ctx.trace_id,
        telemetry=_telemetry(started),
    )
