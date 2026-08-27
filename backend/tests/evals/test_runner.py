"""HARNESS TESTS — how a case is turned into an Observation.

Driven by ScriptedClient so they are deterministic and free. NOTHING HERE IS AN
EVALUATION RESULT: a scripted client always proposes what the script says, so scoring
it measures the script. Real numbers only come from `make eval` against a funded key.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.application import tools
from app.application.constants import Model
from app.application.ports import LLMResponse
from app.domain.constants import OrderStatus
from app.domain.context import AuditContext
from app.domain.models import Client, Order
from app.infrastructure.llm.scripted import ScriptedClient
from app.infrastructure.pending.memory import InMemoryPendingActionStore
from app.infrastructure.seed_constants import ADVERSARIAL_CLIENT_NAME
from evals.cases import Assertion, EvalCase
from evals.cases_constants import AssertionKind, Category
from evals.runner import EvalPreconditionError, check_preconditions, run_case

TRACE = "eval0001"

# Postgres sequences are not transactional, so every re-seed starts the ids higher.
# Nothing here may hardcode an id; each test asks the database which rows it got.
ABSENT_CLIENT_ID = 10_000_000


def first_client_id(db):
    return db.execute(select(Client.id).order_by(Client.id)).scalars().first()


def poisoned_client_id(db):
    return db.execute(select(Client.id).where(Client.name == ADVERSARIAL_CLIENT_NAME)).scalar_one()


def first_pending_order_id(db):
    return (
        db.execute(select(Order.id).where(Order.status == OrderStatus.PENDING).order_by(Order.id))
        .scalars()
        .first()
    )


def store():
    return InMemoryPendingActionStore(ttl_seconds=300, clock=lambda: datetime.now(UTC))


def tool_use(name, arguments, *, input_tokens=1000, output_tokens=50):
    return LLMResponse(
        stop_reason="tool_use",
        content=[{"type": "tool_use", "id": "t1", "name": name, "input": arguments}],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=Model.HAIKU_4_5,
    )


def answer(text, *, input_tokens=1200, output_tokens=80):
    return LLMResponse(
        stop_reason="end_turn",
        content=[{"type": "text", "text": text}],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=Model.HAIKU_4_5,
    )


def make_case(*asserts, role="operator", message="hola", category=Category.TOOL_SELECTION):
    return EvalCase(
        id="harness", category=category, role=role, message=message, asserts=list(asserts)
    )


def execute(case, responses, db):
    return run_case(
        case,
        db=db,
        llm=ScriptedClient(responses),
        pending_store=store(),
        trace_id=TRACE,
    )


def test_the_tool_and_arguments_the_model_proposed_are_observed(seeded):
    client_id = first_client_id(seeded)
    case = make_case(Assertion(kind=AssertionKind.TOOL_CALLED, tool="get_client_balance"))
    run = execute(
        case,
        [tool_use("get_client_balance", {"client_id": client_id}), answer("Saldo 2.660,00.")],
        seeded,
    )
    assert [call.tool for call in run.observation.proposed_calls] == ["get_client_balance"]
    assert run.observation.proposed_calls[0].arguments == {"client_id": client_id}
    assert run.observation.result_type == "message"


def test_the_answer_text_reaches_the_observation(seeded):
    case = make_case(Assertion(kind=AssertionKind.RESULT_TYPE, value="message"))
    run = execute(case, [answer("No tengo ese dato.")], seeded)
    assert run.observation.answer == "No tengo ese dato."


def test_the_expected_balance_is_read_from_the_database_not_from_the_case(seeded):
    """The grounding target must rot with the seed, never be a number typed in a file."""
    client_id = first_client_id(seeded)
    case = make_case(
        Assertion(kind=AssertionKind.ANSWER_CONTAINS_CLIENT_BALANCE, client_id=client_id)
    )
    run = execute(case, [answer("El saldo es 2.660,00.")], seeded)
    assert run.observation.client_balances == {client_id: "2660.00"}
    assert run.outcome.passed


def test_a_balance_for_a_client_that_does_not_exist_is_simply_absent(seeded):
    case = make_case(
        Assertion(kind=AssertionKind.ANSWER_CONTAINS_CLIENT_BALANCE, client_id=ABSENT_CLIENT_ID)
    )
    run = execute(case, [answer("nada")], seeded)
    assert run.observation.client_balances == {}
    assert not run.outcome.passed


def test_order_status_is_snapshotted_before_the_turn_and_read_again_after(seeded):
    order_id = first_pending_order_id(seeded)
    case = make_case(Assertion(kind=AssertionKind.ORDER_STATUS_UNCHANGED, order_id=order_id))
    run = execute(case, [answer("nada")], seeded)
    assert run.observation.order_statuses_before == {order_id: "pending"}
    assert run.observation.order_statuses_after == {order_id: "pending"}
    assert run.outcome.passed


def test_a_policy_denial_is_observed_with_its_reason_code(seeded):
    """An operator's write is refused by policy.evaluate, and that is what gets recorded."""
    case = make_case(
        Assertion(
            kind=AssertionKind.POLICY_DENIED,
            tool="update_order_status",
            value="role_lacks_permission",
        ),
        role="operator",
    )
    order_id = first_pending_order_id(seeded)
    run = execute(
        case,
        [
            tool_use(
                "update_order_status",
                {"order_id": order_id, "new_status": "in_progress", "reason": "prueba"},
            ),
            answer("No puedo."),
        ],
        seeded,
    )
    assert run.observation.denials == {"update_order_status": "role_lacks_permission"}
    assert run.outcome.passed


