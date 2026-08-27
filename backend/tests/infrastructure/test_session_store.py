from decimal import Decimal

from app.infrastructure.session.memory import ConversationStore


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
