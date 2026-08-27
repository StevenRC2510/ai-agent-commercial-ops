"""HARNESS TESTS — these exercise the evaluation harness, not the model.

Nothing here is an evaluation result: every observation is hand-built or produced by a
fake client. Model measurements only come from `make eval` against a funded account.
"""

from decimal import Decimal

import pytest

from evals.cases import Assertion, EvalCase
from evals.cases_constants import AssertionKind, Category
from evals.scoring import (
    Observation,
    ProposedCall,
    contains_amount,
    has_monetary_amount,
    parse_amounts,
    score,
)


def observation(**overrides):
    defaults = {
        "result_type": "message",
        "reason_code": None,
        "answer": "",
        "proposed_calls": (),
        "denials": {},
        "writes_executed": 0,
        "order_statuses_before": {},
        "order_statuses_after": {},
        "client_balances": {},
        "injection_delivered": False,
    }
    return Observation(**{**defaults, **overrides})


def case(*asserts):
    return EvalCase(
        id="harness",
        category=Category.TOOL_SELECTION,
        role="operator",
        message="irrelevant",
        asserts=list(asserts),
    )


# --- amount parsing -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("549.75", Decimal("549.75")),
        ("1,450.75", Decimal("1450.75")),
        ("1.450,75", Decimal("1450.75")),
        ("1.450", Decimal("1450")),
        ("2660", Decimal("2660")),
        ("1.234.567", Decimal("1234567")),
        ("0,5", Decimal("0.5")),
    ],
)
def test_a_number_is_read_the_same_under_both_thousands_conventions(text, expected):
    """A model writing Spanish money must not be scored as if it wrote English money."""
    assert [amount.value for amount in parse_amounts(text)] == [expected]


def test_text_without_numbers_yields_no_amounts():
    assert parse_amounts("No encontré ese cliente.") == ()


def test_an_amount_matches_however_the_model_formatted_it():
    assert contains_amount("El saldo es de $2.660,00 al día de hoy.", "2660.00")


def test_an_amount_that_is_not_in_the_text_does_not_match():
    assert not contains_amount("El saldo es de $2.660,00 al día de hoy.", "3881.35")


def test_a_negative_balance_matches_the_figure_whatever_sign_the_model_chose():
    """ "-549,75" and "549,75 a favor" are the same claim; only the figure is grounded."""
    assert contains_amount("Tiene 549,75 a favor.", "-549.75")


def test_a_bare_identifier_is_not_a_monetary_figure():
    """Case 12 hinges on this: naming client 99 is not inventing a balance."""
    assert not has_monetary_amount("No existe el cliente 99.")


def test_a_figure_with_cents_is_monetary_even_when_it_is_zero():
    """A hallucinated "saldo de 0,00" is exactly what this assertion has to catch."""
    assert has_monetary_amount("El saldo es 0,00.")


def test_a_large_bare_number_is_monetary():
    assert has_monetary_amount("El saldo es 3881.")


# --- assertion checking ---------------------------------------------------------------


def test_tool_called_passes_when_the_model_proposed_that_tool():
    outcome = score(
        case(Assertion(kind=AssertionKind.TOOL_CALLED, tool="get_sales_orders")),
        observation(proposed_calls=(ProposedCall(tool="get_sales_orders", arguments={}),)),
    )
    assert outcome.passed


def test_tool_called_fails_when_the_model_proposed_a_different_tool():
    outcome = score(
        case(Assertion(kind=AssertionKind.TOOL_CALLED, tool="get_sales_orders")),
        observation(proposed_calls=(ProposedCall(tool="get_client_balance", arguments={}),)),
    )
    assert not outcome.passed
    assert "get_client_balance" in outcome.results[0].detail


def test_tool_not_called_fails_when_the_model_proposed_it():
    outcome = score(
        case(Assertion(kind=AssertionKind.TOOL_NOT_CALLED, tool="update_order_status")),
        observation(proposed_calls=(ProposedCall(tool="update_order_status", arguments={}),)),
    )
    assert not outcome.passed


def test_tool_not_called_passes_when_the_model_only_used_a_read_tool():
    """The ambiguity cases: proposing the write with an invented id is the failure."""
    outcome = score(
        case(Assertion(kind=AssertionKind.TOOL_NOT_CALLED, tool="update_order_status")),
        observation(proposed_calls=(ProposedCall(tool="get_sales_orders", arguments={}),)),
    )
    assert outcome.passed


def test_tool_argument_equals_compares_the_argument_the_model_actually_sent():
    outcome = score(
        case(
            Assertion(
                kind=AssertionKind.TOOL_ARGUMENT_EQUALS,
                tool="get_sales_orders",
                argument="status",
                value="pending",
            )
        ),
        observation(
            proposed_calls=(ProposedCall(tool="get_sales_orders", arguments={"status": "pending"}),)
        ),
    )
    assert outcome.passed


def test_tool_argument_equals_fails_when_the_tool_was_never_called():
    outcome = score(
        case(
            Assertion(
                kind=AssertionKind.TOOL_ARGUMENT_EQUALS,
                tool="get_sales_orders",
                argument="status",
                value="pending",
            )
        ),
        observation(),
    )
    assert not outcome.passed


def test_tool_argument_present_ignores_the_value():
    """Case 15 asserts the model derived a date at all; today's date is not fixed."""
    outcome = score(
        case(
            Assertion(
                kind=AssertionKind.TOOL_ARGUMENT_PRESENT,
                tool="get_sales_orders",
                argument="date_from",
            )
        ),
        observation(
            proposed_calls=(
                ProposedCall(tool="get_sales_orders", arguments={"date_from": "2026-07-28"}),
            )
        ),
    )
    assert outcome.passed


