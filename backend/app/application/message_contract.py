"""The Messages API contract every message list handed to the LLM port must satisfy.

Anthropic rejects an orphaned tool_use, a tool_result outside a user message and two
messages in a row with the same role. Stated once here, for the code and for the tests.
"""

from itertools import pairwise
from typing import Any


class MessageContractError(ValueError):
    """A message list the Messages API would answer with a 400."""


def _blocks(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    return (
        [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []
    )


def _ids_of(message: dict[str, Any], block_type: str, id_key: str) -> list[Any]:
    return [b.get(id_key) for b in _blocks(message) if b.get("type") == block_type]


def _tool_use_ids(message: dict[str, Any]) -> list[Any]:
    return _ids_of(message, "tool_use", "id")


def _tool_result_ids(message: dict[str, Any]) -> list[Any]:
    return _ids_of(message, "tool_result", "tool_use_id")


def message_contract_violations(messages: list[dict[str, Any]]) -> list[str]:
    """Every way this conversation breaks the contract, so one run reports them all."""
    violations: list[str] = []
    for index, message in enumerate(messages):
        answered = {rid for later in messages[index + 1 :] for rid in _tool_result_ids(later)}
        orphans = [tid for tid in _tool_use_ids(message) if tid not in answered]
        if orphans:
            violations.append(f"message {index}: tool_use {orphans} has no later tool_result")
        if _tool_result_ids(message) and message.get("role") != "user":
            role = message.get("role")
            violations.append(f"message {index}: tool_result blocks sit in a {role!r} message")
    for index, (previous, current) in enumerate(pairwise(messages), start=1):
        if previous.get("role") == current.get("role"):
            role = current.get("role")
            violations.append(f"messages {index - 1}-{index}: two {role!r} messages in a row")
    return violations


def enforce_message_contract(messages: list[dict[str, Any]]) -> None:
    """Raises MessageContractError naming every violation; returns None when there are none."""
    violations = message_contract_violations(messages)
    if violations:
        raise MessageContractError("; ".join(violations))
