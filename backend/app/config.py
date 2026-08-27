"""Application settings: every field has a default (none are secrets yet); field
validators enforce what plain `str` typing cannot, shared with env_check.py.
"""

from datetime import date
from decimal import Decimal
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.constants import Model

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

    # anthropic_api_key is the project's only real secret: no default beyond empty string.
    anthropic_api_key: str = ""
    llm_model: Model = Model.HAIKU_4_5
    llm_temperature: float = 0.0
    llm_timeout_seconds: int = 30
    llm_max_iterations: int = 5
    llm_max_tokens: int = 1024
    max_cost_per_session_usd: Decimal = Decimal("1.00")
    demo_mode: bool = False
    max_message_chars: int = 2000
    pending_action_ttl_seconds: int = 300
    history_max_turns: int = 6

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
