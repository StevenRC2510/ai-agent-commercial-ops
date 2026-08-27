"""HARNESS TESTS — the case file's schema and loader. No model is involved.

The suite's own 15 cases are checked here for shape only; nothing here scores a model.
"""

import pytest
from pydantic import ValidationError

from app.domain.constants import ALLOWED_TRANSITIONS
from app.infrastructure.seed_constants import ADVERSARIAL_CLIENT_NAME, CLIENTS, ORDERS
from evals.cases import Assertion, CaseFileError, EvalCase, load_cases
from evals.cases_constants import CASES_PATH, REQUIRED_FIELDS, AssertionKind, Category

EXPECTED_CASE_COUNT = 15

ILLEGAL_TRANSITION_CASE = "illegal_transition_is_refused_by_the_policy"
SUPERVISOR_INJECTION_CASE = "injected_name_reaches_a_supervisor"
OPERATOR_INJECTION_CASE = "injected_name_backs_an_operator_escalation"

MINIMAL_CASE = """
cases:
  - id: only
    category: tool_selection
    role: operator
    message: ¿Qué órdenes están pendientes?
    asserts:
      - kind: tool_called
        tool: get_sales_orders
"""


def write(tmp_path, text):
    path = tmp_path / "cases.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_minimal_case_file_loads(tmp_path):
    cases = load_cases(write(tmp_path, MINIMAL_CASE))
    assert len(cases) == 1
    assert cases[0].id == "only"
    assert cases[0].asserts[0].kind is AssertionKind.TOOL_CALLED


def test_a_missing_file_fails_loudly(tmp_path):
    with pytest.raises(CaseFileError, match="could not be read"):
        load_cases(tmp_path / "absent.yaml")


def test_malformed_yaml_fails_loudly(tmp_path):
    with pytest.raises(CaseFileError, match="could not be read"):
        load_cases(write(tmp_path, "cases: [oops\n"))


def test_a_file_without_a_cases_list_fails_loudly(tmp_path):
    with pytest.raises(CaseFileError, match="top-level 'cases:' list"):
        load_cases(write(tmp_path, "suite: []\n"))


def test_an_empty_cases_list_fails_loudly(tmp_path):
    """Zero cases would report a 100% pass rate over nothing."""
    with pytest.raises(CaseFileError, match="holds no cases"):
        load_cases(write(tmp_path, "cases: []\n"))


def test_a_case_that_is_not_a_mapping_fails_loudly(tmp_path):
    with pytest.raises(CaseFileError, match="case #1 is not a mapping"):
        load_cases(write(tmp_path, "cases:\n  - just a string\n"))


def test_an_unknown_field_is_rejected_instead_of_ignored(tmp_path):
    """A typo in a case name would otherwise silently assert nothing."""
    with pytest.raises(CaseFileError, match="case #1 is invalid"):
        load_cases(write(tmp_path, MINIMAL_CASE + "    expects: something\n"))


def test_an_unknown_assertion_kind_is_rejected(tmp_path):
    text = MINIMAL_CASE.replace("kind: tool_called", "kind: vibes_are_good")
    with pytest.raises(CaseFileError, match="case #1 is invalid"):
        load_cases(write(tmp_path, text))


def test_an_unknown_tool_name_is_rejected(tmp_path):
    """The tool vocabulary comes from ToolName, so the case file cannot drift from it."""
    text = MINIMAL_CASE.replace("tool: get_sales_orders", "tool: drop_all_orders")
    with pytest.raises(CaseFileError, match="case #1 is invalid"):
        load_cases(write(tmp_path, text))


def test_a_case_with_no_assertions_is_rejected(tmp_path):
    """A case that asserts nothing would count as a pass and mean nothing."""
    text = MINIMAL_CASE.split("asserts:")[0] + "asserts: []\n"
    with pytest.raises(CaseFileError, match="case #1 is invalid"):
        load_cases(write(tmp_path, text))


def test_duplicate_case_ids_are_rejected(tmp_path):
    with pytest.raises(CaseFileError, match="duplicate case ids"):
        load_cases(write(tmp_path, MINIMAL_CASE + MINIMAL_CASE.replace("cases:", "")))


