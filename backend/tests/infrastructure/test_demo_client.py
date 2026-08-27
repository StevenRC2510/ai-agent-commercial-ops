"""DemoClient: the keyword-driven fake model that makes DEMO_MODE a working system."""

import pytest

from app.application.agent.orchestrator import wrap_untrusted
from app.application.constants import Model
from app.application.permissions import ToolName
from app.infrastructure.llm.demo import DemoClient
from app.infrastructure.llm.demo_constants import (
    CAPABILITIES_REPLY,
    CLARIFICATIONS,
    KEYWORDS,
    LOOP_GUARD_REPLY,
    ORDERS_EMPTY_ANSWER,
)

ORDERS_PAYLOAD = {
    "count": 2,
    "orders": [
        {"id": 11, "client_id": 3, "status": "in_progress", "total": "2200.00"},
        {"id": 4, "client_id": 1, "status": "pending", "total": "990.00"},
    ],
}

BALANCE_PAYLOAD = {
    "client_id": 3,
    "name": "Miguel Santos",
    "total_ordered": "9000.00",
    "total_paid": "7500.00",
    "balance": "1500.00",
    "credit_limit": "22000.00",
    "exceeds_credit_limit": False,
}


def _create(messages):
    return DemoClient(model=Model.HAIKU_4_5).create(system="", messages=messages, tools=[])


def _reply_to(text):
    return _create([{"role": "user", "content": text}])


def _only_block(response):
    assert len(response.content) == 1, response.content
    return response.content[0]


def _text_of(response):
    return _only_block(response)["text"]


def _after_tool_result(user_text, content):
    """The shape run_turn builds: the proposal, then the result handed back to the model."""
    return [
        {"role": "user", "content": user_text},
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "demo", "name": "get_sales_orders", "input": {}}
            ],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "demo", "content": content}],
        },
    ]


@pytest.mark.parametrize(
    ("message", "expected_arguments"),
    [
        ("dame las ordenes pendientes", {"status": "pending"}),
        ("¿QUÉ ÓRDENES fueron ENTREGADAS?", {"status": "delivered"}),
        ("cuantas ordenes canceladas hay", {"status": "cancelled"}),
        ("lista de pedidos", {}),
        (
            "muestrame las ventas entre 2026-06-01 y 2026-06-15",
            {"date_from": "2026-06-01", "date_to": "2026-06-15"},
        ),
    ],
)
def test_a_read_intent_proposes_get_sales_orders(message, expected_arguments):
    """Accent- and case-insensitive: the demo users type Spanish, however they type it."""
    response = _reply_to(message)

    assert response.stop_reason == "tool_use"
    block = _only_block(response)
    assert block["name"] == ToolName.GET_SALES_ORDERS.value
    assert block["input"] == expected_arguments


@pytest.mark.parametrize(
    ("message", "expected_client_id"),
    [
        ("¿cuál es el saldo del cliente 3?", 3),
        ("cuanto DEBE el cliente 2", 2),
        ("pagos del cliente 7", 7),
    ],
)
def test_a_balance_intent_proposes_get_client_balance(message, expected_client_id):
    response = _reply_to(message)

    assert response.stop_reason == "tool_use"
    block = _only_block(response)
    assert block["name"] == ToolName.GET_CLIENT_BALANCE.value
    assert block["input"] == {"client_id": expected_client_id}


@pytest.mark.parametrize(
    ("message", "expected_order_id", "expected_status"),
    [
        ("marca la orden #11 como entregada", 11, "delivered"),
        ("cancela la orden 4", 4, "cancelled"),
        ("actualiza la orden 7 a en proceso", 7, "in_progress"),
        ("cambia la orden 9 a cancelada", 9, "cancelled"),
    ],
)
def test_a_write_intent_proposes_update_order_status(message, expected_order_id, expected_status):
    """The one path that must reach the confirmation card, so it needs valid arguments."""
    response = _reply_to(message)

    assert response.stop_reason == "tool_use"
    block = _only_block(response)
    assert block["name"] == ToolName.UPDATE_ORDER_STATUS.value
    assert block["input"]["order_id"] == expected_order_id
    assert block["input"]["new_status"] == expected_status
    assert len(block["input"]["reason"]) >= 3


