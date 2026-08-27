"""A keyword-driven fake LLMClient: DEMO_MODE's model, with no API key and no cost.

It reads the conversation on every call: proposing a tool for a fresh user message, answering
from a tool result once one comes back, and finishing the intent it asked a clarification
about. Same contract as the real client, so every proposal still goes through the policy.
"""

import json
import unicodedata
from typing import Any
from uuid import uuid4

from app.application.constants import Model
from app.application.permissions import ToolName
from app.application.ports import LLMResponse
from app.domain.constants import ALLOWED_TRANSITIONS, STATUS_LABELS_ES, OrderStatus
from app.infrastructure.llm.demo_constants import (
    BALANCE_ANSWER,
    CANDIDATES_ANSWER,
    CANDIDATES_EMPTY_ANSWER,
    CANDIDATES_QUESTION,
    CANDIDATES_SAMPLE_SIZE,
    CAPABILITIES_REPLY,
    CLARIFICATION_OPENERS,
    CLARIFICATIONS,
    DATE_PATTERN,
    LOOP_GUARD_REPLY,
    MISSING_SLOT_ASKS,
    ORDER_LINE,
    ORDERS_ANSWER,
    ORDERS_EMPTY_ANSWER,
    ORDERS_SAMPLE_SIZE,
    SLOT_ANSWER_FILLERS,
    STATUS_STEMS,
    STEM_EXCLUSIONS,
    TOOL_ERROR_ANSWER,
    TOOL_STEMS,
    TOOL_USE_ID_PREFIX,
    UNTRUSTED_PATTERN,
    WORD_PATTERN,
    WRITE_REASON,
    WriteSlot,
)

Message = dict[str, Any]


def _tool_use_id() -> str:
    return f"{TOOL_USE_ID_PREFIX}-{uuid4().hex[:8]}"


def _normalise(text: str) -> str:
    """Lowercase and accent-stripped, because the users type Spanish however they like."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _words(text: str) -> tuple[str, ...]:
    return tuple(WORD_PATTERN.findall(_normalise(text)))


def _first_number(words: tuple[str, ...]) -> int | None:
    return next((int(word) for word in words if word.isdigit()), None)


def _matches_a_stem(word: str, stems: tuple[str, ...], excluded: tuple[str, ...] = ()) -> bool:
    """A prefix match, so every conjugation of a stem counts; an excluded suffix vetoes it."""
    return word.startswith(stems) and not word.endswith(excluded)


def _mentions(words: tuple[str, ...], tool: ToolName) -> bool:
    return any(_matches_a_stem(w, TOOL_STEMS[tool], STEM_EXCLUSIONS.get(tool, ())) for w in words)


def _detect_tool(words: tuple[str, ...]) -> ToolName | None:
    return next((tool for tool in TOOL_STEMS if _mentions(words, tool)), None)


def _detect_status(words: tuple[str, ...]) -> OrderStatus | None:
    for status, stems in STATUS_STEMS.items():
        if any(_matches_a_stem(word, stems) for word in words):
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


def _balance_arguments(words: tuple[str, ...]) -> dict[str, Any] | None:
    client_id = _first_number(words)
    return None if client_id is None else {"client_id": client_id}


def _arguments_for(tool: ToolName, words: tuple[str, ...], text: str) -> dict[str, Any] | None:
    if tool is ToolName.GET_SALES_ORDERS:
        return _read_arguments(words, text)
    if tool is ToolName.GET_CLIENT_BALANCE:
        return _balance_arguments(words)
    return _write_arguments(words)


def _needs_the_order_lookup(tool: ToolName | None, words: tuple[str, ...]) -> bool:
    """A change with no order number: look them up instead of asking the user to guess one."""
    return tool is ToolName.UPDATE_ORDER_STATUS and _first_number(words) is None


def _opens_a_turn(message: Message) -> bool:
    """A plain-text user message; a tool_result continues a turn instead of starting one."""
    return message.get("role") == "user" and isinstance(message.get("content"), str)


def _current_turn(messages: list[Message]) -> list[Message]:
    """Messages since the latest plain-text user message: older turns are not a loop."""
    for index in reversed(range(len(messages))):
        if _opens_a_turn(messages[index]):
            return messages[index:]
    return list(messages)


def _turn_request(turn: list[Message]) -> str:
    """The plain-text user message this turn is answering, empty when there is none."""
    content = turn[0].get("content") if turn else ""
    return content if isinstance(content, str) else ""


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


def _said_text(message: Message) -> str:
    return "".join(b.get("text", "") for b in _blocks(message) if b.get("type") == "text")


def _clarified_tool(message: Message) -> ToolName | None:
    """The tool a clarification asked about, recognised by the line the client opened with."""
    text = _said_text(message)
    return next(
        (tool for tool, openers in CLARIFICATION_OPENERS.items() if text.startswith(openers)),
        None,
    )


def _pending_tool(messages: list[Message]) -> ToolName | None:
    """What the client asked about last, which is the only intent a follow-up may complete."""
    return next(
        (_clarified_tool(m) for m in reversed(messages) if m.get("role") == "assistant"), None
    )


def _is_status_word(word: str) -> bool:
    return any(_matches_a_stem(word, stems) for stems in STATUS_STEMS.values())


def _answers_a_slot(tool: ToolName, words: tuple[str, ...]) -> bool:
    """Only a number, a status, filler and the pending tool's own verb: an answer, not a new ask."""
    return bool(words) and all(
        word.isdigit()
        or _is_status_word(word)
        or word in SLOT_ANSWER_FILLERS
        or _mentions((word,), tool)
        for word in words
    )


