"""Database engine and session factory. Infrastructure only."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.domain.models import Base


def statement_timeout_connect_args() -> dict[str, str]:
    """Server-side ceiling on every statement, lock waits included. Postgres reads 0 as no limit."""
    return {"options": f"-c statement_timeout={settings.db_statement_timeout_ms}"}


engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    connect_args=statement_timeout_connect_args(),
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def create_schema() -> None:
    """Create every table if it does not already exist."""
    Base.metadata.create_all(engine)
