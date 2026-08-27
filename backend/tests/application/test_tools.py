"""Read/write tool execution. Deterministic ordering, exact money, and atomicity."""

from datetime import date
from decimal import Decimal

import pytest

from app.application import tools
from app.domain.constants import MAX_ORDER_LIMIT, OrderStatus
from app.domain.context import AuditContext
from app.domain.errors import ClientNotFoundError, InvalidTransitionError, OrderNotFoundError
from app.domain.models import AuditLog, Client, Order, Payment

CTX = AuditContext(actor="u-test", role="supervisor", trace_id="abc12345")


@pytest.fixture
def sample(db):
    client = Client(name="Carlos Mendoza", email="c@example.com", credit_limit=Decimal("5000.00"))
    other = Client(name="Lucia Ferrer", email="l@example.com", credit_limit=Decimal("1000.00"))
    db.add_all([client, other])
    db.flush()

    db.add_all(
        [
            Order(
                client_id=client.id,
                status=OrderStatus.PENDING,
                total=Decimal("100.00"),
                created_at=date(2026, 6, 1),
            ),
            Order(
                client_id=client.id,
                status=OrderStatus.PENDING,
                total=Decimal("200.00"),
                created_at=date(2026, 6, 10),
            ),
            Order(
                client_id=client.id,
                status=OrderStatus.DELIVERED,
                total=Decimal("300.00"),
                created_at=date(2026, 6, 5),
            ),
            Order(
                client_id=client.id,
                status=OrderStatus.CANCELLED,
                total=Decimal("999.00"),
                created_at=date(2026, 6, 7),
            ),
            Order(
                client_id=other.id,
                status=OrderStatus.PENDING,
                total=Decimal("50.00"),
                created_at=date(2026, 6, 3),
            ),
        ]
    )
    db.add(Payment(client_id=client.id, amount=Decimal("250.00"), paid_at=date(2026, 6, 8)))
    db.flush()
    return {"client_id": client.id, "other_id": other.id}


def test_status_filter_returns_only_matching_orders(db, sample):
    result = tools.get_sales_orders(db, status=OrderStatus.PENDING)
    assert result["count"] == 3
    assert all(o["status"] == "pending" for o in result["orders"])


def test_date_range_includes_both_endpoints(db, sample):
    result = tools.get_sales_orders(db, date_from=date(2026, 6, 1), date_to=date(2026, 6, 5))
    dates = {o["created_at"] for o in result["orders"]}
    assert "2026-06-01" in dates
    assert "2026-06-05" in dates
    assert "2026-06-10" not in dates


def test_client_filter_excludes_other_clients(db, sample):
    assert tools.get_sales_orders(db, client_id=sample["client_id"])["count"] == 4


def test_results_are_ordered_newest_first(db, sample):
    result = tools.get_sales_orders(db, client_id=sample["client_id"])
    dates = [o["created_at"] for o in result["orders"]]
    assert dates == sorted(dates, reverse=True)


def test_results_are_ordered_by_id_desc_within_the_same_date(db, sample):
    """Same created_at must still sort deterministically, by id descending."""
    client_id = sample["client_id"]
    same_day = date(2026, 7, 1)
    first = Order(
        client_id=client_id, status=OrderStatus.PENDING, total=Decimal("1.00"), created_at=same_day
    )
    second = Order(
        client_id=client_id, status=OrderStatus.PENDING, total=Decimal("2.00"), created_at=same_day
    )
    db.add_all([first, second])
    db.flush()

    result = tools.get_sales_orders(db, client_id=client_id, date_from=same_day, date_to=same_day)
    ids = [o["id"] for o in result["orders"]]
    assert ids == sorted(ids, reverse=True)


def test_limit_runs_verbatim_because_the_clamp_lives_only_in_the_schema(db, sample):
    """A second clamp here would let an audited limit differ from the executed one.

    Seeds one row more than it asks for, so the count also proves the limit is applied.
    """
    requested = MAX_ORDER_LIMIT + 5
    client_id = sample["other_id"]
    db.add_all(
        [
            Order(
                client_id=client_id,
                status=OrderStatus.PENDING,
                total=Decimal("1.00"),
                created_at=date(2026, 7, 2),
            )
            for _ in range(requested)
        ]
    )
    db.flush()

    result = tools.get_sales_orders(db, client_id=client_id, limit=requested)
    assert result["count"] == requested
    assert result["count"] > MAX_ORDER_LIMIT


def test_balance_excludes_cancelled_orders(db, sample):
    result = tools.get_client_balance(db, sample["client_id"])
    # 100 + 200 + 300 = 600 ordered; the 999 cancelled order is excluded.
    assert result["total_ordered"] == "600.00"
    assert result["total_paid"] == "250.00"
    assert result["balance"] == "350.00"


def test_overpaid_client_yields_a_negative_balance_without_raising(db, sample):
    db.add(
        Payment(client_id=sample["client_id"], amount=Decimal("1000.00"), paid_at=date(2026, 6, 9))
    )
    db.flush()
    assert Decimal(tools.get_client_balance(db, sample["client_id"])["balance"]) < 0


def test_exceeds_credit_limit_is_strict_greater_than(db, sample):
    assert tools.get_client_balance(db, sample["client_id"])["exceeds_credit_limit"] is False

    db.add(
        Order(
            client_id=sample["client_id"],
            status=OrderStatus.PENDING,
            total=Decimal("10000.00"),
            created_at=date(2026, 6, 12),
        )
    )
    db.flush()
    assert tools.get_client_balance(db, sample["client_id"])["exceeds_credit_limit"]