def _clarified_words(messages: list[Message]) -> tuple[str, ...]:
    """Newest first, back through the turns the client answered with a question of its own.

    A turn it answered any other way is a request already served, and its words must not
    leak into the pending intent.
    """
    collected: list[str] = []
    answers: list[Message] = []
    for message in reversed(messages):
        if _opens_a_turn(message):
            if answers and not any(_clarified_tool(answer) for answer in answers):
                break
            collected.extend(_words(message["content"]))
            answers = []
        elif message.get("role") == "assistant":
            answers.append(message)
    return tuple(collected)


def _pending_arguments(tool: ToolName, words: tuple[str, ...]) -> dict[str, Any] | None:
    if tool is ToolName.UPDATE_ORDER_STATUS:
        return _write_arguments(words)
    return _balance_arguments(words)


def _missing_slot_ask(tool: ToolName, words: tuple[str, ...]) -> str:
    """Asks only for the half still missing; with both of them gone, the first question stands."""
    order_id, status = _first_number(words), _detect_status(words)
    if tool is ToolName.UPDATE_ORDER_STATUS and (order_id is None) != (status is None):
        return MISSING_SLOT_ASKS[WriteSlot.ORDER_ID if order_id is None else WriteSlot.NEW_STATUS]
    return CLARIFICATIONS[tool]


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


def _order_lines(orders: list[dict[str, Any]]) -> str:
    return ", ".join(
        ORDER_LINE.format(
            order_id=order["id"],
            status=STATUS_LABELS_ES[OrderStatus(order["status"])],
            total=order["total"],
        )
        for order in orders
    )


def _orders_answer(payload: dict[str, Any]) -> str:
    orders = payload.get("orders") or []
    if not orders:
        return ORDERS_EMPTY_ANSWER
    return ORDERS_ANSWER.format(
        count=payload["count"], sample=_order_lines(orders[:ORDERS_SAMPLE_SIZE])
    )


def _accepts_the_change(order: dict[str, Any], target: OrderStatus | None) -> bool:
    """Legal targets for the row, narrowed to the one the user asked for when it is known."""
    allowed = ALLOWED_TRANSITIONS[OrderStatus(order["status"])]
    return bool(allowed) if target is None else target in allowed


def _candidates_answer(payload: dict[str, Any], target: OrderStatus | None) -> str:
    """Offers only orders the change is legal for: a dead-end candidate is worse than none."""
    candidates = [
        order for order in payload.get("orders") or [] if _accepts_the_change(order, target)
    ]
    if not candidates:
        return CANDIDATES_EMPTY_ANSWER
    shown = candidates[:CANDIDATES_SAMPLE_SIZE]
    return CANDIDATES_ANSWER.format(
        question=CANDIDATES_QUESTION,
        shown=len(shown),
        found=len(candidates),
        sample=_order_lines(shown),
        example=shown[0]["id"],
    )


def _answer_from_result(turn: list[Message]) -> str:
    content = _last_tool_result(turn)
    if content is None:
        return LOOP_GUARD_REPLY
    payload = _unwrap(content)
    if payload is None:
        return content
    if "orders" in payload:
        words = _words(_turn_request(turn))
        if _needs_the_order_lookup(_detect_tool(words), words):
            return _candidates_answer(payload, _detect_status(words))
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
    ) -> LLMResponse:
        turn = _current_turn(messages)
        if _proposed_a_tool(turn):
            return self._text(_answer_from_result(turn))
        user_message = _turn_request(turn)
        pending = _pending_tool(messages)
        if pending is not None and _answers_a_slot(pending, _words(user_message)):
            return self._complete(pending, _clarified_words(messages))
        return self._propose(user_message)

    def _complete(self, tool: ToolName, words: tuple[str, ...]) -> LLMResponse:
        """Finishes the intent the last clarification asked about, or asks for what is left."""
        arguments = _pending_arguments(tool, words)
        if arguments is None:
            return self._text(_missing_slot_ask(tool, words))
        return self._tool_use(tool, arguments)

    def _propose(self, user_message: str) -> LLMResponse:
        words = _words(user_message)
        tool = _detect_tool(words)
        if tool is None:
            return self._text(CAPABILITIES_REPLY)
        arguments = _arguments_for(tool, words, user_message)
        if arguments is not None:
            return self._tool_use(tool, arguments)
        if _needs_the_order_lookup(tool, words):
            return self._tool_use(ToolName.GET_SALES_ORDERS, {})
        return self._text(_missing_slot_ask(tool, words))

    def _text(self, text: str) -> LLMResponse:
        return self._response("end_turn", [{"type": "text", "text": text}])

    def _tool_use(self, tool: ToolName, arguments: dict[str, Any]) -> LLMResponse:
        block = {"type": "tool_use", "id": _tool_use_id(), "name": tool.value, "input": arguments}
        return self._response("tool_use", [block])

    def _response(self, stop_reason: str, content: list[dict[str, Any]]) -> LLMResponse:
        return LLMResponse(
            stop_reason=stop_reason,
            content=content,
            input_tokens=0,
            output_tokens=0,
            model=self._model,
        )
