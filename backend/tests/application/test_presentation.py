"""Presentation tests: denial text lookup and the consent-summary sentence."""

import pytest

from app.application import messages, policy, presentation
from app.domain.actions import OrderStatusChange
from app.domain.constants import ALLOWED_TRANSITIONS, OrderStatus


def test_every_denial_reason_has_a_message():
    """Type-level bridge: mypy stops a reason not in the enum, this stops an enum member with
    no message. Task 9 cannot add a denial code without both."""
    assert set(policy.DenialReason) == set(messages.DENIAL_TEXTS)


@pytest.mark.parametrize("reason", [r.value for r in policy.DenialReason])
def test_render_denial_returns_text_for_every_denial_reason(reason):
    assert presentation.render_denial(reason)


def test_every_wire_reason_renders_exactly_its_table_text():
    """The whole table, reached through the wire string the policy layer emits."""
    expected = {reason.value: text for reason, text in messages.DENIAL_TEXTS.items()}
    assert {reason: presentation.render_denial(reason) for reason in expected} == expected


def _change(from_status, to_status, reason="el taller ya lo recibio"):
    return OrderStatusChange(
        order_id=123, from_status=from_status, to_status=to_status, reason=reason
    )


def test_summary_uses_spanish_labels_and_names_the_order():
    summary = presentation.render_summary(_change(OrderStatus.IN_PROGRESS, OrderStatus.DELIVERED))
    assert summary == (
        'Cambiar la orden #123 de "en proceso" a "entregada". ' "Motivo: el taller ya lo recibio"
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [(current, target) for current in OrderStatus for target in ALLOWED_TRANSITIONS[current]],
)
def test_summary_never_leaks_an_english_status_value(current, target):
    summary = presentation.render_summary(_change(current, target))
    for status in OrderStatus:
        assert status.value not in summary


def test_render_summary_is_deterministic():
    """The persisted consent string must be reproducible from the change."""
    change = _change(OrderStatus.PENDING, OrderStatus.CANCELLED)
    assert presentation.render_summary(change) == presentation.render_summary(change)


def test_render_summary_depends_only_on_the_change_value():
    a = _change(OrderStatus.PENDING, OrderStatus.CANCELLED, reason="motivo uno")
    b = _change(OrderStatus.PENDING, OrderStatus.CANCELLED, reason="motivo uno")
    assert presentation.render_summary(a) == presentation.render_summary(b)


def test_reason_is_reproduced_verbatim_including_punctuation_and_accents():
    reason = 'el cliente dijo: "¡ya lo recibió, gracias!" - confirmado'
    summary = presentation.render_summary(
        _change(OrderStatus.PENDING, OrderStatus.IN_PROGRESS, reason=reason)
    )
    assert summary.endswith(f"Motivo: {reason}")
