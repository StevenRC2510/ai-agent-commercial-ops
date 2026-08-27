"""Database engine and session factory. Infrastructure only."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.domain.models import Base

engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def create_schema() -> None:
    """Create every table if it does not already exist."""
    Base.metadata.create_all(engine)
