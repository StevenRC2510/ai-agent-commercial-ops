"""Behaviour of the real LLMClient's retry policy — SDK mocked, no network, no key.

SPEC-2 §13 acceptance criterion 8 depends on this: an invalid key must fail fast, not
retry, so the fallback shows up without doubling the latency of a failure that cannot heal.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import anthropic
import httpx
import pytest

from app.infrastructure.llm.anthropic import AnthropicClient


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _http_response(status_code: int) -> httpx.Response:
    return httpx.Response(status_code=status_code, request=_request())


def _connection_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(message="connection failed", request=_request())


def _authentication_error() -> anthropic.AuthenticationError:
    return anthropic.AuthenticationError(
        "invalid x-api-key", response=_http_response(401), body=None
    )


def _bad_request_error() -> anthropic.BadRequestError:
    return anthropic.BadRequestError("malformed request", response=_http_response(400), body=None)


class _FakeBlock:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def model_dump(self) -> dict[str, Any]:
        return self._data


def _fake_message(
    *,
    input_tokens: int = 10,
    output_tokens: int = 5,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
) -> MagicMock:
    """A minimal stand-in for `anthropic.types.Message` — only the attributes we read."""
    usage = MagicMock(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
    )
    message = MagicMock(
        stop_reason="end_turn",
        content=[_FakeBlock({"type": "text", "text": "hola"})],
        usage=usage,
        model="claude-haiku-4-5",
    )
    return message


def _client(**overrides: Any) -> AnthropicClient:
    kwargs: dict[str, Any] = {
        "api_key": "sk-test",
        "model": "claude-haiku-4-5",
        "temperature": 0.0,
        "timeout_seconds": 30,
        "max_tokens": 1024,
    }
    kwargs.update(overrides)
    return AnthropicClient(**kwargs)


@patch("app.infrastructure.llm.anthropic.time.sleep")
@patch("anthropic.Anthropic")
def test_a_connection_error_then_success_returns_the_response_and_calls_twice(
    mock_anthropic: MagicMock, mock_sleep: MagicMock
) -> None:
    mock_sdk_client = mock_anthropic.return_value
    mock_sdk_client.messages.create.side_effect = [_connection_error(), _fake_message()]

    result = _client().create(system="s", messages=[], tools=[])

    assert result.content[0]["text"] == "hola"
    assert mock_sdk_client.messages.create.call_count == 2


@patch("app.infrastructure.llm.anthropic.time.sleep")
@patch("anthropic.Anthropic")
def test_a_connection_error_on_both_calls_raises_and_calls_exactly_twice(
    mock_anthropic: MagicMock, mock_sleep: MagicMock
) -> None:
    mock_sdk_client = mock_anthropic.return_value
    mock_sdk_client.messages.create.side_effect = [_connection_error(), _connection_error()]

    with pytest.raises(anthropic.APIConnectionError):
        _client().create(system="s", messages=[], tools=[])

    assert mock_sdk_client.messages.create.call_count == 2


@patch("app.infrastructure.llm.anthropic.time.sleep")
@patch("anthropic.Anthropic")
def test_an_authentication_error_raises_immediately_and_calls_exactly_once(
    mock_anthropic: MagicMock, mock_sleep: MagicMock
) -> None:
    """The assertion that matters most: a sneaky retry would double the call count."""
    mock_sdk_client = mock_anthropic.return_value
    mock_sdk_client.messages.create.side_effect = [_authentication_error()]

    with pytest.raises(anthropic.AuthenticationError):
        _client().create(system="s", messages=[], tools=[])

    assert mock_sdk_client.messages.create.call_count == 1
    mock_sleep.assert_not_called()


@patch("app.infrastructure.llm.anthropic.time.sleep")
@patch("anthropic.Anthropic")
def test_a_bad_request_error_raises_immediately_and_calls_exactly_once(
    mock_anthropic: MagicMock, mock_sleep: MagicMock
) -> None:
    mock_sdk_client = mock_anthropic.return_value
    mock_sdk_client.messages.create.side_effect = [_bad_request_error()]

    with pytest.raises(anthropic.BadRequestError):
        _client().create(system="s", messages=[], tools=[])

    assert mock_sdk_client.messages.create.call_count == 1
    mock_sleep.assert_not_called()


@patch("anthropic.Anthropic")
def test_a_successful_call_maps_usage_onto_llm_response(mock_anthropic: MagicMock) -> None:
    mock_sdk_client = mock_anthropic.return_value
    mock_sdk_client.messages.create.side_effect = [
        _fake_message(
            input_tokens=100,
            output_tokens=42,
            cache_read_input_tokens=80,
            cache_creation_input_tokens=20,
        )
    ]

    result = _client().create(system="s", messages=[], tools=[])

    assert result.stop_reason == "end_turn"
    assert result.input_tokens == 100
    assert result.output_tokens == 42
    assert result.cache_read_input_tokens == 80
    assert result.cache_creation_input_tokens == 20
    assert result.model == "claude-haiku-4-5"


@patch("anthropic.Anthropic")
def test_temperature_and_max_tokens_from_settings_reach_the_sdk_call(
    mock_anthropic: MagicMock,
) -> None:
    mock_sdk_client = mock_anthropic.return_value
    mock_sdk_client.messages.create.side_effect = [_fake_message()]

    _client(temperature=0.7, max_tokens=777).create(system="s", messages=[], tools=[])

    _, kwargs = mock_sdk_client.messages.create.call_args
    assert kwargs["temperature"] == 0.7
    assert kwargs["max_tokens"] == 777