def test_a_write_intent_without_an_order_asks_instead_of_inventing_one():
    response = _reply_to("quiero cambiar una orden")

    assert response.stop_reason == "end_turn"
    assert _text_of(response) == CLARIFICATIONS[ToolName.UPDATE_ORDER_STATUS]


def test_a_balance_intent_without_a_client_asks_instead_of_inventing_one():
    response = _reply_to("¿cuál es el saldo?")

    assert response.stop_reason == "end_turn"
    assert _text_of(response) == CLARIFICATIONS[ToolName.GET_CLIENT_BALANCE]


def test_an_unrecognised_message_says_what_it_can_do():
    response = _reply_to("hola, ¿qué tal?")

    assert response.stop_reason == "end_turn"
    assert _text_of(response) == CAPABILITIES_REPLY


def test_the_answer_after_a_read_quotes_the_rows_it_was_given():
    """Grounded, not canned: the numbers in the answer come from the tool result."""
    response = _create(_after_tool_result("dame las ordenes", wrap_untrusted(ORDERS_PAYLOAD)))

    assert response.stop_reason == "end_turn"
    answer = _text_of(response)
    assert "2" in answer
    assert "#11" in answer and "2200.00" in answer
    assert "#4" in answer and "990.00" in answer


def test_the_answer_after_an_empty_read_does_not_invent_rows():
    payload = {"count": 0, "orders": []}
    response = _create(_after_tool_result("dame las ordenes", wrap_untrusted(payload)))

    assert _text_of(response) == ORDERS_EMPTY_ANSWER


def test_the_answer_after_a_balance_quotes_the_client_row():
    response = _create(_after_tool_result("saldo del cliente 3", wrap_untrusted(BALANCE_PAYLOAD)))

    answer = _text_of(response)
    assert "Miguel Santos" in answer
    assert "1500.00" in answer


def test_a_tool_error_is_reported_and_not_dressed_up_as_data():
    payload = {"error": "client 99 does not exist"}
    response = _create(_after_tool_result("saldo del cliente 99", wrap_untrusted(payload)))

    assert "client 99 does not exist" in _text_of(response)


def test_a_denial_handed_back_as_plain_text_becomes_the_answer():
    """Policy denials arrive unwrapped and already in Spanish; the model just says them."""
    denial = "Tu rol no tiene permiso para esta operación."
    response = _create(_after_tool_result("cambia la orden 11 a entregada", denial))

    assert _text_of(response) == denial


def test_it_never_proposes_a_tool_twice_in_the_same_turn():
    """The loop guard: a proposal with no result back must still end the turn."""
    messages = [
        {"role": "user", "content": "dame las ordenes pendientes"},
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "demo", "name": "get_sales_orders", "input": {}}
            ],
        },
    ]

    response = _create(messages)

    assert response.stop_reason == "end_turn"
    assert _text_of(response) == LOOP_GUARD_REPLY


def test_a_tool_call_in_an_older_turn_does_not_silence_the_next_question():
    """The guard looks at the current turn only, or a session would answer once and stop."""
    history = _after_tool_result("dame las ordenes", wrap_untrusted(ORDERS_PAYLOAD))
    history.append({"role": "assistant", "content": [{"type": "text", "text": "Encontré 2."}]})
    history.append({"role": "user", "content": "¿cuál es el saldo del cliente 3?"})

    response = _create(history)

    assert response.stop_reason == "tool_use"
    assert _only_block(response)["name"] == ToolName.GET_CLIENT_BALANCE.value


def test_every_keyword_is_stored_already_normalised():
    """Matching happens on accent-stripped lowercase text, so an accented keyword is dead."""
    for tool, words in KEYWORDS.items():
        for word in words:
            assert word.isascii() and word.islower(), f"{tool.value}: {word!r}"
