"""HTTP request and response contracts.

Separate from application/policy.py schemas: this is the public API, those validate model calls.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    database: str
