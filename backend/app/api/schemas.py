"""HTTP request and response contracts.

Separate from application/policy.py schemas: this is the public API, those validate model calls.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    demo_mode: bool


class ReadyResponse(BaseModel):
    status: str
    database: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # No max length here: an over-long message earns the orchestrator's message, not a 422.
    message: str = Field(min_length=1)
    session_id: str = Field(min_length=1, max_length=100)


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending_id: str = Field(min_length=1, max_length=100)
    approved: bool


class Telemetry(BaseModel):
    latency_ms: int
    input_tokens: int
    output_tokens: int
    iterations: int


class TurnResponse(BaseModel):
    """One answer from the agent, whatever the endpoint that produced it (SPEC-2 §8)."""

    type: Literal["message", "confirmation_required", "error"]
    text: str
    trace_id: str
    pending_id: str | None = None
    pending_summary: str | None = None
    telemetry: Telemetry | None = None
    # Machine-readable denial code, so a client never has to match on Spanish prose.
    reason_code: str | None = None
