from datetime import date
from decimal import Decimal

from app.domain.constants import OrderStatus
from app.domain.models import AuditLog, Client, Order, Payment


def test_client_persists_credit_limit_as_exact_decimal(db):
    client = Client(name="Ana Gomez", email="ana@example.com", credit_limit=Decimal("1234.56"))
    db.add(client)
    db.flush()
    db.refresh(client)
    assert client.credit_limit == Decimal("1234.56")


def test_order_persists_status_and_total(db):
    client = Client(name="Luis Diaz", email="luis@example.com", credit_limit=Decimal("0.00"))
    db.add(client)
    db.flush()

    order = Order(
        client_id=client.id,
        status=OrderStatus.PENDING,
        total=Decimal("999.99"),
        created_at=date(2026, 1, 15),
    )
    db.add(order)
    db.flush()
    db.refresh(order)
    assert order.status == OrderStatus.PENDING
    assert order.total == Decimal("999.99")


def test_order_status_loads_as_orderstatus_instance(db):
    """Guards against the Enum column silently degrading back to a plain string."""
    client = Client(name="Rosa Paz", email="rosa@example.com", credit_limit=Decimal("0.00"))
    db.add(client)
    db.flush()

    order = Order(
        client_id=client.id,
        status=OrderStatus.DELIVERED,
        total=Decimal("10.00"),
        created_at=date(2026, 1, 1),
    )
    db.add(order)
    db.flush()
    db.expire(order)
    assert isinstance(order.status, OrderStatus)
    assert order.status.value == "delivered"
    assert order.status.name == "DELIVERED"


def test_payment_persists_amount(db):
    client = Client(name="Mara Ruiz", email="mara@example.com", credit_limit=Decimal("500.00"))
    db.add(client)
    db.flush()

    payment = Payment(client_id=client.id, amount=Decimal("250.25"), paid_at=date(2026, 1, 20))
    db.add(payment)
    db.flush()
    db.refresh(payment)
    assert payment.amount == Decimal("250.25")


def test_audit_log_stores_args_as_queryable_json(db):
    entry = AuditLog(
        trace_id="abc12345",
        actor="u-1",
        role="supervisor",
        action="update_order_status",
        args={"order_id": 3, "new_status": "delivered", "reason": "entregada hoy"},
        outcome="executed",
        reason_code="ok",
        displayed_summary=None,
    )
    db.add(entry)
    db.flush()
    db.refresh(entry)
    assert entry.args["reason"] == "entregada hoy"
    assert entry.ts is not None


def test_audit_log_displayed_summary_is_nullable(db):
    """Always NULL in this phase; populated once pending actions exist."""
    entry = AuditLog(
        trace_id="abc12345",
        actor="u-1",
        role="operator",
        action="get_sales_orders",
        args={},
        outcome="denied",
        reason_code="role_lacks_permission",
    )
    db.add(entry)
    db.flush()
    assert entry.displayed_summary is None
