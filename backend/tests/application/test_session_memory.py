from app.application.session_memory import trim_history


def _turn(index: int, with_tool_result: bool = True) -> list[dict]:
    turn = [
        {"role": "user", "content": [{"type": "text", "text": f"pregunta {index}"}]},
        {"role": "assistant", "content": [{"type": "text", "text": f"respuesta {index}"}]},
    ]
    if with_tool_result:
        turn.insert(
            1,
            {"role": "user", "content": [{"type": "tool_result", "content": "x" * 500}]},
        )
    return turn


def test_a_non_list_content_is_never_mistaken_for_a_tool_result() -> None:
    history = [
        {"role": "assistant", "content": [{"type": "text", "text": "hola"}]},
        {"role": "user", "content": "plain text, not a content-block list"},
    ]
    assert trim_history(history, max_turns=6) == history


def test_recent_turns_are_kept_whole() -> None:
    history = [m for i in range(3) for m in _turn(i)]
    trimmed = trim_history(history, max_turns=6)
    assert trimmed == history


def test_old_tool_results_are_dropped_but_the_summary_survives() -> None:
    """The assistant already wrote what mattered; the raw 200-row table did not."""
    history = [m for i in range(10) for m in _turn(i)]
    trimmed = trim_history(history, max_turns=6)
    rendered = str(trimmed)
    assert "respuesta 0" in rendered
    assert "tool_result" not in str(trimmed[:6])


def test_trimming_shrinks_the_payload() -> None:
    history = [m for i in range(10) for m in _turn(i)]
    assert len(str(trim_history(history, max_turns=6))) < len(str(history))


def test_trimming_is_idempotent() -> None:
    history = [m for i in range(10) for m in _turn(i)]
    once = trim_history(history, max_turns=6)
    assert trim_history(once, max_turns=6) == once
