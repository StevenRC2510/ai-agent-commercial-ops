"""Structured descriptions of writes, independent of the tool that requested them."""

from dataclasses import dataclass

from app.domain.constants import OrderStatus


@dataclass(frozen=True)
class OrderStatusChange:
    """What a write would change. Rendered into prose by the presentation layer."""

    order_id: int
    from_status: OrderStatus
    to_status: OrderStatus
    reason: str
