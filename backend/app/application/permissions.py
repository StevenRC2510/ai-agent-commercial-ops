"""AUTHORIZATION TABLE — the complete answer to "what may each role do".

Isolated so that nothing — no config, no environment, no module added later —
can influence who is allowed to do what. That isolation is enforced by
tests/architecture/test_imports.py, which parses this file and asserts it
imports nothing beyond `types`, a pure type constructor with no configuration,
I/O, or state of its own. The table itself is immutable at runtime: it is
wrapped in MappingProxyType, so a key cannot be reassigned or added from
outside this module. frozenset values close the same gap one level down, for
the sets of tool names each role maps to.
"""

from types import MappingProxyType

ROLE_PERMISSIONS: MappingProxyType[str, frozenset[str]] = MappingProxyType(
    {
        "operator": frozenset({"get_sales_orders", "get_client_balance"}),
        "supervisor": frozenset({"get_sales_orders", "get_client_balance", "update_order_status"}),
    }
)

REQUIRES_CONFIRMATION: frozenset[str] = frozenset({"update_order_status"})
