"""FastAPI dependencies."""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.infrastructure.db import SessionLocal


def get_db() -> Iterator[Session]:
    """Provide a session. Does not commit — use cases own their transaction."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
