"""Names and reserved fields used by the structured logging setup."""

LOGGER_NAME = "app"

RESERVED_LOG_RECORD_FIELDS = frozenset(
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
