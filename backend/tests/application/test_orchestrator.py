"""Behaviour suite for the orchestrator: every proposal must pass through the policy."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.application.agent.orchestrator import (
    TurnResult,
    _confirmation_result,
    _run_read_tool,
    run_turn,
    strip_personal_fields,
    wrap_untrusted,
)
from app.application.constants import Model
from app.application.messages import (
    FALLBACK_BUDGET_EXCEEDED,
    FALLBACK_INPUT_TOO_LONG,
    FALLBACK_MAX_ITERATIONS,
)
from app.application.permissions import DenialReason, Role, ToolName
from app.application.policy import PolicyDecision
from app.application.ports import LLMResponse
from app.application.pricing import estimate_cost
from app.config import settings
from app.domain.constants import OrderStatus
from app.domain.models import AuditLog, Client, Order
from app.infrastructure.llm.scripted import ScriptedClient
from app.infrastructure.pending.memory import InMemoryPendingActionStore


def _tool_use(tool: ToolName, args: dict[str, Any]) -> dict[str, Any]:
    return {"type": "tool_use", "id": "tu-1", "name": tool.value, "input": args}


def _response_with(block: dict[str, Any]) -> LLMResponse:
    return LLMResponse(
        stop_reason="tool_use",
        content=[block],
        input_tokens=10,
        output_tokens=5,
        model="claude-haiku-4-5",
    )


def _text_response(text: str) -> LLMResponse:
    return LLMResponse(
        stop_reason="end_turn",
        content=[{"type": "text", "text": text}],
        input_tokens=10,
        output_tokens=5,
        model="claude-haiku-4-5",
    )


def _log(trace_id: str, event: str, **fields: Any) -> None:
    """No-op logger for tests that assert on something other than logging."""


def _store() -> InMemoryPendingActionStore:
    """A real, working store — not a stub — since `pending_store` is a required port."""
    return InMemoryPendingActionStore(ttl_seconds=300, clock=lambda: datetime.now(UTC))


def _run(**kwargs: Any) -> TurnResult:
    """Calls `run_turn`, filling the required ports with harmless test defaults."""
    kwargs.setdefault("log", _log)
    kwargs.setdefault("pending_store", _store())
    return run_turn(**kwargs)


def test_an_operator_attempting_a_write_gets_a_message_and_changes_nothing(db, seeded):
    order = db.query(Order).filter_by(status=OrderStatus.PENDING).first()
    llm = ScriptedClient(
        [
            _response_with(
                _tool_use(
                    ToolName.UPDATE_ORDER_STATUS,
                    {
                        "order_id": order.id,
                        "new_status": "delivered",
                        "reason": "motivo valido",
                    },
                )
            ),
            _text_response("No tienes permiso para esa operación."),
        ]
    )
    result = _run(
        user_message="cambia la orden",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert result.type == "message"
    db.refresh(order)
    assert order.status is OrderStatus.PENDING


def test_a_supervisor_write_stops_at_confirmation_and_changes_nothing_yet(db, seeded):
    order = db.query(Order).filter_by(status=OrderStatus.PENDING).first()
    llm = ScriptedClient(
        [
            _response_with(
                _tool_use(
                    ToolName.UPDATE_ORDER_STATUS,
                    {
                        "order_id": order.id,
                        "new_status": "in_progress",
                        "reason": "el taller lo recibio",
                    },
                )
            ),
        ]
    )
    result = _run(
        user_message="pásala a en proceso",
        role=Role.SUPERVISOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert result.type == "confirmation_required"
    assert result.pending_id
    assert "en proceso" in result.pending_summary
    db.refresh(order)
    assert order.status is OrderStatus.PENDING


def test_the_loop_does_not_continue_after_requesting_confirmation(db, seeded):
    """One scripted response only: a second call would raise ScriptExhaustedError."""
    order = db.query(Order).filter_by(status=OrderStatus.PENDING).first()
    llm = ScriptedClient(
        [
            _response_with(
                _tool_use(
                    ToolName.UPDATE_ORDER_STATUS,
                    {
                        "order_id": order.id,
                        "new_status": "in_progress",
                        "reason": "motivo valido",
                    },
                )
            ),
        ]
    )
    _run(
        user_message="x",
        role=Role.SUPERVISOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert len(llm.calls) == 1


def test_a_denial_is_audited_and_returned_to_the_model_for_explanation(db, seeded):
    llm = ScriptedClient(
        [
            _response_with(
                _tool_use(
                    ToolName.UPDATE_ORDER_STATUS,
                    {"order_id": 1, "new_status": "delivered", "reason": "x"},
                )
            ),
            _text_response("No puedo hacer eso."),
        ]
    )
    _run(
        user_message="x",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    denied = db.query(AuditLog).filter_by(outcome="denied").all()
    assert len(denied) == 1
    assert denied[0].reason_code == "role_lacks_permission"
    second_call_messages = str(llm.calls[1].messages)
    assert "is_error" in second_call_messages or "no tiene permiso" in second_call_messages.lower()


def test_the_repair_loop_lets_the_model_fix_its_own_arguments(db, seeded):
    """First attempt invalid, second correct, success with no user intervention."""
    llm = ScriptedClient(
        [
            _response_with(_tool_use(ToolName.GET_SALES_ORDERS, {"limit": -5})),
            _response_with(_tool_use(ToolName.GET_SALES_ORDERS, {"limit": 5})),
            _text_response("Hay 5 órdenes."),
        ]
    )
    result = _run(
        user_message="dame órdenes",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert result.type == "message"
    assert len(llm.calls) == 3


def test_an_unknown_tool_from_the_model_is_denied(db, seeded):
    llm = ScriptedClient(
        [
            _response_with({"type": "tool_use", "id": "t", "name": "drop_database", "input": {}}),
            _text_response("No existe esa operación."),
        ]
    )
    _run(
        user_message="x",
        role=Role.SUPERVISOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert db.query(AuditLog).filter_by(reason_code="unknown_tool").count() == 1


def test_an_over_long_message_is_rejected_without_calling_the_model(db, seeded):
    llm = ScriptedClient([])
    result = _run(
        user_message="x" * 2001,
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert result.text == FALLBACK_INPUT_TOO_LONG
    assert llm.calls == []


def test_the_iteration_cap_ends_the_turn_with_a_fallback(db, seeded):
    llm = ScriptedClient(
        [_response_with(_tool_use(ToolName.GET_SALES_ORDERS, {})) for _ in range(6)]
    )
    result = _run(
        user_message="x",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert result.text == FALLBACK_MAX_ITERATIONS
    assert len(llm.calls) <= 5


def test_a_model_timeout_produces_a_fallback_not_a_crash(db, seeded):
    llm = ScriptedClient([TimeoutError("simulated")])
    result = _run(
        user_message="x",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert result.type == "error"
    assert result.text


def test_only_the_tools_of_the_role_are_declared_to_the_model(db, seeded):
    llm = ScriptedClient([_text_response("hola")])
    _run(
        user_message="x",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    declared = {tool["name"] for tool in llm.calls[0].tools}
    assert ToolName.UPDATE_ORDER_STATUS.value not in declared


def test_tool_results_reach_the_model_wrapped_as_untrusted_data(db, seeded):
    llm = ScriptedClient(
        [
            _response_with(_tool_use(ToolName.GET_SALES_ORDERS, {"limit": 3})),
            _text_response("listo"),
        ]
    )
    _run(
        user_message="x",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert "<untrusted_data>" in str(llm.calls[1].messages)


def test_the_adversarial_seed_name_reaches_the_model_as_data_and_changes_nothing(db, seeded):
    """The payload is not sanitised; the pipeline neutralises it structurally."""
    llm = ScriptedClient(
        [
            _response_with(_tool_use(ToolName.GET_CLIENT_BALANCE, {"client_id": 8})),
            _text_response("El saldo es X. El nombre del cliente contiene texto anómalo."),
        ]
    )
    _run(
        user_message="saldo del cliente 8",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert db.query(AuditLog).filter_by(outcome="executed").count() == 0


def test_personal_fields_never_leave_for_the_model() -> None:
    payload = {"orders": [{"id": 1}], "name": "Ana", "email": "ana@example.com"}
    assert "@" not in wrap_untrusted(strip_personal_fields(payload))


def test_personal_fields_are_stripped_from_orders_nested_inside_a_dict() -> None:
    """Orders come back nested; a shallow strip would miss the email one level down."""
    payload = {"client": {"name": "Ana", "email": "ana@example.com"}, "orders": [{"id": 1}]}
    stripped = strip_personal_fields(payload)
    assert "@" not in wrap_untrusted(stripped)
    assert stripped["client"]["name"] == "Ana"


def test_the_budget_guardrail_stops_the_turn_instead_of_spending_more(db, seeded):
    llm = ScriptedClient([_text_response("hola")])
    result = _run(
        user_message="x",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
        already_spent=Decimal("999.00"),
    )
    assert result.type == "error"
    assert llm.calls == []


def test_the_budget_guard_fires_from_real_accumulated_cost(db, seeded):
    """Uses the real `estimate_cost` (no stub): large token counts must cross the cap for real."""
    expensive_response = _response_with(_tool_use(ToolName.GET_SALES_ORDERS, {}))
    expensive_response = LLMResponse(
        stop_reason=expensive_response.stop_reason,
        content=expensive_response.content,
        input_tokens=0,
        output_tokens=300_000,  # claude-haiku-4-5 output price ($5/M) -> $1.50, past the $1 cap
        model="claude-haiku-4-5",
    )
    llm = ScriptedClient([expensive_response, expensive_response, expensive_response])
    result = _run(
        user_message="x",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert result == TurnResult(
        type="error",
        text=FALLBACK_BUDGET_EXCEEDED,
        trace_id="abc12345",
        cost_usd=Decimal("1.50"),  # the one call it did make, at $5/M output
        telemetry={
            "latency_ms": result.telemetry["latency_ms"] if result.telemetry else None,
            "input_tokens": 0,
            "output_tokens": 300_000,
            "iterations": 1,
        },
    )
    assert len(llm.calls) == 1


def test_the_in_loop_budget_guard_reports_what_the_turn_already_spent(db, seeded):
    """A turn stopped mid-loop was billed for the call it made; zeros would call it free."""
    expensive = _response_with(_tool_use(ToolName.GET_SALES_ORDERS, {}))
    expensive = LLMResponse(
        stop_reason=expensive.stop_reason,
        content=expensive.content,
        input_tokens=0,
        output_tokens=300_000,
        model="claude-haiku-4-5",
    )
    result = _run(
        user_message="x",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=ScriptedClient([expensive]),
        trace_id="abc12345",
    )
    assert result.telemetry is not None
    assert result.telemetry["output_tokens"] == 300_000
    assert result.telemetry["iterations"] == 1


def test_a_failing_tool_returns_a_safe_message_never_a_stacktrace(db, seeded):
    llm = ScriptedClient(
        [
            _response_with(_tool_use(ToolName.GET_CLIENT_BALANCE, {"client_id": 999})),
            _text_response("No encontré a ese cliente."),
        ]
    )
    result = _run(
        user_message="saldo del cliente 999",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert result.type == "message"
    second_call_messages = str(llm.calls[1].messages)
    assert "Traceback" not in second_call_messages


def test_a_leading_text_block_alongside_a_tool_use_block_is_skipped_not_executed(db, seeded):
    """The model may narrate before proposing a tool; only tool_use blocks are dispatched."""
    mixed_response = LLMResponse(
        stop_reason="tool_use",
        content=[
            {"type": "text", "text": "Consultando..."},
            _tool_use(ToolName.GET_SALES_ORDERS, {"limit": 1}),
        ],
        input_tokens=10,
        output_tokens=5,
        model="claude-haiku-4-5",
    )
    llm = ScriptedClient([mixed_response, _text_response("listo")])
    result = _run(
        user_message="x",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert result.type == "message"


def test_a_write_tool_can_never_reach_direct_execution(db) -> None:
    """Defence in depth: update_order_status always requires confirmation, never runs here."""
    safe_args = {"order_id": 1, "new_status": "delivered", "reason": "motivo valido"}
    with pytest.raises(AssertionError):
        _run_read_tool(ToolName.UPDATE_ORDER_STATUS, safe_args, db)


def test_a_confirmation_decision_without_a_change_is_an_invariant_violation() -> None:
    """Defence in depth: policy must never set requires_confirmation without a change."""
    bad_decision = PolicyDecision(
        allowed=True, requires_confirmation=True, reason="ok", change=None
    )
    with pytest.raises(AssertionError):
        _confirmation_result(
            bad_decision,
            session_id="s-1",
            actor="u-1",
            role="supervisor",
            tool_name=ToolName.UPDATE_ORDER_STATUS.value,
            trace_id="abc12345",
            store=_store(),
            log_fn=_log,
            cost_usd=Decimal("0.00"),
            telemetry={},
        )


def test_the_logger_never_receives_raw_user_text(db, seeded):
    logged: list[tuple[str, dict[str, Any]]] = []

    def fake_log(trace_id: str, event: str, **fields: Any) -> None:
        logged.append((event, fields))

    llm = ScriptedClient([_text_response("hola")])
    secret_text = "mi correo es alguien@example.com"
    _run(
        user_message=secret_text,
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
        log=fake_log,
    )
    user_message_events = [fields for event, fields in logged if event == "user_message"]
    assert len(user_message_events) == 1
    assert "chars" in user_message_events[0]
    assert "sha8" in user_message_events[0]
    assert all(secret_text not in str(value) for _, fields in logged for value in fields.values())


def _cost(input_tokens: int, output_tokens: int) -> Decimal:
    return estimate_cost(Model.HAIKU_4_5, input_tokens, output_tokens)


def test_a_completed_turn_reports_exactly_what_it_spent(db, seeded):
    result = _run(
        user_message="x",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=ScriptedClient([_text_response("hola")]),
        trace_id="abc12345",
    )
    assert result.cost_usd == _cost(10, 5)


_NO_MODEL_RAN = {"latency_ms": 0, "input_tokens": 0, "output_tokens": 0, "iterations": 0}


def _over_long_turn(db):
    """Refused on length, before the model is ever reached."""
    return _run(
        user_message="x" * 2001,
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=ScriptedClient([]),
        trace_id="abc12345",
    )


def _exhausted_budget_turn(db):
    """Refused on the pre-flight budget guard, also before any call."""
    return _run(
        user_message="x",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=ScriptedClient([]),
        trace_id="abc12345",
        already_spent=Decimal("999.00"),
    )


def test_a_guard_that_returns_before_any_model_call_reports_a_computed_zero(db, seeded):
    assert _over_long_turn(db).cost_usd == Decimal("0.00")


def test_the_budget_guard_bills_nothing_for_the_turn_it_refuses_to_start(db, seeded):
    assert _exhausted_budget_turn(db).cost_usd == Decimal("0.00")


def test_an_over_long_message_reports_zeros_because_no_model_ran(db, seeded):
    """Zeros are the honest measurement here, exactly as /confirm reports them."""
    assert _over_long_turn(db).telemetry == _NO_MODEL_RAN


def test_the_preflight_budget_guard_reports_zeros_because_no_model_ran(db, seeded):
    assert _exhausted_budget_turn(db).telemetry == _NO_MODEL_RAN


def _confirmation_turn(db):
    """Drives a supervisor write proposal to the confirmation card."""
    order = db.query(Order).filter_by(status=OrderStatus.IN_PROGRESS).first()
    llm = ScriptedClient(
        [
            _response_with(
                _tool_use(
                    ToolName.UPDATE_ORDER_STATUS,
                    {"order_id": order.id, "new_status": "delivered", "reason": "motivo valido"},
                )
            )
        ]
    )
    return _run(
        user_message="x",
        role=Role.SUPERVISOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )


def test_a_confirmation_turn_reports_the_telemetry_of_the_call_that_produced_it(db, seeded):
    """The card is a turn like any other: the numbers exist, they were merely not carried."""
    result = _confirmation_turn(db)
    assert result.type == "confirmation_required"
    assert result.telemetry["input_tokens"] == 10
    assert result.telemetry["output_tokens"] == 5
    assert result.telemetry["iterations"] == 1
    assert result.telemetry["latency_ms"] >= 0


def test_a_confirmation_turn_reports_the_calls_it_paid_for(db, seeded):
    """cost_usd is billing, not telemetry: it must be right whatever the turn's type."""
    result = _confirmation_turn(db)
    assert result.type == "confirmation_required"
    assert result.cost_usd == _cost(10, 5)


