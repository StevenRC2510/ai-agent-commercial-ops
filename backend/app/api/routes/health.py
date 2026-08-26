"""Liveness and readiness probes."""

from fastapi import APIRouter, Response, status

from app.api.schemas import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


def check_database() -> bool:
    """Return True when the database answers. Overridden in tests."""
    try:
        from sqlalchemy import text

        from app.infrastructure.db import engine

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        # Also covers ModuleNotFoundError before Task 5 adds app.infrastructure.db.
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
