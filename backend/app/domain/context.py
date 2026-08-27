"""Request-scoped identity and tracing data."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditContext:
    """Who is acting and under which trace, for audit records only.

    Never used for authorization decisions - that is the policy layer's job.
    """

    actor: str
    role: str
    trace_id: str