def _failing_turn(db, responses):
    """One read proposal is executed per response, so each entry is a call really paid for."""
    return _run(
        user_message="x",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=ScriptedClient(responses),
        trace_id="abc12345",
    )


def _model_error_turn(db):
    return _failing_turn(
        db, [_response_with(_tool_use(ToolName.GET_SALES_ORDERS, {})), TimeoutError("simulated")]
    )


def _iteration_cap_turn(db):
    return _failing_turn(
        db, [_response_with(_tool_use(ToolName.GET_SALES_ORDERS, {})) for _ in range(6)]
    )


def test_a_model_error_still_reports_the_calls_that_succeeded_before_it(db, seeded):
    result = _model_error_turn(db)
    assert result.type == "error"
    assert result.cost_usd == _cost(10, 5)


def test_the_iteration_cap_reports_every_call_it_paid_for(db, seeded):
    result = _iteration_cap_turn(db)
    assert result.text == FALLBACK_MAX_ITERATIONS
    assert result.cost_usd == _cost(10, 5) * 5


def test_a_model_error_reports_the_tokens_the_turn_had_already_spent(db, seeded):
    """Zeros here would tell an operator the failing turn was free: one call was paid for."""
    telemetry = _model_error_turn(db).telemetry
    assert telemetry["input_tokens"] == 10
    assert telemetry["output_tokens"] == 5
    assert telemetry["iterations"] == 1


