"""Liveness and readiness probes."""

from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.schemas import HealthResponse, ReadyResponse
from app.infrastructure.db import engine

router = APIRouter(tags=["health"])


def check_database() -> bool:
    """Return True when the database answers. Overridden in tests."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness. Touches nothing, so a database blip cannot restart us."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
def ready(response: Response) -> ReadyResponse:
    """Readiness. Verifies the database answers."""
    reachable = check_database()
    if not reachable:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(
        status="ok" if reachable else "degraded",
        database="up" if reachable else "down",
    )
