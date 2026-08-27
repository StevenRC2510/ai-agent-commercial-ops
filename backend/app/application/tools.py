"""EXECUTION — data access and the one write path. Knows nothing about permissions.

Arguments arrive already validated by the policy layer. Every query goes through the
ORM; no SQL is ever built by string concatenation.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.domain.constants import (
    ALLOWED_TRANSITIONS,
    DEFAULT_ORDER_LIMIT,
    MAX_ORDER_LIMIT,
    OrderStatus,
)
from app.domain.context import AuditContext
from app.domain.errors import ClientNotFoundError, InvalidTransitionError, OrderNotFoundError
from app.domain.models import AuditLog, Client, Order, Payment

_ZERO = Decimal("0.00")


def _money(value: Decimal | None) -> str:
    return str((value or _ZERO).quantize(_ZERO))


def get_sales_orders(
    db: Session,
    *,
    status: OrderStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    client_id: int | None = None,
    limit: int = DEFAULT_ORDER_LIMIT,
) -> dict[str, Any]:
    """Query orders with optional filters.

    Filters on created_at; both date bounds are inclusive. Results are ordered
    newest first, then by id descending, so repeated calls are reproducible.
    """
    query = select(Order)
    if status is not None:
        query = query.where(Order.status == OrderStatus(status).value)
    if date_from is not None:
        query = query.where(Order.created_at >= date_from)
    if date_to is not None:
        query = query.where(Order.created_at <= date_to)
    if client_id is not None:
        query = query.where(Order.client_id == client_id)

    query = query.order_by(Order.created_at.desc(), Order.id.desc())
    query = query.limit(min(limit, MAX_ORDER_LIMIT))

    orders = db.execute(query).scalars().all()
    return {
        "count": len(orders),
        "orders": [
            {
                "id": o.id,
                "client_id": o.client_id,
                "status": o.status,
                "total": _money(o.total),
                "created_at": o.created_at.isoformat(),
                "notes": o.notes,
            }
            for o in orders
        ],
    }


def get_client_balance(db: Session, client_id: int) -> dict[str, Any]:
    """Return the client's ordered/paid totals. Cancelled orders do not count."""
    client = db.get(Client, client_id)
    if client is None:
        raise ClientNotFoundError(f"client {client_id} does not exist")

    total_ordered = db.execute(
        select(func.coalesce(func.sum(Order.total), _ZERO)).where(
            Order.client_id == client_id,
            Order.status != OrderStatus.CANCELLED.value,
        )
    ).scalar_one()

    total_paid = db.execute(
        select(func.coalesce(func.sum(Payment.amount), _ZERO)).where(Payment.client_id == client_id)
    ).scalar_one()

    balance = total_ordered - total_paid
    return {
        "client_id": client.id,
        "name": client.name,
        "total_ordered": _money(total_ordered),
        "total_paid": _money(total_paid),
        "balance": _money(balance),
        "credit_limit": _money(client.credit_limit),
        "exceeds_credit_limit": balance > client.credit_limit,
    }


def record_audit(
    db: Session,
    *,
    ctx: AuditContext,
    action: str,
    args: dict[str, Any],
    outcome: str,
    reason_code: str,
    displayed_summary: str | None = None,
) -> int:
    """Append one audit row. Does not commit; the caller owns the transaction."""
    entry = AuditLog(
        trace_id=ctx.trace_id,
        actor=ctx.actor,
        role=ctx.role,
        action=action,
        args=args,
        outcome=outcome,
        reason_code=reason_code,
        displayed_summary=displayed_summary,
    )
    db.add(entry)
    db.flush()
    return entry.id


def _locked_order_query(order_id: int) -> Select[tuple[Order]]:
    """FOR UPDATE so a concurrent confirmation on the same order blocks, not overwrites."""
    return select(Order).where(Order.id == order_id).with_for_update()


def update_order_status(
    db: Session,
    order_id: int,
    new_status: OrderStatus,
    reason: str,
    *,
    ctx: AuditContext,
    displayed_summary: str | None = None,
) -> dict[str, Any]:
    """Apply the status change and its audit row in one transaction.

    This is the transaction boundary: both writes commit together or not at all.
    Validation failures raise before any write is staged, so there is nothing to roll back.
    """
    order = db.execute(_locked_order_query(order_id)).scalar_one_or_none()
    if order is None:
        raise OrderNotFoundError(f"order {order_id} does not exist")

    previous = OrderStatus(order.status)
    target = OrderStatus(new_status)
    if target not in ALLOWED_TRANSITIONS[previous]:
        raise InvalidTransitionError(f"{previous.value} -> {target.value}")

    try:
        order.status = target
        order.updated_at = datetime.now(UTC)

        audit_id = record_audit(
            db,
            ctx=ctx,
            action="update_order_status",
            args={"order_id": order_id, "new_status": target.value, "reason": reason},
            outcome="executed",
            reason_code="ok",
            displayed_summary=displayed_summary,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "order_id": order_id,
        "previous_status": previous.value,
        "new_status": target.value,
        "audit_id": audit_id,
    }
