"""Cross-cutting HTTP concerns: one trace id per request, echoed back to the caller."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.infrastructure import obs

# Header name the HTTP surface writes. Shared with the CORS setup in app/main.py.
TRACE_HEADER = "X-Trace-Id"


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Stamps the request so every log line and every response share one identifier."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = obs.new_trace_id()
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers[TRACE_HEADER] = trace_id
        return response
