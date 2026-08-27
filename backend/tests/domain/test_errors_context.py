import dataclasses

import pytest

from app.domain.context import AuditContext
from app.domain.errors import (
    ClientNotFoundError,
    DomainError,
    InvalidTransitionError,
    OrderNotFoundError,
)


@pytest.mark.parametrize("error", [ClientNotFoundError, OrderNotFoundError, InvalidTransitionError])
def test_domain_errors_share_a_common_base(error):
    assert issubclass(error, DomainError)


def test_audit_context_is_immutable():
    ctx = AuditContext(actor="u-1", role="operator", trace_id="abc12345")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.role = "supervisor"


def test_audit_context_compares_by_value():
    a = AuditContext(actor="u-1", role="operator", trace_id="abc12345")
    b = AuditContext(actor="u-1", role="operator", trace_id="abc12345")
    assert a == b
