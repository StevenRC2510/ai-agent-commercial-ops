from app.application.message_contract import enforce_message_contract
from app.application.session_memory import trim_history


def _turn(index: int, with_tool_call: bool = True) -> list[dict]:
    """One turn exactly as run_turn builds it: plain question, proposal, result, prose."""
    question = {"role": "user", "content": f"pregunta {index}"}
    answer = {"role": "assistant", "content": [{"type": "text", "text": f"respuesta {index}"}]}
    if not with_tool_call:
        return [question, answer]
    return [
        question,
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": f"tu-{index}", "name": "get_sales_orders", "input": {}}
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": f"tu-{index}", "content": "x" * 500}
            ],
        },
        answer,
    ]


def _conversation(turns: int) -> list[dict]:
    return [message for index in range(turns) for message in _turn(index)]


def test_the_fixture_is_the_shape_the_orchestrator_really_builds() -> None:
    """If this fails every test below proves nothing: they would trim an impossible history."""
    enforce_message_contract(_conversation(10))


def test_a_non_list_content_is_never_mistaken_for_a_tool_result() -> None:
    history = [
        {"role": "assistant", "content": [{"type": "text", "text": "hola"}]},
        {"role": "user", "content": "plain text, not a content-block list"},
    ]
    assert trim_history(history, max_turns=6) == history


def test_recent_turns_are_kept_whole() -> None:
    history = _conversation(3)
    trimmed = trim_history(history, max_turns=6)
    assert trimmed == history


def test_old_tool_results_are_dropped_but_the_summary_survives() -> None:
    """The assistant already wrote what mattered; the raw 200-row table did not."""
    history = _conversation(10)
    trimmed = trim_history(history, max_turns=6)
    assert "respuesta 0" in str(trimmed)
    assert "tool_result" not in str(trimmed[:8])


def test_the_tool_use_an_old_tool_result_answered_is_dropped_with_it() -> None:
    """A kept tool_use whose result was trimmed away is exactly what the API rejects."""
    trimmed = trim_history(_conversation(10), max_turns=6)
    assert "tool_use" not in str(trimmed[:8])


def test_trimming_leaves_a_conversation_the_messages_api_would_accept() -> None:
    trimmed = trim_history(_conversation(10), max_turns=6)
    enforce_message_contract(trimmed)


def test_an_assistant_message_that_only_proposed_a_tool_disappears_entirely() -> None:
    """Stripping its only block would leave an empty content list, which is not sendable."""
    trimmed = trim_history(_conversation(10), max_turns=6)
    assert all(message["content"] for message in trimmed)


def test_a_turn_that_never_called_a_tool_is_left_untouched() -> None:
    history = [message for index in range(10) for message in _turn(index, with_tool_call=False)]
    assert trim_history(history, max_turns=6) == history


def test_trimming_shrinks_the_payload() -> None:
    history = _conversation(10)
    assert len(str(trim_history(history, max_turns=6))) < len(str(history))


def test_trimming_is_idempotent() -> None:
    history = _conversation(10)
    once = trim_history(history, max_turns=6)
    assert trim_history(once, max_turns=6) == once


def test_trimming_does_not_mutate_the_history_it_was_given() -> None:
    """chat.py keeps the trimmed list; the caller's messages must survive it unchanged."""
    history = _conversation(10)
    before = str(history)
    trim_history(history, max_turns=6)
    assert str(history) == before
