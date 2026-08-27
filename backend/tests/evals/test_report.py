"""HARNESS TESTS — the report's arithmetic and layout.

Every CaseRun below is fabricated by hand to exercise the renderer. These numbers are
test fixtures, not measurements: no model produced any of them.
"""

from datetime import UTC, datetime
from decimal import Decimal

from app.application.constants import Model
from evals.cases import Assertion, EvalCase
from evals.cases_constants import AssertionKind, Category
from evals.report import render_report, summarise
from evals.scoring import AssertionResult, CaseOutcome, CaseRun, Observation, score

GENERATED = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)

EMPTY_OBSERVATION = Observation(
    result_type="message",
    reason_code=None,
    answer="",
    proposed_calls=(),
    denials={},
    writes_executed=0,
    order_statuses_before={},
    order_statuses_after={},
    client_balances={},
    injection_delivered=False,
)


def a_case(case_id, category, *asserts, role="operator"):
    return EvalCase(
        id=case_id,
        category=category,
        role=role,
        message="¿Qué órdenes están pendientes?",
        asserts=list(asserts),
    )


def a_run(case, *, passed=True, latency_ms=1000, cost="0.001", answer="", input_tokens=1000):
    results = tuple(
        AssertionResult(assertion=assertion, passed=passed, detail="observed something")
        for assertion in case.asserts
    )
    return CaseRun(
        outcome=CaseOutcome(case=case, results=results),
        observation=Observation(**{**EMPTY_OBSERVATION.__dict__, "answer": answer}),
        model=Model.HAIKU_4_5,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=50,
        cost_usd=Decimal(cost),
        trace_id="3f2a1b9c",
    )


def header_args():
    return {
        "model": Model.HAIKU_4_5,
        "prompt_version": "2026-08-27.1",
        "temperature": 0.0,
        "generated_at": GENERATED,
    }


TOOL_ASSERTION = Assertion(kind=AssertionKind.TOOL_CALLED, tool="get_sales_orders")
TYPE_ASSERTION = Assertion(kind=AssertionKind.RESULT_TYPE, value="message")


# --- summary arithmetic ---------------------------------------------------------------


def test_an_empty_run_summarises_to_zero_without_dividing_by_zero():
    summary = summarise(())
    assert summary.total == 0
    assert summary.pass_rate == 0.0
    assert summary.total_cost_usd == Decimal(0)


def test_the_overall_pass_rate_counts_cases_not_assertions():
    runs = (
        a_run(a_case("a", Category.TOOL_SELECTION, TOOL_ASSERTION, TYPE_ASSERTION)),
        a_run(a_case("b", Category.TOOL_SELECTION, TOOL_ASSERTION), passed=False),
    )
    summary = summarise(runs)
    assert (summary.passed, summary.total) == (1, 2)
    assert summary.pass_rate == 50.0


def test_tool_selection_accuracy_counts_only_tool_shaped_assertions():
    """A case that refuses correctly must not inflate the tool-selection number."""
    runs = (
        a_run(a_case("a", Category.TOOL_SELECTION, TOOL_ASSERTION, TYPE_ASSERTION)),
        a_run(a_case("b", Category.AUTHORIZATION, TYPE_ASSERTION), passed=False),
    )
    summary = summarise(runs)
    assert (summary.tool_selection_passed, summary.tool_selection_total) == (1, 1)


def test_the_correct_refusal_rate_covers_the_authorization_and_injection_cases():
    runs = (
        a_run(a_case("a", Category.TOOL_SELECTION, TYPE_ASSERTION)),
        a_run(a_case("b", Category.AUTHORIZATION, TYPE_ASSERTION)),
        a_run(a_case("c", Category.INJECTION, TYPE_ASSERTION), passed=False),
    )
    summary = summarise(runs)
    assert (summary.refusal_passed, summary.refusal_total) == (1, 2)


def test_median_latency_is_a_median_not_a_mean():
    """One slow case must not move the number the model comparison table reports."""
    runs = tuple(
        a_run(a_case(str(index), Category.TOOL_SELECTION, TYPE_ASSERTION), latency_ms=latency)
        for index, latency in enumerate([900, 1000, 20000])
    )
    assert summarise(runs).median_latency_ms == 1000


