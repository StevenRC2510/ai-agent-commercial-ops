"""Composition root. Depends on every layer; no layer depends on it."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.config import settings
from app.infrastructure import obs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    obs.configure_logging()
    obs.log(obs.new_trace_id(), "app_start")
    yield


app = FastAPI(title="Commercial Operations Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router)
