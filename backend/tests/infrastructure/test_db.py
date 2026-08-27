"""The server-side ceiling on how long any single statement may run."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.config import settings
from app.infrastructure.db import engine, statement_timeout_connect_args


def _engine_with_current_settings():
    return create_engine(
        settings.test_database_url, future=True, connect_args=statement_timeout_connect_args()
    )


def test_a_query_that_outlives_the_ceiling_is_cancelled(monkeypatch):
    """Without this the LLM call is bounded by a timeout and the query behind it is not."""
    monkeypatch.setattr(settings, "db_statement_timeout_ms", 100)
    with (
        _engine_with_current_settings().connect() as connection,
        pytest.raises(DBAPIError) as caught,
    ):
        connection.execute(text("SELECT pg_sleep(1)"))
    assert "canceling statement" in str(caught.value)


def test_a_zero_ceiling_lets_a_slow_query_run_to_completion(monkeypatch):
    """Postgres' own convention for statement_timeout: 0 is no limit, not no time."""
    monkeypatch.setattr(settings, "db_statement_timeout_ms", 0)
    with _engine_with_current_settings().connect() as connection:
        assert connection.execute(text("SELECT 1 FROM pg_sleep(0.3)")).scalar_one() == 1


def test_the_application_engine_carries_a_ceiling_by_default():
    with engine.connect() as connection:
        assert connection.execute(text("SHOW statement_timeout")).scalar_one() != "0"
