"""Test fixtures.

Two database fixtures exist on purpose:

  db       savepoint-isolated; fast; used by almost every test
  db_real  a real top-level transaction; used only by tests that assert on
           transactional behaviour, which cannot be observed from inside
           another transaction

Never request both fixtures in the same test: db_real's TRUNCATE needs an ACCESS
EXCLUSIVE lock and would block against db's still-open transaction on the same tables.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.context import AuditContext
from app.domain.models import Base

_TABLES = ", ".join(t.name for t in Base.metadata.sorted_tables)

# db_real truncates tables; if test and app URLs ever match, this would destroy app data.
if settings.test_database_url == settings.database_url:
    raise RuntimeError(
        "Refusing to run: the test database is the application database. "
        "db_real truncates tables and would destroy application data."
    )


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(settings.test_database_url, future=True, pool_pre_ping=True)
    Base.metadata.create_all(eng)
    with eng.begin() as conn:
        conn.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))
    return eng


@pytest.fixture
def db(engine):
    """Session bound to an outer transaction that is always rolled back.

    join_transaction_mode="create_savepoint" means the code under test may
    call commit() and rollback() freely: those act on a SAVEPOINT, never on
    the fixture's own transaction.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def db_real(engine):
    """Session with a real top-level transaction. Cleaned up by TRUNCATE."""
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))


@pytest.fixture
def audit_ctx() -> AuditContext:
    return AuditContext(actor="u-test", role="supervisor", trace_id="abc12345")
