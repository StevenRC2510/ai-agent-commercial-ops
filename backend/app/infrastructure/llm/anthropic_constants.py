"""Retry and model-id constants for the Anthropic client adapter."""

import re

import anthropic

RETRYABLE_ERRORS = (
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)

RETRY_BACKOFF_SECONDS = 1.0  # base delay before the single retry

DATE_SUFFIX = re.compile(r"-\d{8}$")
