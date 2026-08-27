"""The real LLMClient: wraps the official Anthropic SDK."""

import time
from typing import Any, cast

import anthropic
from anthropic.types import MessageParam, ToolParam

from app.application.constants import Model
from app.application.ports import LLMResponse
from app.infrastructure.llm.anthropic_constants import (
    DATE_SUFFIX,
    RETRY_BACKOFF_SECONDS,
    RETRYABLE_ERRORS,
)


class UnknownModelError(RuntimeError):
    """Raised when the API echoes a model id this client cannot map to `Model`."""


def _normalize_model(wire_value: str) -> Model:
    """Anthropic may echo a resolved, dated id; bare ids are the vocabulary we own."""
    try:
        return Model(wire_value)
    except ValueError:
        pass
    try:
        return Model(DATE_SUFFIX.sub("", wire_value))
    except ValueError as exc:
        raise UnknownModelError(f"Anthropic returned an unmapped model id: {wire_value!r}") from exc


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
        except RETRYABLE_ERRORS:
            time.sleep(RETRY_BACKOFF_SECONDS)
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
            model=_normalize_model(response.model),
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )
