"""PRESENTATION — the only place the Spanish text a human reads gets built.

Imports domain and the pure vocabulary/message tables, never policy: rendering stays
independent of decisions.
"""

from app.application.messages import DENIAL_TEXTS
from app.application.permissions import DenialReason
from app.domain.actions import OrderStatusChange
from app.domain.constants import STATUS_LABELS_ES


def render_denial(reason: str) -> str:
    """Human-readable Spanish message for a PolicyDecision denial reason code."""
    return DENIAL_TEXTS[DenialReason(reason)]


def render_summary(change: OrderStatusChange) -> str:
    """Consent sentence a supervisor approves before the write it describes executes."""
    old = STATUS_LABELS_ES[change.from_status]
    new = STATUS_LABELS_ES[change.to_status]
    return f'Cambiar la orden #{change.order_id} de "{old}" a "{new}". ' f"Motivo: {change.reason}"
