"""AUTHORIZATION VOCABULARY AND TABLE — the complete answer to "what may each role do".

Imports almost nothing by design; tests/architecture/test_imports.py enforces it.
"""

from enum import Enum
from types import MappingProxyType


class Role(str, Enum):
    OPERATOR = "operator"
    SUPERVISOR = "supervisor"


class ToolName(str, Enum):
    GET_SALES_ORDERS = "get_sales_orders"
    GET_CLIENT_BALANCE = "get_client_balance"
    UPDATE_ORDER_STATUS = "update_order_status"


class DenialReason(str, Enum):
    """The closed set of reasons evaluate() may deny a call. Task 9 adds no new member lightly."""

    UNKNOWN_TOOL = "unknown_tool"
    ROLE_LACKS_PERMISSION = "role_lacks_permission"
    INVALID_ARGUMENTS = "invalid_arguments"
    ORDER_NOT_FOUND = "order_not_found"
    INVALID_STATUS_TRANSITION = "invalid_status_transition"
    STATE_CHANGED_SINCE_CONSENT = "state_changed_since_consent"


ROLE_PERMISSIONS: MappingProxyType[Role, frozenset[ToolName]] = MappingProxyType(
    {
        Role.OPERATOR: frozenset({ToolName.GET_SALES_ORDERS, ToolName.GET_CLIENT_BALANCE}),
        Role.SUPERVISOR: frozenset(
            {ToolName.GET_SALES_ORDERS, ToolName.GET_CLIENT_BALANCE, ToolName.UPDATE_ORDER_STATUS}
        ),
    }
)

REQUIRES_CONFIRMATION: frozenset[ToolName] = frozenset({ToolName.UPDATE_ORDER_STATUS})
