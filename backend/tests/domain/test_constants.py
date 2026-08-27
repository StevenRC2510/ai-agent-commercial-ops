from app.domain.constants import (
    ALLOWED_TRANSITIONS,
    DEFAULT_ORDER_LIMIT,
    MAX_ORDER_LIMIT,
    STATUS_LABELS_ES,
    VALID_STATUSES,
    OrderStatus,
)


def test_valid_statuses_is_derived_from_the_enum():
    """Guards the single source of truth: no hand-written duplicate list."""
    assert tuple(s.value for s in OrderStatus) == VALID_STATUSES


def test_every_status_has_a_spanish_label():
    assert set(STATUS_LABELS_ES) == set(OrderStatus)


def test_terminal_statuses_allow_no_transitions():
    assert ALLOWED_TRANSITIONS[OrderStatus.DELIVERED] == frozenset()
    assert ALLOWED_TRANSITIONS[OrderStatus.CANCELLED] == frozenset()


def test_every_status_appears_in_the_transition_table():
    assert set(ALLOWED_TRANSITIONS) == set(OrderStatus)


def test_transition_table_matches_the_business_rules() -> None:
    """The only independent check of the table's content, not just its shape."""
    assert {
        OrderStatus.PENDING: frozenset({OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED}),
        OrderStatus.IN_PROGRESS: frozenset({OrderStatus.DELIVERED, OrderStatus.CANCELLED}),
        OrderStatus.DELIVERED: frozenset(),
        OrderStatus.CANCELLED: frozenset(),
    } == ALLOWED_TRANSITIONS


def test_no_status_transitions_to_itself():
    for status, targets in ALLOWED_TRANSITIONS.items():
        assert status not in targets


def test_limits_are_ordered():
    assert 0 < DEFAULT_ORDER_LIMIT <= MAX_ORDER_LIMIT
