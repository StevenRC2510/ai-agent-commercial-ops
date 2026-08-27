"""History trimming (SPEC 2 §6.2). Pure list grouping and slicing, no IO.

`ConversationStore` (mutable state across requests) stays in
`app.infrastructure.session.memory`; this module holds only the pure shaping logic.
"""

from typing import Any


def _is_tool_result_message(message: dict[str, Any]) -> bool:
    content = message.get("content")
    if not isinstance(content, list) or not content:
        return False
    return all(isinstance(block, dict) and block.get("type") == "tool_result" for block in content)


def _starts_new_turn(message: dict[str, Any]) -> bool:
    return message.get("role") == "user" and not _is_tool_result_message(message)


def _group_into_turns(history: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    turns: list[list[dict[str, Any]]] = []
    for message in history:
        if not turns or _starts_new_turn(message):
            turns.append([message])
        else:
            turns[-1].append(message)
    return turns


def trim_history(history: list[dict[str, Any]], max_turns: int) -> list[dict[str, Any]]:
    """Keep the last max_turns turns whole; drop tool_result blocks from older ones.

    The assistant's text already summarizes what a tool returned, so the raw
    tool_result payload of an old turn carries no information the model still needs.
    """
    turns = _group_into_turns(history)
    if len(turns) <= max_turns:
        return list(history)
    old_turns, recent_turns = turns[:-max_turns], turns[-max_turns:]
    trimmed_old = [
        message for turn in old_turns for message in turn if not _is_tool_result_message(message)
    ]
    kept_recent = [message for turn in recent_turns for message in turn]
    return trimmed_old + kept_recent
