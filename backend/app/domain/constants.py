"""Shared business vocabulary. Everything imports these; nothing duplicates them."""

from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


VALID_STATUSES: tuple[str, ...] = tuple(s.value for s in OrderStatus)

ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING: frozenset({OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED}),
    OrderStatus.IN_PROGRESS: frozenset({OrderStatus.DELIVERED, OrderStatus.CANCELLED}),
    OrderStatus.DELIVERED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}

ROLES: tuple[str, ...] = ("operator", "supervisor")

# Persisted values are English domain data; the end user reads Spanish.
STATUS_LABELS_ES: dict[OrderStatus, str] = {
    OrderStatus.PENDING: "pendiente",
    OrderStatus.IN_PROGRESS: "en proceso",
    OrderStatus.DELIVERED: "entregada",
    OrderStatus.CANCELLED: "cancelada",
}

DEFAULT_ORDER_LIMIT: int = 50
MAX_ORDER_LIMIT: int = 200
