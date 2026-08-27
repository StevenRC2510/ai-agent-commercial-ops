"""RUNNER — one case, one real turn, one Observation.

Composes the same pipeline `/chat` uses, so a pass here is a claim about the deployed
system and not about a test double. The only addition is the recording decorator.
"""

import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application import tools
from app.application.agent.orchestrator import run_turn
from app.application.ports import LLMClient, PendingActionStore
from app.application.pricing import estimate_cost
from app.config import settings
from app.domain.constants import OrderStatus
from app.domain.errors import DomainError
from app.domain.models import AuditLog, Client, Order
from app.infrastructure.seed_constants import ADVERSARIAL_CLIENT_NAME
from evals.cases import EvalCase
from evals.preflight import EvalBlockedError
from evals.recording import RecordingClient
from evals.scoring import CaseRun, Observation, score

# Every audit row a case produces carries this actor, so eval traffic is never read as a user's.
EVAL_ACTOR = "eval-runner"


class EvalPreconditionError(EvalBlockedError):
    """The database cannot support the suite. Running anyway would produce noise."""


def check_preconditions(db: Session) -> None:
    """The cases name real ids and a real poisoned client; both have to be there."""
    if db.execute(select(Client.id).limit(1)).first() is None:
        raise EvalPreconditionError("The database holds no clients. Run `make reset` first.")
    poisoned = db.execute(select(Client.id).where(Client.name == ADVERSARIAL_CLIENT_NAME)).first()
    if poisoned is None:
        raise EvalPreconditionError(
            "The adversarial seed client is missing, so the injection cases would prove "
            "nothing. Run `make reset` first."
        )


def _order_statuses(db: Session, order_ids: tuple[int, ...]) -> dict[int, str]:
    if not order_ids:
        return {}
    rows = db.execute(select(Order.id, Order.status).where(Order.id.in_(order_ids))).all()
    return {row.id: OrderStatus(row.status).value for row in rows}


def _client_balances(db: Session, client_ids: tuple[int, ...]) -> dict[int, str]:
    """The grounding target, read live. A missing client simply has no expected figure."""
    balances = {}
    for client_id in client_ids:
        try:
            balances[client_id] = str(tools.get_client_balance(db, client_id)["balance"])
        except DomainError:
            continue
    return balances


def _executed_writes(db: Session, trace_id: str) -> int:
    return int(
        db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.trace_id == trace_id, AuditLog.outcome == "executed"
            )
        ).scalar_one()
    )


def run_case(
    case: EvalCase,
    *,
    db: Session,
    llm: LLMClient,
    pending_store: PendingActionStore,
    trace_id: str,
) -> CaseRun:
    """Run the case and assemble everything the scoring needs. Never raises."""
    recorder = RecordingClient(llm)
    denials: dict[str, str] = {}

    def capture(_trace: str, event: str, **fields: Any) -> None:  # noqa: ANN401 - log payload
        if event == "policy_decision" and not fields.get("allowed"):
            denials[str(fields["tool"])] = str(fields["reason"])

    before = _order_statuses(db, case.order_ids())
    started = time.monotonic()
    error = ""
    result_type, answer, reason_code = "error", "", None
    telemetry: dict[str, Any] = {}
    try:
        result = run_turn(
            user_message=case.message,
            role=case.role.value,
            actor=EVAL_ACTOR,
            session_id=f"eval-{case.id}",
            db=db,
            llm=recorder,
            trace_id=trace_id,
            pending_store=pending_store,
            log=capture,
        )
        result_type, answer, reason_code = result.type, result.text, result.reason_code
        telemetry = dict(result.telemetry or {})
    except Exception as exc:
        db.rollback()
        error = f"{type(exc).__name__}: {exc}"
    latency_ms = int((time.monotonic() - started) * 1000)

    observation = Observation(
        result_type=result_type,
        reason_code=reason_code,
        answer=answer,
        proposed_calls=recorder.proposed_calls,
        denials=denials,
        writes_executed=_executed_writes(db, trace_id),
        order_statuses_before=before,
        order_statuses_after=_order_statuses(db, case.order_ids()),
        client_balances=_client_balances(db, case.client_ids()),
        injection_delivered=recorder.saw_in_prompt(ADVERSARIAL_CLIENT_NAME),
    )
    model = recorder.model or settings.llm_model
    return CaseRun(
        outcome=score(case, observation),
        observation=observation,
        model=model,
        latency_ms=latency_ms,
        input_tokens=recorder.input_tokens,
        output_tokens=recorder.output_tokens,
        cost_usd=estimate_cost(model, recorder.input_tokens, recorder.output_tokens),
        trace_id=trace_id,
        error=error,
        telemetry=telemetry,
    )
