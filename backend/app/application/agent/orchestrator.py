"""ORCHESTRATOR — proposes; never decides. Every `tool_use` block goes through
`policy.evaluate()` before anything happens, and its verdict is obeyed without exception.
"""

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.application import policy, presentation, tools
from app.application.agent.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from app.application.agent.tool_schemas import tool_schemas_for
from app.application.constants import PERSONAL_FIELDS
from app.application.messages import (
    FALLBACK_BUDGET_EXCEEDED,
    FALLBACK_INPUT_TOO_LONG,
    FALLBACK_LLM_ERROR,
    FALLBACK_MAX_ITERATIONS,
)
from app.application.pending import PendingAction
from app.application.permissions import ToolName
from app.application.ports import LLMClient, PendingActionStore
from app.application.pricing import estimate_cost
from app.application.session_memory import trim_history
from app.application.tool_args import TOOL_SCHEMAS, GetClientBalanceArgs, GetSalesOrdersArgs
from app.config import settings
from app.domain.context import AuditContext
from app.domain.errors import DomainError

LogFn = Callable[..., None]
JSONValue = dict[str, "JSONValue"] | list["JSONValue"] | str | int | float | bool | None

_ZERO_COST = Decimal("0.00")


@dataclass(frozen=True)
class TurnResult:
    """`cost_usd` is what THIS turn spent, and it has no default on purpose.

    Telemetry only exists for a turn that reached a final message; billing must not
    depend on how the turn ended, so a missing cost fails construction instead.
    """

    type: Literal["message", "confirmation_required", "error"]
    text: str
    trace_id: str
    cost_usd: Decimal
    pending_id: str | None = None
    pending_summary: str | None = None
    telemetry: dict[str, Any] | None = None


def wrap_untrusted(payload: dict[str, JSONValue]) -> str:
    """Marks tool output as data, never instruction, before it reaches the model."""
    body = json.dumps(payload, ensure_ascii=False, default=str)
    return f"<untrusted_data>\n{body}\n</untrusted_data>"


def strip_personal_fields(payload: dict[str, JSONValue]) -> dict[str, JSONValue]:
    """Recursively drops personal identifiers the model does not need to answer (SPEC-2 §6.1)."""
    return {key: _strip(value) for key, value in payload.items() if key not in PERSONAL_FIELDS}


def _strip(value: JSONValue) -> JSONValue:
    if isinstance(value, dict):
        return {key: _strip(v) for key, v in value.items() if key not in PERSONAL_FIELDS}
    if isinstance(value, list):
        return [_strip(item) for item in value]
    return value


def _sha8(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:8]


def _extract_text(content: list[dict[str, Any]]) -> str:
    return "".join(block.get("text", "") for block in content if block.get("type") == "text")


def _run_read_tool(
    tool: ToolName, safe_args: Mapping[str, Any] | None, db: Session
) -> dict[str, Any]:
    schema = TOOL_SCHEMAS[tool]
    args = schema(**dict(safe_args or {}))
    if tool is ToolName.GET_SALES_ORDERS and isinstance(args, GetSalesOrdersArgs):
        return tools.get_sales_orders(
            db,
            status=args.status,
            date_from=args.date_from,
            date_to=args.date_to,
            client_id=args.client_id,
            limit=args.limit,
        )
    if tool is ToolName.GET_CLIENT_BALANCE and isinstance(args, GetClientBalanceArgs):
        return tools.get_client_balance(db, client_id=args.client_id)
    raise AssertionError(f"{tool.value} requires confirmation and must never execute directly")


def _confirmation_result(
    decision: policy.PolicyDecision,
    *,
    session_id: str,
    actor: str,
    role: str,
    tool_name: str,
    trace_id: str,
    store: PendingActionStore,
    log_fn: LogFn,
    cost_usd: Decimal,
) -> TurnResult:
    if decision.change is None:
        raise AssertionError("requires_confirmation implies policy set a change")
    summary = presentation.render_summary(decision.change)
    action = PendingAction(
        pending_id="",
        session_id=session_id,
        actor=actor,
        role=role,
        tool_name=ToolName(tool_name),
        safe_args=decision.safe_args or {},
        change=decision.change,
        displayed_summary=summary,
    )
    pending_id = store.create(action)
    log_fn(trace_id, "confirmation_required", pending_id=pending_id, tool=tool_name)
    return TurnResult(
        type="confirmation_required",
        text=summary,
        trace_id=trace_id,
        cost_usd=cost_usd,
        pending_id=pending_id,
        pending_summary=summary,
    )


