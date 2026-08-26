"""Request-scoped identity and tracing data."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditContext:
    """Who is acting and under which trace, for audit records only.

    Never used to make an authorization decision — that is the execution
    layer's responsibility, based on its own permission checks.
    """

    actor: str
    role: str
    trace_id: str
