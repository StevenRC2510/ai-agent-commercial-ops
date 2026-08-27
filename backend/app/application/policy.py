"""POLICY — decides what is allowed. Never renders text, never calls a model.

Import whitelist enforced by tests/architecture/test_imports.py.
"""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.permissions import REQUIRES_CONFIRMATION, ROLE_PERMISSIONS
from app.application.tool_args import TOOL_SCHEMAS, UpdateOrderStatusArgs
from app.domain.actions import OrderStatusChange
from app.domain.constants import ALLOWED_TRANSITIONS
from app.domain.models import Order


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

    Defence in depth: evaluate() re-validates every call, so hiding a tool here fails open.
    """
    return ROLE_PERMISSIONS.get(role, frozenset())


def evaluate(tool_name: str, raw_args: dict, role: str, db: Session) -> PolicyDecision:
    """Decide whether this call may run. The order of checks is significant.

    `db` must be a usable session, or `_check_state` raises rather than authorising anything.
    """
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
    """Data-dependent preconditions. The only place this module touches the DB."""
    safe_args = MappingProxyType(args.model_dump(mode="json"))
    requires_confirmation = tool_name in REQUIRES_CONFIRMATION

    if not requires_confirmation:
        return PolicyDecision(
            allowed=True,
            requires_confirmation=False,
            reason="ok",
            safe_args=safe_args,
        )

    if not isinstance(args, UpdateOrderStatusArgs):
        raise TypeError(f"{tool_name} requires UpdateOrderStatusArgs, got {type(args).__name__}")

    current_status = db.execute(
        select(Order.status).where(Order.id == args.order_id)
    ).scalar_one_or_none()
    if current_status is None:
        return _deny(DenialReason.ORDER_NOT_FOUND)

    if args.new_status not in ALLOWED_TRANSITIONS[current_status]:
        return _deny(DenialReason.INVALID_STATUS_TRANSITION)

    return PolicyDecision(
        allowed=True,
        requires_confirmation=requires_confirmation,
        reason="ok",
        safe_args=safe_args,
        change=OrderStatusChange(
            order_id=args.order_id,
            from_status=current_status,
            to_status=args.new_status,
            reason=args.reason,
        ),
    )
