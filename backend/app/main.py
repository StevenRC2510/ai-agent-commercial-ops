"""Composition root. Depends on every layer; no layer depends on it."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import RateLimitExceededError
from app.api.middleware import TRACE_HEADER, TraceIdMiddleware
from app.api.routes import chat, confirm, health
from app.api.schemas import TurnResponse
from app.application import presentation
from app.application.messages import FALLBACK_INTERNAL_ERROR
from app.application.permissions import DenialReason
from app.config import settings
from app.infrastructure import obs
from app.infrastructure.db import SessionLocal, create_schema
from app.infrastructure.seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    obs.configure_logging()
    create_schema()
    with SessionLocal() as session:
        seeded = seed_if_empty(session)
    obs.log(obs.new_trace_id(), "seed_completed", seeded=seeded)
    obs.log(obs.new_trace_id(), "app_start")
    yield


app = FastAPI(title="Commercial Operations Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    # Without this the browser can read the response but never the trace id on it.
    expose_headers=[TRACE_HEADER],
)
app.add_middleware(TraceIdMiddleware)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Log against the trace id and answer generically: no stacktrace ever reaches a client."""
    trace_id = getattr(request.state, "trace_id", "")
    obs.log(
        trace_id,
        "unhandled_exception",
        level=logging.ERROR,
        failure=type(exc).__name__,
        error=str(exc),
    )
    body = TurnResponse(type="error", text=FALLBACK_INTERNAL_ERROR, trace_id=trace_id)
    return JSONResponse(
        status_code=500, content=body.model_dump(), headers={TRACE_HEADER: trace_id}
    )


@app.exception_handler(RateLimitExceededError)
async def handle_rate_limited(request: Request, exc: RateLimitExceededError) -> JSONResponse:
    """Answer the standard error envelope; who was throttled is logged, never published."""
    trace_id = getattr(request.state, "trace_id", "")
    obs.log(trace_id, "rate_limited", level=logging.WARNING, actor=str(exc))
    reason = DenialReason.RATE_LIMITED.value
    body = TurnResponse(
        type="error", text=presentation.render_denial(reason), trace_id=trace_id, reason_code=reason
    )
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=body.model_dump(),
        headers={TRACE_HEADER: trace_id},
    )


app.include_router(health.router)
app.include_router(chat.router)
app.include_router(confirm.router)