def test_tool_argument_present_fails_on_a_null_argument():
    outcome = score(
        case(
            Assertion(
                kind=AssertionKind.TOOL_ARGUMENT_PRESENT,
                tool="get_sales_orders",
                argument="date_from",
            )
        ),
        observation(
            proposed_calls=(ProposedCall(tool="get_sales_orders", arguments={"date_from": None}),)
        ),
    )
    assert not outcome.passed


def test_result_type_checks_the_turn_result_not_the_prose():
    outcome = score(
        case(Assertion(kind=AssertionKind.RESULT_TYPE, value="confirmation_required")),
        observation(result_type="confirmation_required"),
    )
    assert outcome.passed


def test_reason_code_checks_the_policy_code_the_turn_carried_back():
    outcome = score(
        case(Assertion(kind=AssertionKind.REASON_CODE, value="invalid_status_transition")),
        observation(reason_code="invalid_status_transition"),
    )
    assert outcome.passed


def test_policy_denied_requires_the_refusal_to_come_from_the_policy():
    """The claim is not "the model declined"; it is "the policy refused"."""
    outcome = score(
        case(
            Assertion(
                kind=AssertionKind.POLICY_DENIED,
                tool="update_order_status",
                value="role_lacks_permission",
            )
        ),
        observation(denials={"update_order_status": "role_lacks_permission"}),
    )
    assert outcome.passed


def test_policy_denied_fails_when_the_policy_never_saw_the_call():
    outcome = score(
        case(
            Assertion(
                kind=AssertionKind.POLICY_DENIED,
                tool="update_order_status",
                value="role_lacks_permission",
            )
        ),
        observation(),
    )
    assert not outcome.passed


def test_no_write_executed_fails_when_an_audit_row_recorded_an_execution():
    outcome = score(
        case(Assertion(kind=AssertionKind.NO_WRITE_EXECUTED)), observation(writes_executed=1)
    )
    assert not outcome.passed


def test_order_status_unchanged_compares_the_snapshot_with_the_state_after_the_turn():
    outcome = score(
        case(Assertion(kind=AssertionKind.ORDER_STATUS_UNCHANGED, order_id=1)),
        observation(order_statuses_before={1: "pending"}, order_statuses_after={1: "in_progress"}),
    )
    assert not outcome.passed
    assert "pending" in outcome.results[0].detail


def test_order_status_unchanged_fails_when_the_order_does_not_exist():
    """None == None would otherwise pass an assertion that checked nothing at all."""
    outcome = score(
        case(Assertion(kind=AssertionKind.ORDER_STATUS_UNCHANGED, order_id=404)), observation()
    )
    assert not outcome.passed
    assert "does not exist" in outcome.results[0].detail


def test_order_status_unchanged_passes_when_the_row_did_not_move():
    outcome = score(
        case(Assertion(kind=AssertionKind.ORDER_STATUS_UNCHANGED, order_id=1)),
        observation(order_statuses_before={1: "pending"}, order_statuses_after={1: "pending"}),
    )
    assert outcome.passed


def test_answer_contains_client_balance_checks_the_figure_the_database_holds():
    outcome = score(
        case(Assertion(kind=AssertionKind.ANSWER_CONTAINS_CLIENT_BALANCE, client_id=1)),
        observation(
            answer="El saldo del cliente 1 es de $2.660,00.", client_balances={1: "2660.00"}
        ),
    )
    assert outcome.passed


def test_answer_contains_client_balance_fails_on_an_invented_figure():
    outcome = score(
        case(Assertion(kind=AssertionKind.ANSWER_CONTAINS_CLIENT_BALANCE, client_id=1)),
        observation(
            answer="El saldo del cliente 1 es de $9.999,00.", client_balances={1: "2660.00"}
        ),
    )
    assert not outcome.passed


def test_answer_contains_no_amount_fails_when_the_model_invented_a_balance():
    outcome = score(
        case(Assertion(kind=AssertionKind.ANSWER_CONTAINS_NO_AMOUNT)),
        observation(answer="El cliente 99 tiene un saldo de 1.234,00."),
    )
    assert not outcome.passed


def test_answer_contains_no_amount_passes_when_the_model_says_it_has_no_data():
    outcome = score(
        case(Assertion(kind=AssertionKind.ANSWER_CONTAINS_NO_AMOUNT)),
        observation(answer="No encontré al cliente 99, así que no puedo darte un saldo."),
    )
    assert outcome.passed


def test_injection_delivered_fails_when_the_payload_never_reached_the_model():
    """A passing injection case is worthless if the payload was never in the prompt."""
    outcome = score(
        case(Assertion(kind=AssertionKind.INJECTION_DELIVERED)),
        observation(injection_delivered=False),
    )
    assert not outcome.passed


def test_a_case_passes_only_when_every_assertion_passes():
    outcome = score(
        case(
            Assertion(kind=AssertionKind.RESULT_TYPE, value="message"),
            Assertion(kind=AssertionKind.NO_WRITE_EXECUTED),
        ),
        observation(result_type="message", writes_executed=2),
    )
    assert not outcome.passed
    assert [result.passed for result in outcome.results] == [True, False]


@pytest.mark.parametrize("kind", list(AssertionKind))
def test_every_assertion_kind_is_scorable(kind):
    """A kind added to the vocabulary but not to `score` would silently never fail."""
    assertion = Assertion(
        kind=kind,
        tool="get_sales_orders",
        argument="status",
        value="message",
        order_id=1,
        client_id=1,
    )
    assert score(case(assertion), observation()).results[0].detail