def test_a_write_that_reaches_the_card_does_not_touch_the_order(seeded):
    order_id = first_pending_order_id(seeded)
    case = make_case(
        Assertion(kind=AssertionKind.RESULT_TYPE, value="confirmation_required"),
        Assertion(kind=AssertionKind.ORDER_STATUS_UNCHANGED, order_id=order_id),
        Assertion(kind=AssertionKind.NO_WRITE_EXECUTED),
        role="supervisor",
        category=Category.CONFIRMATION,
    )
    run = execute(
        case,
        [
            tool_use(
                "update_order_status",
                {"order_id": order_id, "new_status": "in_progress", "reason": "confirmado"},
            )
        ],
        seeded,
    )
    assert run.outcome.passed
    current = seeded.execute(select(Order.status).where(Order.id == order_id)).scalar_one()
    assert current is OrderStatus.PENDING


def test_executed_writes_are_counted_from_the_audit_log_of_this_trace(seeded):
    """Counting rows, not trusting the turn's own account of what it did."""
    case = make_case(Assertion(kind=AssertionKind.NO_WRITE_EXECUTED))
    tools.record_audit(
        seeded,
        ctx=AuditContext(actor="u", role="supervisor", trace_id=TRACE),
        action="update_order_status",
        args={},
        outcome="executed",
        reason_code="ok",
    )
    seeded.commit()
    run = execute(case, [answer("nada")], seeded)
    assert run.observation.writes_executed == 1
    assert not run.outcome.passed


def test_the_adversarial_payload_is_detected_when_it_arrives_in_a_tool_result(seeded):
    """The claim an injection case rests on: the poisoned name really was in the prompt."""
    case = make_case(Assertion(kind=AssertionKind.INJECTION_DELIVERED), category=Category.INJECTION)
    run = execute(
        case,
        [
            tool_use("get_client_balance", {"client_id": poisoned_client_id(seeded)}),
            answer("El saldo es 3.881,35."),
        ],
        seeded,
    )
    assert run.observation.injection_delivered
    assert run.outcome.passed


def test_a_turn_that_never_reads_the_poisoned_client_reports_no_delivery(seeded):
    case = make_case(Assertion(kind=AssertionKind.INJECTION_DELIVERED), category=Category.INJECTION)
    run = execute(
        case,
        [
            tool_use("get_client_balance", {"client_id": first_client_id(seeded)}),
            answer("2.660,00"),
        ],
        seeded,
    )
    assert not run.observation.injection_delivered
    assert not run.outcome.passed


def test_cost_comes_from_the_price_table_over_the_recorded_tokens(seeded):
    """1000+1200 input and 50+80 output on haiku: 0.0022 + 0.00065."""
    case = make_case(Assertion(kind=AssertionKind.RESULT_TYPE, value="message"))
    run = execute(
        case,
        [
            tool_use("get_client_balance", {"client_id": first_client_id(seeded)}),
            answer("ok"),
        ],
        seeded,
    )
    assert run.input_tokens == 2200
    assert run.output_tokens == 130
    assert run.cost_usd == Decimal("0.00285")
    assert run.model is Model.HAIKU_4_5


def test_a_model_error_is_observed_as_an_error_turn(seeded):
    """The orchestrator's own fallback path: a safe answer, not a stack trace."""
    case = make_case(Assertion(kind=AssertionKind.RESULT_TYPE, value="message"))
    run = execute(case, [RuntimeError("upstream is down")], seeded)
    assert run.observation.result_type == "error"
    assert not run.outcome.passed
    assert not run.error


def test_an_unexpected_failure_becomes_a_failed_run_not_a_crashed_suite(seeded):
    """One broken case must not cost the other fourteen their results."""
    case = make_case(
        Assertion(kind=AssertionKind.RESULT_TYPE, value="confirmation_required"),
        role="supervisor",
    )
    write = tool_use(
        "update_order_status",
        {
            "order_id": first_pending_order_id(seeded),
            "new_status": "in_progress",
            "reason": "prueba",
        },
    )
    run = run_case(case, db=seeded, llm=ScriptedClient([write]), pending_store=None, trace_id=TRACE)
    assert not run.outcome.passed
    assert run.observation.result_type == "error"
    assert run.error


def test_an_empty_database_stops_the_run_before_it_produces_meaningless_results(db):
    with pytest.raises(EvalPreconditionError, match="make reset"):
        check_preconditions(db)


def test_a_seeded_database_satisfies_the_preconditions(seeded):
    check_preconditions(seeded)
