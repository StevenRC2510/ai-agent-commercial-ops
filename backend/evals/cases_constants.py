"""The closed vocabulary a case file may use, and the fields each assertion needs."""

from collections.abc import Mapping
from enum import Enum
from pathlib import Path

CASES_PATH = Path(__file__).resolve().parent / "cases.yaml"


class Category(str, Enum):
    """What a case is evidence about. The report breaks the pass rate down by these."""

    TOOL_SELECTION = "tool_selection"
    AMBIGUITY = "ambiguity"
    AUTHORIZATION = "authorization"
    INJECTION = "injection"
    GROUNDING = "grounding"
    CONFIRMATION = "confirmation"


# Categories whose cases are refusals: the "correct refusal rate" is measured over these.
REFUSAL_CATEGORIES: frozenset[Category] = frozenset({Category.AUTHORIZATION, Category.INJECTION})


class AssertionKind(str, Enum):
    """Every assertion is an observable outcome: a tool, an argument, a code, or a row.

    None of them reads the model's prose, so a right answer in different words passes.
    """

    TOOL_CALLED = "tool_called"
    TOOL_NOT_CALLED = "tool_not_called"
    TOOL_ARGUMENT_EQUALS = "tool_argument_equals"
    TOOL_ARGUMENT_PRESENT = "tool_argument_present"
    RESULT_TYPE = "result_type"
    REASON_CODE = "reason_code"
    POLICY_DENIED = "policy_denied"
    NO_WRITE_EXECUTED = "no_write_executed"
    ORDER_STATUS_UNCHANGED = "order_status_unchanged"
    ANSWER_CONTAINS_CLIENT_BALANCE = "answer_contains_client_balance"
    ANSWER_CONTAINS_NO_AMOUNT = "answer_contains_no_amount"
    INJECTION_DELIVERED = "injection_delivered"


# Kinds whose pass rate is the tool-selection accuracy the model comparison table reports.
TOOL_SELECTION_KINDS: frozenset[AssertionKind] = frozenset(
    {
        AssertionKind.TOOL_CALLED,
        AssertionKind.TOOL_NOT_CALLED,
        AssertionKind.TOOL_ARGUMENT_EQUALS,
        AssertionKind.TOOL_ARGUMENT_PRESENT,
    }
)

REQUIRED_FIELDS: Mapping[AssertionKind, tuple[str, ...]] = {
    AssertionKind.TOOL_CALLED: ("tool",),
    AssertionKind.TOOL_NOT_CALLED: ("tool",),
    AssertionKind.TOOL_ARGUMENT_EQUALS: ("tool", "argument", "value"),
    AssertionKind.TOOL_ARGUMENT_PRESENT: ("tool", "argument"),
    AssertionKind.RESULT_TYPE: ("value",),
    AssertionKind.REASON_CODE: ("value",),
    AssertionKind.POLICY_DENIED: ("tool", "value"),
    AssertionKind.NO_WRITE_EXECUTED: (),
    AssertionKind.ORDER_STATUS_UNCHANGED: ("order_id",),
    AssertionKind.ANSWER_CONTAINS_CLIENT_BALANCE: ("client_id",),
    AssertionKind.ANSWER_CONTAINS_NO_AMOUNT: (),
    AssertionKind.INJECTION_DELIVERED: (),
}
