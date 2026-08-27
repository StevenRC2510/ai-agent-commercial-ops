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


def _without_tool_use_blocks(message: dict[str, Any]) -> dict[str, Any] | None:
    """None when nothing but tool_use blocks was there: an empty content list is not sendable."""
    content = message.get("content")
    if not isinstance(content, list):
        return message
    kept = [b for b in content if not (isinstance(b, dict) and b.get("type") == "tool_use")]
    if not kept:
        return None
    return message if len(kept) == len(content) else {**message, "content": kept}


def _reduced_to_prose(turn: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """An old turn without its tool traffic: the results go, and so do the calls they answer."""
    kept: list[dict[str, Any]] = []
    for message in turn:
        if _is_tool_result_message(message):
            continue
        stripped = _without_tool_use_blocks(message)
        if stripped is not None:
            kept.append(stripped)
    return kept


def trim_history(history: list[dict[str, Any]], max_turns: int) -> list[dict[str, Any]]:
    """Keep the last max_turns turns whole; drop the tool traffic of the older ones.

    The assistant's text already summarizes what a tool returned, so an old turn keeps
    its prose. A tool_use whose tool_result went with it would be an orphan the API rejects.
    """
    turns = _group_into_turns(history)
    if len(turns) <= max_turns:
        return list(history)
    old_turns, recent_turns = turns[:-max_turns], turns[-max_turns:]
    trimmed_old = [message for turn in old_turns for message in _reduced_to_prose(turn)]
    kept_recent = [message for turn in recent_turns for message in turn]
    return trimmed_old + kept_recent
