"""Deterministic seeding. The data tables live in seed_constants."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.models import Client, Order, Payment
from app.infrastructure.seed_constants import CLIENTS, ORDERS, PAYMENTS


def anchor_date() -> date:
    """Reference date for all relative dates. Empty setting means today."""
    raw = settings.seed_anchor_date.strip()
    return date.fromisoformat(raw) if raw else date.today()


def seed_if_empty(db: Session) -> bool:
    """Populate the database when it holds no clients. True if it seeded."""
    if db.query(Client).first() is not None:
        return False

    anchor = anchor_date()

    clients = [
        Client(name=name, email=email, credit_limit=Decimal(limit))
        for name, email, limit in CLIENTS
    ]
    db.add_all(clients)
    db.flush()

    db.add_all(
        Order(
            client_id=clients[i].id,
            status=status,
            total=Decimal(total),
            created_at=anchor - timedelta(days=days),
        )
        for i, status, total, days in ORDERS
    )
    db.add_all(
        Payment(
            client_id=clients[i].id, amount=Decimal(amount), paid_at=anchor - timedelta(days=days)
        )
        for i, amount, days in PAYMENTS
    )
    db.commit()
    return True
