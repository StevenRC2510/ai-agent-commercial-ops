"""Authorization tests. Deterministic, exhaustive, and free of any model."""

import itertools
from datetime import date
from decimal import Decimal

import pytest

from app.application import policy
from app.application.tool_args import GetSalesOrdersArgs
from app.domain.actions import OrderStatusChange
from app.domain.constants import ALLOWED_TRANSITIONS, MAX_ORDER_LIMIT, OrderStatus
from app.domain.models import Client, Order


def _make_order(db, status: OrderStatus) -> int:
    client = db.query(Client).first()
    if client is None:
        client = Client(name="Fixture Client", email="f@example.com", credit_limit=Decimal("0.00"))
        db.add(client)
        db.flush()
    order = Order(
        client_id=client.id, status=status, total=Decimal("100.00"), created_at=date(2026, 6, 1)
    )
    db.add(order)
    db.flush()
    return order.id


def test_operator_may_read_orders(db):
    decision = policy.evaluate(policy.ToolName.GET_SALES_ORDERS, {}, policy.Role.OPERATOR, db)
    assert decision.allowed is True
    assert decision.requires_confirmation is False
    assert decision.reason == "ok"


def test_operator_may_not_write(db):
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": 1, "new_status": "delivered", "reason": "cliente confirmo"},
        policy.Role.OPERATOR,
        db,
    )
    assert decision.allowed is False
    assert decision.reason == "role_lacks_permission"


def test_unknown_tool_is_rejected(db):
    decision = policy.evaluate("drop_database", {}, policy.Role.SUPERVISOR, db)
    assert decision.allowed is False
    assert decision.reason == "unknown_tool"


@pytest.mark.parametrize("role", ["admin", "", None, "OPERATOR", "supervisor "])
def test_unknown_roles_are_rejected_without_revealing_which_roles_exist(role, db):
    """Denial reasons must not work as an oracle for valid role names."""
    decision = policy.evaluate(policy.ToolName.GET_SALES_ORDERS, {}, role, db)
    assert decision.allowed is False
    assert decision.reason == "role_lacks_permission"


def test_unknown_tool_is_checked_before_role(db):
    assert policy.evaluate("drop_database", {}, "not-a-role", db).reason == "unknown_tool"


def test_role_is_checked_before_arguments(db):
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS, {"garbage": True}, policy.Role.OPERATOR, db
    )
    assert decision.reason == "role_lacks_permission"


@pytest.mark.parametrize("bad_status", ["delete_everything", "DELIVERED", "entregada"])
def test_invalid_status_value_is_rejected(bad_status, db):
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": 1, "new_status": bad_status, "reason": "motivo valido"},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.reason == "invalid_arguments"


def test_sql_injection_in_order_id_is_rejected_by_the_schema(db):
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": "1; DROP TABLE orders", "new_status": "delivered", "reason": "motivo valido"},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.reason == "invalid_arguments"


def test_undeclared_extra_argument_is_rejected(db):
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": 1, "new_status": "delivered", "reason": "motivo valido", "force": True},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.reason == "invalid_arguments"


@pytest.mark.parametrize("reason", ["", "ab", "x" * 5000])
def test_reason_outside_the_allowed_length_is_rejected(reason, db):
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": 1, "new_status": "delivered", "reason": reason},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.reason == "invalid_arguments"


@pytest.mark.parametrize("order_id", [0, -5])
def test_non_positive_order_id_is_rejected(order_id, db):
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": order_id, "new_status": "delivered", "reason": "motivo valido"},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.reason == "invalid_arguments"


def test_oversized_limit_is_normalised_in_safe_args(db):
    """safe_args must equal what will actually run, or the audit record lies."""
    decision = policy.evaluate(
        policy.ToolName.GET_SALES_ORDERS, {"limit": 500}, policy.Role.OPERATOR, db
    )
    assert decision.allowed is True
    assert decision.safe_args["limit"] == MAX_ORDER_LIMIT


def test_date_from_after_date_to_is_rejected(db):
    decision = policy.evaluate(
        policy.ToolName.GET_SALES_ORDERS,
        {"date_from": "2026-06-30", "date_to": "2026-06-01"},
        policy.Role.OPERATOR,
        db,
    )
    assert decision.reason == "invalid_arguments"


