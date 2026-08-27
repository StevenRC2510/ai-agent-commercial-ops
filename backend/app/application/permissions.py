"""AUTHORIZATION TABLE — the complete answer to "what may each role do".

Imports almost nothing by design; tests/architecture/test_imports.py enforces it.
"""

from types import MappingProxyType

ROLE_PERMISSIONS: MappingProxyType[str, frozenset[str]] = MappingProxyType(
    {
        "operator": frozenset({"get_sales_orders", "get_client_balance"}),
        "supervisor": frozenset({"get_sales_orders", "get_client_balance", "update_order_status"}),
    }
)

REQUIRES_CONFIRMATION: frozenset[str] = frozenset({"update_order_status"})