def test_client_with_no_activity_has_a_zero_balance(db, sample):
    assert tools.get_client_balance(db, sample["other_id"])["total_paid"] == "0.00"


def test_unknown_client_raises_a_domain_error(db, sample):
    with pytest.raises(ClientNotFoundError):
        tools.get_client_balance(db, 999999)


def test_update_changes_the_status_and_writes_exactly_one_audit_row(db, sample):
    order = db.query(Order).filter_by(status=OrderStatus.PENDING).first()
    result = tools.update_order_status(
        db, order.id, OrderStatus.IN_PROGRESS, "el taller ya lo recibio", ctx=CTX
    )
    assert result["previous_status"] == "pending"
    assert result["new_status"] == "in_progress"

    db.refresh(order)
    assert order.status == OrderStatus.IN_PROGRESS
    assert order.updated_at is not None

    rows = db.query(AuditLog).filter_by(outcome="executed").all()
    assert len(rows) == 1
    assert rows[0].action == "update_order_status"
    assert rows[0].trace_id == "abc12345"
    assert rows[0].args["reason"] == "el taller ya lo recibio"
    assert rows[0].reason_code == "ok"
    assert rows[0].id == result["audit_id"]


def test_update_persists_the_displayed_summary_when_given(db, sample):
    order = db.query(Order).filter_by(status=OrderStatus.PENDING).first()
    summary = 'Cambiar la orden #1 de "pendiente" a "en proceso". Motivo: prueba'
    tools.update_order_status(
        db, order.id, OrderStatus.IN_PROGRESS, "prueba", ctx=CTX, displayed_summary=summary
    )
    assert db.query(AuditLog).one().displayed_summary == summary


def test_update_on_a_missing_order_raises_and_writes_nothing(db, sample):
    with pytest.raises(OrderNotFoundError):
        tools.update_order_status(db, 999999, OrderStatus.DELIVERED, "motivo valido", ctx=CTX)
    assert db.query(AuditLog).filter_by(outcome="executed").count() == 0


def test_invalid_transition_changes_nothing(db, sample):
    order = db.query(Order).filter_by(status=OrderStatus.DELIVERED).first()
    with pytest.raises(InvalidTransitionError):
        tools.update_order_status(db, order.id, OrderStatus.PENDING, "motivo valido", ctx=CTX)
    db.refresh(order)
    assert order.status == OrderStatus.DELIVERED
    assert db.query(AuditLog).filter_by(outcome="executed").count() == 0


def test_record_audit_accepts_a_denial_with_no_summary(db):
    audit_id = tools.record_audit(
        db,
        ctx=CTX,
        action="update_order_status",
        args={"order_id": 1},
        outcome="denied",
        reason_code="role_lacks_permission",
    )
    row = db.get(AuditLog, audit_id)
    assert row.outcome == "denied"
    assert row.displayed_summary is None


def test_update_order_status_locks_the_row_for_update(db, sample):
    """A single process cannot prove mutual exclusion; this asserts the lock is requested,
    not that it prevents a concurrent write."""
    order = db.query(Order).filter_by(status=OrderStatus.PENDING).first()
    query = tools._locked_order_query(order.id)
    sql = str(query.compile(compile_kwargs={"literal_binds": True}))
    assert "FOR UPDATE" in sql


def test_write_and_audit_roll_back_together_on_failure(db_real, monkeypatch):
    """Uses db_real: transactional behaviour cannot be observed from inside another
    transaction. With the savepoint fixture this test would exercise a different
    mechanism than production does."""
    client = Client(name="Atomicity Probe", email="a@example.com", credit_limit=Decimal("0.00"))
    db_real.add(client)
    db_real.flush()
    order = Order(
        client_id=client.id,
        status=OrderStatus.PENDING,
        total=Decimal("100.00"),
        created_at=date(2026, 6, 1),
    )
    db_real.add(order)
    db_real.commit()
    order_id = order.id

    def explode(*args, **kwargs):
        raise RuntimeError("audit write failed")

    monkeypatch.setattr(tools, "record_audit", explode)

    with pytest.raises(RuntimeError):
        tools.update_order_status(
            db_real, order_id, OrderStatus.IN_PROGRESS, "motivo valido", ctx=CTX
        )

    db_real.expire_all()
    assert db_real.get(Order, order_id).status == OrderStatus.PENDING
    assert db_real.query(AuditLog).count() == 0


def test_write_and_audit_commit_together_on_success(db_real):
    """Companion to the failure case: on success, exactly one audit row lands, on db_real."""
    client = Client(name="Commit Probe", email="b@example.com", credit_limit=Decimal("0.00"))
    db_real.add(client)
    db_real.flush()
    order = Order(
        client_id=client.id,
        status=OrderStatus.PENDING,
        total=Decimal("100.00"),
        created_at=date(2026, 6, 1),
    )
    db_real.add(order)
    db_real.commit()
    order_id = order.id

    tools.update_order_status(db_real, order_id, OrderStatus.IN_PROGRESS, "motivo valido", ctx=CTX)

    db_real.expire_all()
    assert db_real.get(Order, order_id).status == OrderStatus.IN_PROGRESS
    assert db_real.query(AuditLog).count() == 1
