"""POLICY — decides what is allowed. Never renders text, never calls a model.

Import whitelist enforced by tests/architecture/test_imports.py.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.permissions import (
    REQUIRES_CONFIRMATION,
    ROLE_PERMISSIONS,
    DenialReason,
    Role,
    ToolName,
)
from app.application.tool_args import TOOL_SCHEMAS, UpdateOrderStatusArgs
from app.domain.actions import OrderStatusChange
from app.domain.constants import ALLOWED_TRANSITIONS
from app.domain.models import Order


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    requires_confirmation: bool
    reason: str  # "ok", or a DenialReason value — plain str on the wire, not the enum itself
    safe_args: MappingProxyType[str, Any] | None = None
    change: OrderStatusChange | None = None


def _deny(reason: DenialReason) -> PolicyDecision:
    return PolicyDecision(allowed=False, requires_confirmation=False, reason=reason.value)


def visible_tools_for(role: str) -> frozenset[ToolName]:
    """Tools that will be declared to the model for this role.

    Defence in depth: evaluate() re-validates every call, so hiding a tool here fails open.
    """
    try:
        role_enum = Role(role)
    except ValueError:
        return frozenset()
    return ROLE_PERMISSIONS.get(role_enum, frozenset())


def evaluate(tool_name: str, raw_args: dict, role: str, db: Session) -> PolicyDecision:
    """Decide whether this call may run. The order of checks is significant.

    `tool_name` and `role` are plain strings off the wire, converted to enums here.
    """
    try:
        tool = ToolName(tool_name)
    except ValueError:
        return _deny(DenialReason.UNKNOWN_TOOL)

    try:
        role_enum: Role | None = Role(role)
    except ValueError:
        role_enum = None
    # Unknown, empty, or None roles all deny identically: reason codes must never leak valid names.
    if role_enum is None or tool not in ROLE_PERMISSIONS.get(role_enum, frozenset()):
        return _deny(DenialReason.ROLE_LACKS_PERMISSION)

    schema = TOOL_SCHEMAS[tool]
    try:
        args = schema(**raw_args)
    except (ValidationError, TypeError):
        return _deny(DenialReason.INVALID_ARGUMENTS)

    return _check_state(tool, args, db)


def _check_state(tool_name: ToolName, args: BaseModel, db: Session) -> PolicyDecision:
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
        raise TypeError(
            f"{tool_name.value} requires UpdateOrderStatusArgs, got {type(args).__name__}"
        )

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