def run_turn(
    *,
    user_message: str,
    role: str,
    actor: str,
    session_id: str,
    db: Session,
    llm: LLMClient,
    trace_id: str,
    pending_store: PendingActionStore,
    log: LogFn,
    history: list[dict[str, Any]] | None = None,
    already_spent: Decimal = _ZERO_COST,
) -> TurnResult:
    """Runs one conversational turn: proposes tool calls, submits each to the policy.

    `pending_store` and `log` are required: a missing pending store means `/confirm`
    can never find what `/chat` proposed, and a missing logger means the audit
    trail silently stops existing. Neither failure should be possible to forget.
    """
    # What this turn spends, separate from what the session already spent. Never a default.
    turn_cost = _ZERO_COST

    if len(user_message) > settings.max_message_chars:
        return TurnResult(
            type="error", text=FALLBACK_INPUT_TOO_LONG, trace_id=trace_id, cost_usd=turn_cost
        )

    if already_spent > settings.max_cost_per_session_usd:
        return TurnResult(
            type="error", text=FALLBACK_BUDGET_EXCEEDED, trace_id=trace_id, cost_usd=turn_cost
        )

    log(trace_id, "user_message", chars=len(user_message), sha8=_sha8(user_message))

    messages = history if history is not None else []
    messages.append({"role": "user", "content": user_message})

    system_prompt = SYSTEM_PROMPT.format(role=role, today=date.today().isoformat())
    declared_tools = tool_schemas_for(role)
    total_input_tokens = 0
    total_output_tokens = 0
    total_latency_ms = 0

    for iteration in range(settings.llm_max_iterations):
        started = time.monotonic()
        try:
            response = llm.create(
                system=system_prompt,
                messages=trim_history(messages, settings.history_max_turns),
                tools=declared_tools,
            )
        except Exception as exc:
            log(trace_id, "llm_error", error=str(exc))
            return TurnResult(
                type="error", text=FALLBACK_LLM_ERROR, trace_id=trace_id, cost_usd=turn_cost
            )
        latency_ms = int((time.monotonic() - started) * 1000)
        total_latency_ms += latency_ms
        total_input_tokens += response.input_tokens
        total_output_tokens += response.output_tokens

        call_cost = estimate_cost(response.model, response.input_tokens, response.output_tokens)
        turn_cost += call_cost
        log(
            trace_id,
            "llm_call",
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cache_read_input_tokens=response.cache_read_input_tokens,
            cache_creation_input_tokens=response.cache_creation_input_tokens,
            latency_ms=latency_ms,
            cost_usd=str(call_cost),
            prompt_version=PROMPT_VERSION,
        )

        if already_spent + turn_cost > settings.max_cost_per_session_usd:
            return TurnResult(
                type="error", text=FALLBACK_BUDGET_EXCEEDED, trace_id=trace_id, cost_usd=turn_cost
            )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            telemetry = {
                "latency_ms": total_latency_ms,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "iterations": iteration + 1,
            }
            return TurnResult(
                type="message",
                text=_extract_text(response.content),
                trace_id=trace_id,
                cost_usd=turn_cost,
                telemetry=telemetry,
            )

        tool_results: list[dict[str, Any]] = []
        for block in response.content:
            if block.get("type") != "tool_use":
                continue
            tool_name = block["name"]
            tool_use_id = block["id"]
            raw_args = block.get("input", {})

            decision = policy.evaluate(tool_name, raw_args, role, db)
            log(
                trace_id,
                "policy_decision",
                tool=tool_name,
                allowed=decision.allowed,
                requires_confirmation=decision.requires_confirmation,
                reason=decision.reason,
            )

            if not decision.allowed:
                tools.record_audit(
                    db,
                    ctx=AuditContext(actor=actor, role=role, trace_id=trace_id),
                    action=tool_name,
                    args=raw_args,
                    outcome="denied",
                    reason_code=decision.reason,
                )
                db.commit()
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": presentation.render_denial(decision.reason),
                        "is_error": True,
                    }
                )
                continue

            if decision.requires_confirmation:
                return _confirmation_result(
                    decision,
                    session_id=session_id,
                    actor=actor,
                    role=role,
                    tool_name=tool_name,
                    trace_id=trace_id,
                    store=pending_store,
                    log_fn=log,
                    cost_usd=turn_cost,
                )

            exec_started = time.monotonic()
            try:
                result_payload = _run_read_tool(ToolName(tool_name), decision.safe_args, db)
                ok = True
            except DomainError as exc:
                result_payload = {"error": str(exc)}
                ok = False
            duration_ms = int((time.monotonic() - exec_started) * 1000)
            log(trace_id, "tool_executed", tool=tool_name, ok=ok, duration_ms=duration_ms)

            wrapped = wrap_untrusted(strip_personal_fields(result_payload))
            tool_results.append(
                {"type": "tool_result", "tool_use_id": tool_use_id, "content": wrapped}
            )

        messages.append({"role": "user", "content": tool_results})

    log(trace_id, "max_iterations_reached")
    return TurnResult(
        type="error", text=FALLBACK_MAX_ITERATIONS, trace_id=trace_id, cost_usd=turn_cost
    )
