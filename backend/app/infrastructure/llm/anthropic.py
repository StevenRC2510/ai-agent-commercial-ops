"""The real LLMClient: wraps the official Anthropic SDK."""

import time
from typing import Any, cast

import anthropic
from anthropic.types import MessageParam, ToolParam

from app.application.ports import LLMResponse

_RETRYABLE = (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError)
_RETRY_BACKOFF_SECONDS = 1.0  # base delay before the single retry


class AnthropicClient:
    """The production LLMClient. `AuthenticationError`/`BadRequestError` never retry."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float,
        timeout_seconds: int,
        max_tokens: int,
    ) -> None:
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout_seconds)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def create(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str | None = None,
    ) -> LLMResponse:
        try:
            return self._call(system=system, messages=messages, tools=tools, model=model)
        except _RETRYABLE:
            time.sleep(_RETRY_BACKOFF_SECONDS)
            return self._call(system=system, messages=messages, tools=tools, model=model)

    def _call(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str | None,
    ) -> LLMResponse:
        response = self._client.messages.create(
            model=model or self._model,
            system=system,
            # The port types these as plain dicts; the shape matches the SDK's TypedDicts.
            messages=cast("list[MessageParam]", messages),
            tools=cast("list[ToolParam]", tools),
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        usage = response.usage
        return LLMResponse(
            stop_reason=response.stop_reason or "",
            content=[block.model_dump() for block in response.content],
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            model=response.model,
        )
