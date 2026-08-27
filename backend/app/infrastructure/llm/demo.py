"""A keyword-driven fake LLMClient: DEMO_MODE's model, with no API key and no cost.

It reads the conversation on every call — proposing a tool for a fresh user message and,
once a tool result comes back, answering from that result. Same contract as the real
client, so every proposal still goes through the policy.
"""

import json
import unicodedata
from typing import Any

from app.application.constants import Model
from app.application.permissions import ToolName
from app.application.ports import LLMResponse
from app.domain.constants import STATUS_LABELS_ES, OrderStatus
from app.infrastructure.llm.demo_constants import (
    BALANCE_ANSWER,
    CAPABILITIES_REPLY,
    CLARIFICATIONS,
    DATE_PATTERN,
    KEYWORDS,
    LOOP_GUARD_REPLY,
    ORDER_LINE,
    ORDERS_ANSWER,
    ORDERS_EMPTY_ANSWER,
    ORDERS_SAMPLE_SIZE,
    STATUS_KEYWORDS,
    TOOL_ERROR_ANSWER,
    TOOL_USE_ID,
    UNTRUSTED_PATTERN,
    WORD_PATTERN,
    WRITE_REASON,
)

Message = dict[str, Any]


def _normalise(text: str) -> str:
    """Lowercase and accent-stripped, because the users type Spanish however they like."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _words(text: str) -> tuple[str, ...]:
    return tuple(WORD_PATTERN.findall(_normalise(text)))


def _first_number(words: tuple[str, ...]) -> int | None:
    return next((int(word) for word in words if word.isdigit()), None)


def _detect_tool(words: tuple[str, ...]) -> ToolName | None:
    for tool, keywords in KEYWORDS.items():
        if any(keyword in words for keyword in keywords):
            return tool
    return None


def _detect_status(words: tuple[str, ...]) -> OrderStatus | None:
    for status, keywords in STATUS_KEYWORDS.items():
        if any(keyword in words for keyword in keywords):
            return status
    return None


def _read_arguments(words: tuple[str, ...], text: str) -> dict[str, Any]:
    arguments: dict[str, Any] = {}
    status = _detect_status(words)
    if status is not None:
        arguments["status"] = status.value
    dates = DATE_PATTERN.findall(text)
    for key, value in zip(("date_from", "date_to"), dates, strict=False):
        arguments[key] = value
    return arguments


def _write_arguments(words: tuple[str, ...]) -> dict[str, Any] | None:
    order_id = _first_number(words)
    status = _detect_status(words)
    if order_id is None or status is None:
        return None
    return {"order_id": order_id, "new_status": status.value, "reason": WRITE_REASON}


def _arguments_for(tool: ToolName, words: tuple[str, ...], text: str) -> dict[str, Any] | None:
    if tool is ToolName.GET_SALES_ORDERS:
        return _read_arguments(words, text)
    if tool is ToolName.GET_CLIENT_BALANCE:
        client_id = _first_number(words)
        return None if client_id is None else {"client_id": client_id}
    return _write_arguments(words)


def _current_turn(messages: list[Message]) -> list[Message]:
    """Messages since the latest plain-text user message: older turns are not a loop."""
    for index in reversed(range(len(messages))):
        message = messages[index]
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            return messages[index:]
    return list(messages)


def _blocks(message: Message) -> list[dict[str, Any]]:
    content = message.get("content")
    return (
        [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []
    )


def _proposed_a_tool(turn: list[Message]) -> bool:
    return any(
        block.get("type") == "tool_use"
        for message in turn
        if message.get("role") == "assistant"
        for block in _blocks(message)
    )


def _last_tool_result(turn: list[Message]) -> str | None:
    for message in reversed(turn):
        results = [b["content"] for b in _blocks(message) if b.get("type") == "tool_result"]
        if results:
            return "".join(results)
    return None


def _unwrap(content: str) -> dict[str, Any] | None:
    """Pulls the payload out of the untrusted-data envelope; None when it is plain text."""
    match = UNTRUSTED_PATTERN.search(content)
    if match is None:
        return None
    try:
        payload = json.loads(match.group("payload"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _orders_answer(payload: dict[str, Any]) -> str:
    orders = payload.get("orders") or []
    if not orders:
        return ORDERS_EMPTY_ANSWER
    sample = ", ".join(
        ORDER_LINE.format(
            order_id=order["id"],
            status=STATUS_LABELS_ES[OrderStatus(order["status"])],
            total=order["total"],
        )
        for order in orders[:ORDERS_SAMPLE_SIZE]
    )
    return ORDERS_ANSWER.format(count=payload["count"], sample=sample)


def _answer_from_result(turn: list[Message]) -> str:
    content = _last_tool_result(turn)
    if content is None:
        return LOOP_GUARD_REPLY
    payload = _unwrap(content)
    if payload is None:
        return content
    if "orders" in payload:
        return _orders_answer(payload)
    if "balance" in payload:
        return BALANCE_ANSWER.format(**payload)
    return TOOL_ERROR_ANSWER.format(error=payload.get("error", content))


class DemoClient:
    """Implements the LLMClient protocol with keyword matching instead of a model."""

    def __init__(self, model: Model) -> None:
        self._model = model

    def create(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str | None = None,
    ) -> LLMResponse:
        turn = _current_turn(messages)
        if _proposed_a_tool(turn):
            return self._text(_answer_from_result(turn))
        return self._propose(turn[0]["content"] if turn else "")

    def _propose(self, user_message: str) -> LLMResponse:
        words = _words(user_message)
        tool = _detect_tool(words)
        if tool is None:
            return self._text(CAPABILITIES_REPLY)
        arguments = _arguments_for(tool, words, user_message)
        if arguments is None:
            return self._text(CLARIFICATIONS[tool])
        return self._tool_use(tool, arguments)

    def _text(self, text: str) -> LLMResponse:
        return self._response("end_turn", [{"type": "text", "text": text}])

    def _tool_use(self, tool: ToolName, arguments: dict[str, Any]) -> LLMResponse:
        block = {"type": "tool_use", "id": TOOL_USE_ID, "name": tool.value, "input": arguments}
        return self._response("tool_use", [block])

    def _response(self, stop_reason: str, content: list[dict[str, Any]]) -> LLMResponse:
        return LLMResponse(
            stop_reason=stop_reason,
            content=content,
            input_tokens=0,
            output_tokens=0,
            model=self._model,
        )
