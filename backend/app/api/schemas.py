"""HTTP request and response contracts.

Deliberately separate from the argument schemas in application/policy.py:
this is the public API surface, those validate what a model proposes.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    database: str
