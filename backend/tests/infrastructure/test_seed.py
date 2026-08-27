from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.domain.constants import OrderStatus
from app.domain.models import Base, Client, Order, Payment
from app.infrastructure import seed

ANCHOR = date(2026, 6, 15)
_TABLES = ", ".join(t.name for t in Base.metadata.sorted_tables)


def _seed(session, monkeypatch):
    monkeypatch.setattr(seed, "anchor_date", lambda: ANCHOR)
    return seed.seed_if_empty(session)


def test_seed_creates_the_expected_row_counts(db, monkeypatch):
    _seed(db, monkeypatch)
    assert db.query(Client).count() == 8
    assert db.query(Order).count() == 30
    assert db.query(Payment).count() == 15


def test_seed_is_idempotent(db, monkeypatch):
    assert _seed(db, monkeypatch) is True
    assert _seed(db, monkeypatch) is False
    assert db.query(Client).count() == 8


def test_seed_places_at_least_three_orders_on_the_anchor_date(db, monkeypatch):
    _seed(db, monkeypatch)
    assert db.query(Order).filter(Order.created_at == ANCHOR).count() >= 3


def test_seed_keeps_every_order_within_the_last_45_days(db, monkeypatch):
    _seed(db, monkeypatch)
    oldest = ANCHOR - timedelta(days=45)
    for order in db.query(Order).all():
        assert oldest <= order.created_at <= ANCHOR


def test_seed_covers_every_status(db, monkeypatch):
    _seed(db, monkeypatch)
    assert {o.status for o in db.query(Order).all()} == {s.value for s in OrderStatus}


def test_seed_stores_the_adversarial_client_name_verbatim(db, monkeypatch):
    """Injection payload is ordinary data. It must not be sanitised or escaped."""
    _seed(db, monkeypatch)
    assert seed.ADVERSARIAL_CLIENT_NAME in {c.name for c in db.query(Client).all()}


def test_seed_creates_the_balance_situations_the_spec_requires(db, monkeypatch) -> None:
    """SPEC-1 §9: exactly one client at zero, at least one overpaid, several positive."""
    _seed(db, monkeypatch)

    order_totals: dict[int, Decimal] = {}
    for order in db.query(Order).filter(Order.status != OrderStatus.CANCELLED).all():
        order_totals[order.client_id] = (
            order_totals.get(order.client_id, Decimal("0.00")) + order.total
        )

    payment_totals: dict[int, Decimal] = {}
    for payment in db.query(Payment).all():
        payment_totals[payment.client_id] = (
            payment_totals.get(payment.client_id, Decimal("0.00")) + payment.amount
        )

    balances = [
        order_totals.get(client.id, Decimal("0.00"))
        - payment_totals.get(client.id, Decimal("0.00"))
        for client in db.query(Client).all()
    ]

    assert sum(1 for b in balances if b == Decimal("0.00")) == 1
    assert sum(1 for b in balances if b < Decimal("0.00")) >= 1
    assert sum(1 for b in balances if b > Decimal("0.00")) >= 3


def _dump(session):
    """Business data keyed by client name, not client_id: identity sequences
    are not transactional, so comparing surrogate keys would test Postgres
    rather than our seed."""
    orders = sorted(
        (name, o.status, str(o.total), o.created_at)
        for o, name in session.query(Order, Client.name).join(Client, Order.client_id == Client.id)
    )
    payments = sorted(
        (name, str(p.amount), p.paid_at)
        for p, name in session.query(Payment, Client.name).join(
            Client, Payment.client_id == Client.id
        )
    )
    return orders, payments


def test_seed_produces_identical_data_on_a_fresh_database(db_real, monkeypatch) -> None:
    """Same anchor, same data: two independent seeds must be byte-identical."""
    monkeypatch.setattr(seed, "anchor_date", lambda: ANCHOR)

    seed.seed_if_empty(db_real)
    first = _dump(db_real)

    db_real.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))
    db_real.commit()

    seed.seed_if_empty(db_real)
    assert _dump(db_real) == first


def test_anchor_date_falls_back_to_today_when_unset(monkeypatch):
    monkeypatch.setattr(seed.settings, "seed_anchor_date", "")
    assert seed.anchor_date() == date.today()


def test_anchor_date_parses_the_configured_value(monkeypatch):
    monkeypatch.setattr(seed.settings, "seed_anchor_date", "2026-06-15")
    assert seed.anchor_date() == ANCHOR
