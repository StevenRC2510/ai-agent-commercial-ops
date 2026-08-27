"""AUTHORIZATION VOCABULARY AND TABLE — the complete answer to "what may each role do".

Imports almost nothing by design; tests/architecture/test_imports.py enforces it.
"""

from enum import Enum
from types import MappingProxyType


class Role(str, Enum):
    OPERATOR = "operator"
    SUPERVISOR = "supervisor"


# Derived, never restated: a hand-written copy of the roles would drift from the enum above.
ROLE_VALUES: frozenset[str] = frozenset(role.value for role in Role)


class ToolName(str, Enum):
    GET_SALES_ORDERS = "get_sales_orders"
    GET_CLIENT_BALANCE = "get_client_balance"
    UPDATE_ORDER_STATUS = "update_order_status"


class DenialReason(str, Enum):
    """The closed set of reasons a call may be refused, by the policy, /confirm or the edge.

    CONSENT_UNUSABLE is deliberately one code for every unusable consent: unknown, expired
    and already-spent must stay indistinguishable, or /confirm becomes an oracle over ids.
    """

    UNKNOWN_TOOL = "unknown_tool"
    ROLE_LACKS_PERMISSION = "role_lacks_permission"
    INVALID_ARGUMENTS = "invalid_arguments"
    ORDER_NOT_FOUND = "order_not_found"
    INVALID_STATUS_TRANSITION = "invalid_status_transition"
    STATE_CHANGED_SINCE_CONSENT = "state_changed_since_consent"
    CONSENT_UNUSABLE = "consent_unusable"
    RATE_LIMITED = "rate_limited"


ROLE_PERMISSIONS: MappingProxyType[Role, frozenset[ToolName]] = MappingProxyType(
    {
        Role.OPERATOR: frozenset({ToolName.GET_SALES_ORDERS, ToolName.GET_CLIENT_BALANCE}),
        Role.SUPERVISOR: frozenset(
            {ToolName.GET_SALES_ORDERS, ToolName.GET_CLIENT_BALANCE, ToolName.UPDATE_ORDER_STATUS}
        ),
    }
)

REQUIRES_CONFIRMATION: frozenset[ToolName] = frozenset({ToolName.UPDATE_ORDER_STATUS})
