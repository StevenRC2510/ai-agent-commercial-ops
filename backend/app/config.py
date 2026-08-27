"""Application settings.

Every setting has a default so the stack boots on a clean clone with no .env.
A value may have a default only if it is not a secret; this phase has none.

The field validators below are the checks the type system (plain `str`) cannot
express on its own. They run every time Settings is built, so both the running
app and app/infrastructure/env_check.py share one definition of "valid" instead
of the script keeping its own copy that could drift.
"""

from datetime import date
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ordered from least to most severe, so error messages list them the way a human would.
VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def _require_url_with_database(value: str) -> str:
    """A connection string needs both a scheme and a database name to be usable."""
    parsed = urlparse(value)
    database_name = parsed.path.lstrip("/")
    if not parsed.scheme or not database_name:
        msg = (
            "expected a connection string like "
            f"postgresql+psycopg://user:password@db:5432/dbname — got {value!r}"
        )
        raise ValueError(msg)
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://commercial_ops:commercial_ops_password@db:5432/commercial_ops"
    )
    test_database_url: str = (
        "postgresql+psycopg://commercial_ops:commercial_ops_password@db:5432/commercial_ops_test"
    )
    log_level: str = "INFO"
    seed_anchor_date: str = ""
    frontend_origin: str = "http://localhost:5173"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        return _require_url_with_database(value)

    @field_validator("test_database_url")
    @classmethod
    def validate_test_database_url(cls, value: str) -> str:
        return _require_url_with_database(value)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        if value not in VALID_LOG_LEVELS:
            levels = ", ".join(VALID_LOG_LEVELS)
            raise ValueError(f"expected one of {levels} — got {value!r}")
        return value

    @field_validator("seed_anchor_date")
    @classmethod
    def validate_seed_anchor_date(cls, value: str) -> str:
        if value:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                msg = f"expected an empty value or a date like 2026-06-15 — got {value!r}"
                raise ValueError(msg) from exc
        return value


settings = Settings()
