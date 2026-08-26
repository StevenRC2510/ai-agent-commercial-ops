"""Structured logging: one JSON object per line on stdout."""

import json
import logging
import logging.config
import secrets
from datetime import UTC, datetime
from typing import Any

from app.config import settings

_LOGGER_NAME = "app"
_RESERVED = frozenset(
    {
        "args",
        "asctime",
        "color_message",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Render every record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            payload: dict[str, Any] = {
                "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "level": record.levelname,
                "event": getattr(record, "event", record.getMessage()),
            }
            trace_id = getattr(record, "trace_id", None)
            if trace_id is not None:
                payload["trace_id"] = trace_id
            for key, value in record.__dict__.items():
                if key not in _RESERVED and key not in payload:
                    payload[key] = value
            return json.dumps(payload, ensure_ascii=False, default=str)
        except Exception as exc:
            # A traceback on stdout would break the one-JSON-per-line invariant.
            original_event = getattr(record, "event", None)
            fallback = {
                "ts": datetime.now(UTC).isoformat(),
                "level": "ERROR",
                "event": "log_format_failed",
                "error": str(exc),
                "original_event": str(original_event) if original_event else "unknown",
            }
            return json.dumps(fallback)


LOGGING_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": JsonFormatter}},
    "handlers": {
        "json": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            # Resolved at configure time, not import time, so tests can swap the stream.
            "stream": "ext://sys.stdout",
        }
    },
    "loggers": {
        _LOGGER_NAME: {"handlers": ["json"], "level": "INFO", "propagate": False},
        "uvicorn": {"handlers": ["json"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["json"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["json"], "level": "INFO", "propagate": False},
    },
    "root": {"handlers": ["json"], "level": "WARNING"},
}


def configure_logging() -> None:
    """Install the JSON handler for the app and for Uvicorn's own loggers."""
    config = {**LOGGING_CONFIG}
    config["loggers"] = {
        name: {**cfg, "level": settings.log_level}
        for name, cfg in LOGGING_CONFIG["loggers"].items()
    }
    logging.config.dictConfig(config)


def new_trace_id() -> str:
    """Eight hex characters - enough to correlate one request."""
    return secrets.token_hex(4)


def log(
    trace_id: str,
    event: str,
    level: int = logging.INFO,
    **fields: Any,  # noqa: ANN401 - log payloads are arbitrary by design
) -> None:
    """Emit one structured event.

    This function performs no redaction: callers alone are responsible for never
    passing a secret or raw user-facing text as a field value (e.g. log a length
    and a short hash instead of the raw string).

    Raises:
        ValueError: if a field name collides with a reserved ``LogRecord``
            attribute (e.g. ``name``, ``module``). Checked unconditionally, before
            the record is built, so the error is raised the same way regardless of
            the configured log level - never only once someone lowers it to DEBUG.
    """
    for key in fields:
        if key in _RESERVED:
            raise ValueError(
                f"Field name {key!r} collides with a reserved LogRecord attribute; rename it."
            )
    logging.getLogger(_LOGGER_NAME).log(
        level, event, extra={"event": event, "trace_id": trace_id, **fields}
    )
