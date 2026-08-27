"""Test fixtures: `db` is savepoint-isolated and fast, for almost every test;
`db_real` uses a real transaction, for tests that must observe transactional
behaviour a savepoint would hide. Never request both in the same test.
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

    `create_savepoint` mode makes commit()/rollback() act on a SAVEPOINT, not the outer one.
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