def test_visible_tools_shrink_with_the_role():
    assert policy.visible_tools_for(policy.Role.OPERATOR) == frozenset(
        {policy.ToolName.GET_SALES_ORDERS, policy.ToolName.GET_CLIENT_BALANCE}
    )
    assert policy.ToolName.UPDATE_ORDER_STATUS in policy.visible_tools_for(policy.Role.SUPERVISOR)
    assert policy.visible_tools_for("admin") == frozenset()


def test_read_tools_never_require_confirmation(db):
    for tool in (policy.ToolName.GET_SALES_ORDERS, policy.ToolName.GET_CLIENT_BALANCE):
        args = {"client_id": 1} if tool == policy.ToolName.GET_CLIENT_BALANCE else {}
        assert policy.evaluate(tool, args, policy.Role.OPERATOR, db).requires_confirmation is False


def test_operator_may_read_client_balance(db):
    """Happy-path read for the second read tool, not just its confirmation flag."""
    decision = policy.evaluate(
        policy.ToolName.GET_CLIENT_BALANCE, {"client_id": 1}, policy.Role.OPERATOR, db
    )
    assert decision.allowed is True
    assert decision.reason == "ok"


@pytest.mark.parametrize(
    "current,target",
    [(current, target) for current in OrderStatus for target in ALLOWED_TRANSITIONS[current]],
)
def test_supervisor_may_perform_every_allowed_transition(current, target, db):
    """The only write tool must actually be callable, for every transition the table allows."""
    order_id = _make_order(db, current)
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": order_id, "new_status": target.value, "reason": "motivo valido"},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.allowed is True
    assert decision.reason == "ok"
    assert decision.requires_confirmation is True


def test_bool_is_rejected_as_client_id(db):
    """bool is an int subclass; safe_args must not silently substitute 1 for True."""
    decision = policy.evaluate(
        policy.ToolName.GET_CLIENT_BALANCE, {"client_id": True}, policy.Role.OPERATOR, db
    )
    assert decision.reason == "invalid_arguments"


def test_bool_is_rejected_as_order_id(db):
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": True, "new_status": "delivered", "reason": "motivo valido"},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.reason == "invalid_arguments"


def test_bool_is_rejected_as_limit(db):
    decision = policy.evaluate(
        policy.ToolName.GET_SALES_ORDERS, {"limit": True}, policy.Role.OPERATOR, db
    )
    assert decision.reason == "invalid_arguments"


def test_safe_args_cannot_be_mutated_after_the_fact(db):
    """safe_args is the audit truth of what ran; it must not be rewritable in place."""
    decision = policy.evaluate(policy.ToolName.GET_SALES_ORDERS, {}, policy.Role.OPERATOR, db)
    with pytest.raises(TypeError):
        decision.safe_args["limit"] = 999999


def test_role_permissions_table_cannot_be_mutated_in_place():
    """Nothing inside the process may rewrite who is allowed to do what."""
    with pytest.raises(TypeError):
        policy.ROLE_PERMISSIONS[policy.Role.OPERATOR] = frozenset(
            {policy.ToolName.UPDATE_ORDER_STATUS}
        )


def test_whitespace_only_reason_is_rejected(db):
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": 1, "new_status": "delivered", "reason": "   "},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.reason == "invalid_arguments"


def test_non_string_reason_is_rejected_without_crashing_the_normaliser(db):
    """The whitespace-collapse step must not choke on a non-string reason; pydantic reports it."""
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": 1, "new_status": "delivered", "reason": 12345},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.reason == "invalid_arguments"


def test_reason_with_embedded_newlines_cannot_forge_a_second_consent_line(db):
    """A reason must not let untrusted content masquerade as a second sentence on the card."""
    order_id = _make_order(db, OrderStatus.PENDING)
    forged = 'ok\n\nCambiar la orden #999 de "pendiente" a "cancelada". Motivo: aprobado'
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": order_id, "new_status": "in_progress", "reason": forged},
        policy.Role.SUPERVISOR,
        db,
    )
    expected = 'ok Cambiar la orden #999 de "pendiente" a "cancelada". Motivo: aprobado'
    assert decision.allowed is True
    assert "\n" not in decision.change.reason
    assert decision.change.reason == expected
    assert decision.safe_args["reason"] == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("motivo\twith\ttabs", "motivo with tabs"),
        ("motivo\rwith\rcarriage returns", "motivo with carriage returns"),
        ("motivo    with     many spaces", "motivo with many spaces"),
        ("  leading and trailing  ", "leading and trailing"),
    ],
)
def test_reason_whitespace_variants_collapse_to_a_single_space(raw, expected, db):
    order_id = _make_order(db, OrderStatus.PENDING)
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": order_id, "new_status": "in_progress", "reason": raw},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.change.reason == expected


