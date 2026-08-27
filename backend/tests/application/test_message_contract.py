"""The Messages API contract stated as tests: what "a valid conversation" means here."""

import pytest

from app.application.message_contract import (
    MessageContractError,
    enforce_message_contract,
    message_contract_violations,
)


def _user(text: str) -> dict:
    return {"role": "user", "content": text}


def _assistant_text(text: str) -> dict:
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def _assistant_tool_use(tool_use_id: str) -> dict:
    return {
        "role": "assistant",
        "content": [{"type": "tool_use", "id": tool_use_id, "name": "t", "input": {}}],
    }


def _tool_result(tool_use_id: str, role: str = "user") -> dict:
    return {
        "role": role,
        "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": "x"}],
    }


VALID = [_user("q"), _assistant_tool_use("tu1"), _tool_result("tu1"), _assistant_text("a")]


def test_a_complete_tool_calling_exchange_is_accepted():
    assert message_contract_violations(VALID) == []


def test_an_empty_conversation_is_accepted():
    assert message_contract_violations([]) == []


def test_a_plain_string_content_carries_no_blocks():
    assert message_contract_violations([_user("hola")]) == []


def test_a_tool_use_with_no_tool_result_is_an_orphan():
    violations = message_contract_violations([_user("q"), _assistant_tool_use("tu1")])
    assert len(violations) == 1
    assert "tu1" in violations[0]


def test_a_tool_result_that_precedes_its_tool_use_does_not_resolve_it():
    """The result must answer a call already made, so position is part of the rule."""
    violations = message_contract_violations([_tool_result("tu1"), _assistant_tool_use("tu1")])
    assert len(violations) == 1
    assert "tu1" in violations[0]


def test_a_tool_result_outside_a_user_message_is_rejected():
    violations = message_contract_violations([_user("q"), _tool_result("tu1", role="assistant")])
    assert len(violations) == 1
    assert "assistant" in violations[0]


def test_two_messages_with_the_same_role_in_a_row_are_rejected():
    violations = message_contract_violations(
        [_user("q"), _assistant_text("a"), _assistant_text("b")]
    )
    assert len(violations) == 1
    assert "assistant" in violations[0]


def test_every_violation_is_reported_not_just_the_first():
    """The shape trim_history produced: an orphan and a role collision in one list."""
    history = [_user("q"), _assistant_tool_use("tu1"), _assistant_text("a")]
    assert len(message_contract_violations(history)) == 2


def test_enforce_accepts_a_valid_conversation_silently():
    assert enforce_message_contract(VALID) is None


def test_enforce_raises_carrying_every_violation():
    with pytest.raises(MessageContractError) as raised:
        enforce_message_contract([_user("q"), _assistant_tool_use("tu1"), _assistant_text("a")])
    assert "tu1" in str(raised.value)
    assert "assistant" in str(raised.value)
