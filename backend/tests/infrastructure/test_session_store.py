from decimal import Decimal

from app.infrastructure.session.memory import ConversationStore, trim_history


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


def test_a_new_session_is_created_on_first_use() -> None:
    store = ConversationStore(history_max_turns=6)
    session = store.get_or_create("s-1")
    assert session.session_id == "s-1"
    assert session.history == []


def test_the_same_session_comes_back() -> None:
    store = ConversationStore(history_max_turns=6)
    first = store.get_or_create("s-1")
    first.add_cost(Decimal("0.01"))
    store.save(first)
    assert store.get_or_create("s-1").accumulated_cost_usd == Decimal("0.01")


def test_sessions_are_isolated_from_each_other() -> None:
    store = ConversationStore(history_max_turns=6)
    a = store.get_or_create("s-1")
    a.history.append({"role": "user", "content": "hola"})
    store.save(a)
    assert store.get_or_create("s-2").history == []


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