def test_total_cost_is_the_sum_of_what_each_case_cost():
    runs = (
        a_run(a_case("a", Category.TOOL_SELECTION, TYPE_ASSERTION), cost="0.00125"),
        a_run(a_case("b", Category.TOOL_SELECTION, TYPE_ASSERTION), cost="0.00200"),
    )
    assert summarise(runs).total_cost_usd == Decimal("0.00325")


def test_mean_input_tokens_is_reported_per_case():
    runs = (
        a_run(a_case("a", Category.TOOL_SELECTION, TYPE_ASSERTION), input_tokens=1000),
        a_run(a_case("b", Category.TOOL_SELECTION, TYPE_ASSERTION), input_tokens=2000),
    )
    assert summarise(runs).mean_input_tokens == 1500


def test_every_category_present_in_the_runs_appears_in_the_breakdown():
    runs = (
        a_run(a_case("a", Category.GROUNDING, TYPE_ASSERTION)),
        a_run(a_case("b", Category.GROUNDING, TYPE_ASSERTION), passed=False),
    )
    assert summarise(runs).by_category[Category.GROUNDING] == (1, 2)


# --- rendering ------------------------------------------------------------------------


def test_a_report_with_no_runs_says_so_instead_of_showing_an_empty_table():
    """The state this project shipped in: a working harness and no funded account."""
    text = render_report((), **header_args())
    assert "No cases were run" in text
    assert "%" not in text


def test_the_header_names_the_model_and_the_prompt_version_that_produced_the_numbers():
    """A pass rate without the prompt that produced it cannot be compared to anything."""
    text = render_report(
        (a_run(a_case("a", Category.TOOL_SELECTION, TYPE_ASSERTION)),), **header_args()
    )
    assert Model.HAIKU_4_5.value in text
    assert "2026-08-27.1" in text
    assert "2026-08-27T12:00:00+00:00" in text


def test_each_case_shows_its_verdict_its_assertions_and_what_was_observed():
    case = a_case("pending_orders_list", Category.TOOL_SELECTION, TOOL_ASSERTION)
    text = render_report((a_run(case),), **header_args())
    assert "pending_orders_list" in text
    assert "PASS" in text
    assert "tool_called" in text
    assert "get_sales_orders" in text
    assert "observed something" in text


def test_a_failing_assertion_is_marked_and_its_detail_is_shown():
    case = a_case("b", Category.AUTHORIZATION, TYPE_ASSERTION)
    text = render_report((a_run(case, passed=False),), **header_args())
    assert "FAIL" in text
    assert "observed something" in text


def test_each_case_reports_its_own_cost_and_trace_id():
    """Measuring what an eval run costs is part of the point; the trace id makes it auditable."""
    case = a_case("a", Category.TOOL_SELECTION, TYPE_ASSERTION)
    text = render_report((a_run(case, cost="0.00125"),), **header_args())
    assert "0.00125" in text
    assert "3f2a1b9c" in text


def test_a_long_answer_is_excerpted_rather_than_dumped_whole():
    case = a_case("a", Category.TOOL_SELECTION, TYPE_ASSERTION)
    text = render_report((a_run(case, answer="x" * 5000),), **header_args())
    assert "x" * 5000 not in text
    assert "…" in text


def test_a_run_that_failed_with_an_exception_shows_the_error():
    case = a_case("a", Category.TOOL_SELECTION, TYPE_ASSERTION)
    run = a_run(case, passed=False)
    broken = CaseRun(**{**run.__dict__, "error": "AttributeError: boom"})
    assert "AttributeError: boom" in render_report((broken,), **header_args())


def test_the_report_of_a_real_outcome_reads_the_same_as_a_fabricated_one():
    """render_report takes CaseRun and nothing else, so the runner cannot bias the layout."""
    case = a_case("a", Category.TOOL_SELECTION, TYPE_ASSERTION)
    outcome = score(case, EMPTY_OBSERVATION)
    run = CaseRun(
        outcome=outcome,
        observation=EMPTY_OBSERVATION,
        model=Model.HAIKU_4_5,
        latency_ms=10,
        input_tokens=1,
        output_tokens=1,
        cost_usd=Decimal("0"),
        trace_id="abc",
    )
    assert "PASS" in render_report((run,), **header_args())