def test_a_model_error_on_the_first_call_reports_zeros_and_no_iteration(db, seeded):
    """Nothing came back, so nothing is claimed: these zeros are measured, not assumed."""
    assert _failing_turn(db, [TimeoutError("simulated")]).telemetry == _NO_MODEL_RAN


def test_the_iteration_cap_reports_the_tokens_of_every_call_it_made(db, seeded):
    """The most expensive turn there is; it must not report itself as the cheapest."""
    calls = settings.llm_max_iterations
    telemetry = _iteration_cap_turn(db).telemetry
    assert telemetry["input_tokens"] == 10 * calls
    assert telemetry["output_tokens"] == 5 * calls
    assert telemetry["iterations"] == calls


def _write_args(order_id: int, new_status: str = "delivered") -> dict[str, Any]:
    return {"order_id": order_id, "new_status": new_status, "reason": "motivo valido"}


def test_a_refused_turn_reports_the_denial_reason(db, seeded):
    """The gap this closes: a refusal must be machine-readable, not only Spanish prose."""
    llm = ScriptedClient(
        [
            _response_with(_tool_use(ToolName.UPDATE_ORDER_STATUS, _write_args(1))),
            _text_response("Tu rol no tiene permiso para esta operación."),
        ]
    )
    result = _run(
        user_message="cambia la orden #1 a entregada",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert result.type == "message"
    assert result.reason_code == DenialReason.ROLE_LACKS_PERMISSION.value


def test_an_ordinary_answer_carries_no_reason_code(db, seeded):
    """Without this, every answer would read as a denial and the signal would be worthless."""
    llm = ScriptedClient(
        [
            _response_with(_tool_use(ToolName.GET_SALES_ORDERS, {"limit": 5})),
            _text_response("Hay 5 órdenes."),
        ]
    )
    result = _run(
        user_message="dame órdenes",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert result.type == "message"
    assert result.reason_code is None


def test_a_refusal_stands_even_when_another_tool_in_the_same_turn_succeeds(db, seeded):
    """Partial refusal is still refusal: a client must never read the success as consent."""
    client_id = db.query(Client).first().id
    mixed = LLMResponse(
        stop_reason="tool_use",
        content=[
            _tool_use(ToolName.UPDATE_ORDER_STATUS, _write_args(1)),
            {
                "type": "tool_use",
                "id": "tu-2",
                "name": ToolName.GET_CLIENT_BALANCE.value,
                "input": {"client_id": client_id},
            },
        ],
        input_tokens=10,
        output_tokens=5,
        model="claude-haiku-4-5",
    )
    llm = ScriptedClient([mixed, _text_response("No puedo cambiarla, pero el saldo es X.")])
    result = _run(
        user_message="cambia la orden #1 y dame el saldo",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert result.reason_code == DenialReason.ROLE_LACKS_PERMISSION.value


def test_a_repaired_call_clears_the_refusal_it_replaces(db, seeded):
    """The model fixed its own arguments, so the user was never refused anything."""
    llm = ScriptedClient(
        [
            _response_with(_tool_use(ToolName.GET_SALES_ORDERS, {"limit": -5})),
            _response_with(_tool_use(ToolName.GET_SALES_ORDERS, {"limit": 5})),
            _text_response("Hay 5 órdenes."),
        ]
    )
    result = _run(
        user_message="dame órdenes",
        role=Role.OPERATOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=llm,
        trace_id="abc12345",
    )
    assert result.reason_code is None


def test_a_confirmation_card_is_never_labelled_a_refusal(db, seeded):
    """A turn awaiting consent was not refused; tagging it would style the card as a denial."""
    order = db.query(Order).filter_by(status=OrderStatus.IN_PROGRESS).first()
    mixed = LLMResponse(
        stop_reason="tool_use",
        content=[
            {
                "type": "tool_use",
                "id": "tu-2",
                "name": ToolName.GET_CLIENT_BALANCE.value,
                "input": {"client_id": -1},
            },
            _tool_use(ToolName.UPDATE_ORDER_STATUS, _write_args(order.id)),
        ],
        input_tokens=10,
        output_tokens=5,
        model="claude-haiku-4-5",
    )
    result = _run(
        user_message="dame el saldo y marca la orden como entregada",
        role=Role.SUPERVISOR.value,
        actor="u-1",
        session_id="s-1",
        db=db,
        llm=ScriptedClient([mixed]),
        trace_id="abc12345",
    )
    assert result.type == "confirmation_required"
    assert result.reason_code is None


def test_cost_usd_has_no_default_a_missing_value_must_fail_construction() -> None:
    """A zero default is exactly how under-billing would come back unnoticed."""
    with pytest.raises(TypeError):
        TurnResult(type="message", text="x", trace_id="abc12345")
