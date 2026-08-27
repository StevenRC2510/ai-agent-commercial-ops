"""Proves the fixtures isolate. If these pass vacuously, every other test lies.

Order-dependent: each test asserts on what the previous one left behind - do not shuffle.
"""

from decimal import Decimal

from sqlalchemy import text

from app.domain.models import Client

MARKER = "fixture-isolation-probe"


def test_savepoint_fixture_accepts_a_write(db):
    db.add(Client(name=MARKER, email="p@example.com", credit_limit=Decimal("0.00")))
    db.flush()
    assert db.query(Client).filter_by(name=MARKER).count() == 1


def test_savepoint_fixture_rolled_the_previous_write_back(db):
    assert db.query(Client).filter_by(name=MARKER).count() == 0


def test_savepoint_fixture_survives_a_commit_by_the_code_under_test(db):
    """The application layer commits. That must not escape the fixture."""
    db.add(Client(name=MARKER, email="p@example.com", credit_limit=Decimal("0.00")))
    db.commit()
    assert db.query(Client).filter_by(name=MARKER).count() == 1


def test_committed_write_from_previous_test_did_not_leak(db):
    assert db.query(Client).filter_by(name=MARKER).count() == 0


def test_savepoint_fixture_survives_a_rollback_by_the_code_under_test(db):
    db.add(Client(name=MARKER, email="p@example.com", credit_limit=Decimal("0.00")))
    db.rollback()
    assert db.execute(text("SELECT 1")).scalar() == 1


def test_real_fixture_actually_commits(db_real):
    db_real.add(Client(name=MARKER, email="p@example.com", credit_limit=Decimal("0.00")))
    db_real.commit()
    assert db_real.query(Client).filter_by(name=MARKER).count() == 1


def test_real_fixture_truncated_the_previous_commit(db_real):
    assert db_real.query(Client).count() == 0
