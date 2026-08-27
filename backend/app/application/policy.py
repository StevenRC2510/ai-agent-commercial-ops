"""POLICY — decides what is allowed. Never renders text, never calls a model.

Import whitelist, enforced by tests/architecture/test_imports.py: dataclasses, enum, types,
typing, pydantic, sqlalchemy, app.application.permissions, app.application.tool_args, app.domain.*
"""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.application.permissions import REQUIRES_CONFIRMATION, ROLE_PERMISSIONS
from app.application.tool_args import TOOL_SCHEMAS
from app.domain.actions import OrderStatusChange


class DenialReason(str, Enum):
    """The closed set of reasons evaluate() may deny a call. Task 9 adds no new member lightly."""

    UNKNOWN_TOOL = "unknown_tool"
    ROLE_LACKS_PERMISSION = "role_lacks_permission"
    INVALID_ARGUMENTS = "invalid_arguments"
    ORDER_NOT_FOUND = "order_not_found"
    INVALID_STATUS_TRANSITION = "invalid_status_transition"


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    requires_confirmation: bool
    reason: str  # "ok", or a DenialReason value — plain str on the wire, not the enum itself
    safe_args: MappingProxyType[str, Any] | None = None
    change: OrderStatusChange | None = None


def _deny(reason: DenialReason) -> PolicyDecision:
    return PolicyDecision(allowed=False, requires_confirmation=False, reason=reason.value)


def visible_tools_for(role: str) -> frozenset[str]:
    """Tools that will be declared to the model for this role.

    Defence in depth: this shrinks the attack surface and saves tokens, but
    evaluate() validates every call regardless — hiding a tool fails open if the
    model hallucinates a name, evaluate() fails closed.
    """
    return ROLE_PERMISSIONS.get(role, frozenset())


def evaluate(tool_name: str, raw_args: dict, role: str, db: Session) -> PolicyDecision:
    """Decide whether this call may run. The order of checks is significant."""
    schema = TOOL_SCHEMAS.get(tool_name)
    if schema is None:
        return _deny(DenialReason.UNKNOWN_TOOL)

    if tool_name not in ROLE_PERMISSIONS.get(role, frozenset()):
        # Unknown, empty, and None roles all fall through to this same reason so
        # denial codes never work as an oracle for which role names are valid.
        return _deny(DenialReason.ROLE_LACKS_PERMISSION)

    try:
        args = schema(**raw_args)
    except (ValidationError, TypeError):
        return _deny(DenialReason.INVALID_ARGUMENTS)

    return _check_state(tool_name, args, db)


def _check_state(tool_name: str, args: BaseModel, db: Session) -> PolicyDecision:
    """Data-dependent preconditions. The only place this module touches the DB.

    Task 9 replaces this stub with the transition matrix and existence checks.
    """
    return PolicyDecision(
        allowed=True,
        requires_confirmation=tool_name in REQUIRES_CONFIRMATION,
        reason="ok",
        safe_args=MappingProxyType(args.model_dump(mode="json")),
    )