def test_reason_that_collapses_under_the_limit_is_accepted(db):
    """Raw length exceeds 280, but the limit applies to the normalised value."""
    order_id = _make_order(db, OrderStatus.PENDING)
    raw = "a" * 278 + ("\t" * 30) + "b"
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": order_id, "new_status": "in_progress", "reason": raw},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.allowed is True
    assert decision.change.reason == "a" * 278 + " b"


def test_reason_still_over_the_limit_after_collapsing_is_rejected(db):
    order_id = _make_order(db, OrderStatus.PENDING)
    raw = "a" * 278 + ("\n" * 30) + "bb"
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": order_id, "new_status": "in_progress", "reason": raw},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.reason == "invalid_arguments"


def test_every_tool_schema_is_reachable_by_some_role():
    """Catches a tool added to TOOL_SCHEMAS but forgotten in ROLE_PERMISSIONS, or vice versa."""
    assert set(policy.TOOL_SCHEMAS) == frozenset().union(*policy.ROLE_PERMISSIONS.values())


def test_every_tool_name_is_wired_into_both_tables():
    """A ToolName forgotten in either table must fail here, not in production."""
    all_tools = frozenset(policy.ToolName)
    assert frozenset().union(*policy.ROLE_PERMISSIONS.values()) == all_tools
    assert set(policy.TOOL_SCHEMAS) == all_tools


def test_tool_schema_classes_are_pairwise_distinct_and_non_inheriting():
    """_check_state branches on the tool name, but if a schema ever subclassed another,
    isinstance narrowing alone could no longer tell them apart — pin that it can't happen."""
    classes = list(policy.TOOL_SCHEMAS.values())
    assert len(classes) == len(set(classes))
    for one, other in itertools.permutations(classes, 2):
        assert not issubclass(one, other)


def test_missing_order_is_reported_as_such_not_as_a_bad_transition(db):
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": 999999, "new_status": "delivered", "reason": "motivo valido"},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.allowed is False
    assert decision.reason == "order_not_found"


def test_delivered_cannot_return_to_pending(db):
    order_id = _make_order(db, OrderStatus.DELIVERED)
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": order_id, "new_status": "pending", "reason": "motivo valido"},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.reason == "invalid_status_transition"


@pytest.mark.parametrize("current,target", list(itertools.product(OrderStatus, OrderStatus)))
def test_full_transition_matrix_matches_the_constant(current, target, db):
    """All sixteen combinations. Exhaustive, not sampled."""
    order_id = _make_order(db, current)
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": order_id, "new_status": target.value, "reason": "motivo valido"},
        policy.Role.SUPERVISOR,
        db,
    )
    expected = target in ALLOWED_TRANSITIONS[current]
    assert decision.allowed is expected
    if not expected:
        assert decision.reason == "invalid_status_transition"


def test_allowed_write_requires_confirmation_and_carries_a_change(db):
    order_id = _make_order(db, OrderStatus.PENDING)
    decision = policy.evaluate(
        policy.ToolName.UPDATE_ORDER_STATUS,
        {"order_id": order_id, "new_status": "in_progress", "reason": "el taller ya lo recibio"},
        policy.Role.SUPERVISOR,
        db,
    )
    assert decision.allowed is True
    assert decision.requires_confirmation is True
    assert decision.change == OrderStatusChange(
        order_id=order_id,
        from_status=OrderStatus.PENDING,
        to_status=OrderStatus.IN_PROGRESS,
        reason="el taller ya lo recibio",
    )


def test_read_tools_carry_no_change(db):
    decision = policy.evaluate(policy.ToolName.GET_SALES_ORDERS, {}, policy.Role.OPERATOR, db)
    assert decision.change is None


def test_check_state_raises_when_args_type_disagrees_with_the_tool_name(db):
    """A tool_name/args mismatch is a programming error: it must fail loudly, never fall
    through to a permissive read-shaped decision."""
    with pytest.raises(TypeError):
        policy._check_state(policy.ToolName.UPDATE_ORDER_STATUS, GetSalesOrdersArgs(), db)