def test_an_assertion_missing_a_field_its_kind_needs_is_rejected():
    with pytest.raises(ValidationError, match="requires"):
        Assertion(kind=AssertionKind.TOOL_CALLED)


def test_every_assertion_kind_declares_the_fields_it_needs():
    """A kind without a row would accept an assertion that can never be evaluated."""
    assert set(REQUIRED_FIELDS) == set(AssertionKind)


def test_a_case_reports_the_orders_and_clients_its_assertions_touch():
    """The runner snapshots exactly these before the model gets a chance to move them."""
    case = EvalCase(
        id="x",
        category=Category.CONFIRMATION,
        role="supervisor",
        message="hola",
        asserts=[
            Assertion(kind=AssertionKind.ORDER_STATUS_UNCHANGED, order_id=3),
            Assertion(kind=AssertionKind.ORDER_STATUS_UNCHANGED, order_id=1),
            Assertion(kind=AssertionKind.ANSWER_CONTAINS_CLIENT_BALANCE, client_id=8),
        ],
    )
    assert case.order_ids() == (1, 3)
    assert case.client_ids() == (8,)


# --- the shipped suite ----------------------------------------------------------------


def test_the_shipped_case_file_holds_exactly_fifteen_valid_cases():
    assert len(load_cases(CASES_PATH)) == EXPECTED_CASE_COUNT


def test_every_category_the_brief_names_is_covered_by_the_shipped_suite():
    """Coverage of the categories is the design of the suite, so it is pinned here."""
    covered = {case.category for case in load_cases(CASES_PATH)}
    assert covered == set(Category)


def test_every_shipped_case_explains_why_it_earns_its_place():
    missing = [case.id for case in load_cases(CASES_PATH) if not case.rationale]
    assert not missing, f"cases without a rationale: {missing}"


def test_the_two_injection_cases_assert_the_payload_actually_reached_the_model():
    """An injection case that passes without delivery would prove nothing at all."""
    injection = [c for c in load_cases(CASES_PATH) if c.category is Category.INJECTION]
    assert len(injection) >= 2
    for case in injection:
        kinds = {assertion.kind for assertion in case.asserts}
        assert AssertionKind.INJECTION_DELIVERED in kinds, case.id


# --- the shipped suite against the seed it is grounded in -----------------------------
# Checked against seed_constants, not a seeded database: Postgres sequences are not
# transactional, so ids in the test database climb and would never match the case file.


def by_id(case_id):
    return next(case for case in load_cases(CASES_PATH) if case.id == case_id)


def test_every_order_a_case_names_is_a_row_the_seed_creates():
    """An id past the end of the seed would fail the case for the wrong reason."""
    for case in load_cases(CASES_PATH):
        for order_id in case.order_ids():
            assert 1 <= order_id <= len(ORDERS), f"{case.id}: order {order_id}"


def test_every_client_a_case_names_is_a_row_the_seed_creates():
    for case in load_cases(CASES_PATH):
        for client_id in case.client_ids():
            assert 1 <= client_id <= len(CLIENTS), f"{case.id}: client {client_id}"


def test_the_illegal_transition_case_names_an_order_the_seed_leaves_terminal():
    """If the seed ever moved order 28 out of a terminal state, the case would pass vacuously."""
    order_id = by_id(ILLEGAL_TRANSITION_CASE).order_ids()[0]
    assert not ALLOWED_TRANSITIONS[ORDERS[order_id - 1][1]]


def test_the_supervisor_injection_case_grounds_on_the_adversarial_client():
    client_id = by_id(SUPERVISOR_INJECTION_CASE).client_ids()[0]
    assert CLIENTS[client_id - 1][0] == ADVERSARIAL_CLIENT_NAME


def test_the_operator_injection_case_names_an_order_of_the_adversarial_client():
    """The user message asks to move "la orden 8"; it has to be that client's order."""
    order_id = by_id(OPERATOR_INJECTION_CASE).order_ids()[0]
    client_index = ORDERS[order_id - 1][0]
    assert CLIENTS[client_index][0] == ADVERSARIAL_CLIENT_NAME
