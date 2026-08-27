"""DemoClient: the keyword-driven fake model that makes DEMO_MODE a working system."""

import re

import pytest

from app.application.agent.orchestrator import wrap_untrusted
from app.application.constants import Model
from app.application.permissions import ToolName
from app.domain.constants import ALLOWED_TRANSITIONS, OrderStatus
from app.infrastructure.llm.demo import DemoClient
from app.infrastructure.llm.demo_constants import (
    CANDIDATES_EMPTY_ANSWER,
    CANDIDATES_QUESTION,
    CANDIDATES_SAMPLE_SIZE,
    CAPABILITIES_REPLY,
    CLARIFICATIONS,
    LOOP_GUARD_REPLY,
    MISSING_SLOT_ASKS,
    ORDERS_EMPTY_ANSWER,
    SLOT_ANSWER_FILLERS,
    STATUS_STEMS,
    TOOL_STEMS,
    WRITE_REASON,
    WriteSlot,
)

ORDERS_PAYLOAD = {
    "count": 2,
    "orders": [
        {"id": 11, "client_id": 3, "status": "in_progress", "total": "2200.00"},
        {"id": 4, "client_id": 1, "status": "pending", "total": "990.00"},
    ],
}

# Newest first, as the tool returns them: two candidates, one delivered and one cancelled.
MIXED_ORDERS_PAYLOAD = {
    "count": 4,
    "orders": [
        {"id": 30, "client_id": 2, "status": "delivered", "total": "100.00"},
        {"id": 12, "client_id": 3, "status": "in_progress", "total": "2200.00"},
        {"id": 9, "client_id": 1, "status": "cancelled", "total": "300.00"},
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


@pytest.mark.parametrize(
    ("message", "expected_status"),
    [
        ("mueve la orden 3 a en proceso", "in_progress"),
        ("quiero que muevas la orden #3 a en proceso", "in_progress"),
        ("muévela a entregada, la orden 3", "delivered"),
        ("quiero mover la orden 3 a en proceso", "in_progress"),
        ("cambia la orden 3 a en proceso", "in_progress"),
        ("necesito que cambies la orden 3 a entregada", "delivered"),
        ("quiero cambiar la orden 3 a cancelada", "cancelled"),
        ("actualiza la orden 3 a en proceso", "in_progress"),
        ("quiero que actualices la orden 3 a entregada", "delivered"),
        ("cancela la orden 3", "cancelled"),
        ("quiero que canceles la orden 3", "cancelled"),
        ("marca la orden 3 como entregada", "delivered"),
        ("necesito que marques la orden 3 como entregada", "delivered"),
    ],
)
def test_any_conjugation_of_a_write_verb_still_proposes_the_write(message, expected_status):
    """A subjunctive asks for the same change as the imperative, and is not a listing."""
    response = _reply_to(message)

    assert response.stop_reason == "tool_use"
    block = _only_block(response)
    assert block["name"] == ToolName.UPDATE_ORDER_STATUS.value
    assert block["input"]["order_id"] == 3
    assert block["input"]["new_status"] == expected_status


@pytest.mark.parametrize(
    ("message", "expected_status"),
    [
        ("muéstrame las órdenes canceladas del cliente 6", "cancelled"),
        ("¿cuáles están canceladas?", "cancelled"),
        ("dame los pedidos cancelados", "cancelled"),
        ("¿qué órdenes fueron entregadas?", "delivered"),
        ("cuántas ventas hay entregadas", "delivered"),
    ],
)
def test_a_past_participle_names_a_state_and_never_triggers_the_write_it_stems_from(
    message, expected_status
):
    """The trap `cancelled_orders_are_a_read_not_a_write` pins: a stem must not swallow it."""
    response = _reply_to(message)

    assert response.stop_reason == "tool_use"
    block = _only_block(response)
    assert block["name"] == ToolName.GET_SALES_ORDERS.value
    assert block["input"] == {"status": expected_status}


def test_a_write_intent_without_an_order_looks_them_up_instead_of_inventing_one():
    """Asking the user to guess an id is a dead end; the read it may do answers the question."""
    response = _reply_to("quiero cambiar una orden")

    assert response.stop_reason == "tool_use"
    block = _only_block(response)
    assert block["name"] == ToolName.GET_SALES_ORDERS.value
    # No status filter: the candidates must not be narrowed to the state asked for.
    assert block["input"] == {}


def test_a_write_intent_with_an_order_but_no_status_asks_only_for_the_status():
    response = _reply_to("actualiza la orden 3")

    assert response.stop_reason == "end_turn"
    assert _text_of(response) == MISSING_SLOT_ASKS[WriteSlot.NEW_STATUS]


def _candidate_ids(text):
    return [int(number) for number in re.findall(r"#(\d+)", text)]


def _lookup_answer(payload, request="quiero cambiar una orden"):
    """What the client says once the lookup it proposed comes back."""
    return _text_of(_create(_after_tool_result(request, wrap_untrusted(payload))))


def test_the_lookup_answer_offers_the_orders_it_was_given_by_id():
    answer = _lookup_answer(MIXED_ORDERS_PAYLOAD)

    assert answer.startswith(CANDIDATES_QUESTION)
    assert _candidate_ids(answer) == [12, 4]
    assert "en proceso" in answer and "2200.00" in answer


def test_the_lookup_answer_never_offers_an_order_that_can_no_longer_change():
    """A delivered or cancelled candidate walks the user into a refusal the policy will raise."""
    answer = _lookup_answer(MIXED_ORDERS_PAYLOAD)

    assert 30 not in _candidate_ids(answer)
    assert 9 not in _candidate_ids(answer)


def test_every_order_the_lookup_answer_offers_is_one_a_change_is_still_legal_for():
    """Pinned against the domain table, so a new transition can never make this list stale."""
    by_id = {order["id"]: order["status"] for order in MIXED_ORDERS_PAYLOAD["orders"]}
    answer = _lookup_answer(MIXED_ORDERS_PAYLOAD)

    for order_id in _candidate_ids(answer):
        assert ALLOWED_TRANSITIONS[OrderStatus(by_id[order_id])]


def test_the_candidates_are_narrowed_to_the_change_the_user_asked_for():
    """Order 4 is pending: offering it for "a entregada" is an illegal transition, not a choice."""
    answer = _lookup_answer(MIXED_ORDERS_PAYLOAD, request="cambia una orden a entregada")

    assert _candidate_ids(answer) == [12]


def test_no_order_accepting_the_requested_change_is_reported_instead_of_offering_a_wrong_one():
    pending_only = {"count": 1, "orders": [MIXED_ORDERS_PAYLOAD["orders"][3]]}

    answer = _lookup_answer(pending_only, request="cambia una orden a entregada")

    assert answer == CANDIDATES_EMPTY_ANSWER


def test_the_lookup_answer_says_how_many_it_is_showing_instead_of_truncating_silently():
    orders = [
        {"id": index, "client_id": 1, "status": "pending", "total": "10.00"}
        for index in range(1, CANDIDATES_SAMPLE_SIZE + 3)
    ]
    answer = _lookup_answer({"count": len(orders), "orders": orders})

    assert len(_candidate_ids(answer)) == CANDIDATES_SAMPLE_SIZE
    assert str(CANDIDATES_SAMPLE_SIZE) in answer
    assert str(len(orders)) in answer


def test_a_lookup_that_finds_nothing_changeable_says_so_instead_of_offering_a_dead_end():
    settled = {"id": 30, "client_id": 1, "status": "delivered", "total": "1.00"}

    assert _lookup_answer({"count": 1, "orders": [settled]}) == CANDIDATES_EMPTY_ANSWER


def test_an_ordinary_read_still_answers_with_rows_not_with_candidates():
    """Only a write missing its order turns a read result into a question."""
    turn = _after_tool_result("dame las ordenes", wrap_untrusted(ORDERS_PAYLOAD))

    assert not _text_of(_create(turn)).startswith(CANDIDATES_QUESTION)


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


def test_every_stem_is_stored_already_normalised():
    """Matching happens on accent-stripped lowercase text, so an accented stem is dead."""
    for key, stems in (*TOOL_STEMS.items(), *STATUS_STEMS.items()):
        for stem in stems:
            assert stem.isascii() and stem.islower(), f"{key.value}: {stem!r}"


def test_every_filler_is_stored_already_normalised():
    for word in SLOT_ANSWER_FILLERS:
        assert word.isascii() and word.islower(), repr(word)


def _clarified(*exchanges):
    """(user message, the line the demo model answered with), in the shape a session stores."""
    messages = []
    for user_text, reply in exchanges:
        messages.append({"role": "user", "content": user_text})
        messages.append({"role": "assistant", "content": [{"type": "text", "text": reply}]})
    return messages


_WRITE_ASK = CLARIFICATIONS[ToolName.UPDATE_ORDER_STATUS]


@pytest.mark.parametrize("follow_up", ["la 12", "la orden 12", "12", "orden 12 a entregada"])
def test_the_answer_to_a_clarification_completes_the_write_it_asked_about(follow_up):
    """The dead end this fixes: the model asked which order, and ignored the answer."""
    messages = _clarified(("Cambia una orden a entregada", _WRITE_ASK))
    messages.append({"role": "user", "content": follow_up})

    response = _create(messages)

    assert response.stop_reason == "tool_use"
    block = _only_block(response)
    assert block["name"] == ToolName.UPDATE_ORDER_STATUS.value
    assert block["input"]["order_id"] == 12
    assert block["input"]["new_status"] == "delivered"


def test_a_follow_up_that_only_gives_the_order_asks_for_the_status_it_still_lacks():
    """Half an answer is not an answer: inventing the other half is what must never happen."""
    messages = _clarified(("quiero cambiar una orden", _WRITE_ASK))
    messages.append({"role": "user", "content": "la 12"})

    response = _create(messages)

    assert response.stop_reason == "end_turn"
    assert _text_of(response) == MISSING_SLOT_ASKS[WriteSlot.NEW_STATUS]


def test_a_follow_up_that_only_gives_the_status_asks_for_the_order_it_still_lacks():
    messages = _clarified(("quiero cambiar una orden", _WRITE_ASK))
    messages.append({"role": "user", "content": "a entregada"})

    response = _create(messages)

    assert response.stop_reason == "end_turn"
    assert _text_of(response) == MISSING_SLOT_ASKS[WriteSlot.ORDER_ID]


def test_the_two_halves_can_arrive_in_two_separate_follow_ups():
    """Each answer is kept, so the intent survives as long as the model keeps asking."""
    messages = _clarified(
        ("quiero cambiar una orden", _WRITE_ASK),
        ("la 12", MISSING_SLOT_ASKS[WriteSlot.NEW_STATUS]),
    )
    messages.append({"role": "user", "content": "entregada"})

    response = _create(messages)

    assert response.stop_reason == "tool_use"
    assert _only_block(response)["input"] == {
        "order_id": 12,
        "new_status": "delivered",
        "reason": WRITE_REASON,
    }


def test_a_follow_up_that_repeats_the_verb_is_still_read_as_an_answer():
    """The second half of the dead end: "muévela a en proceso" answered, and was ignored."""
    messages = _clarified(
        ("quiero cambiar una orden", _WRITE_ASK),
        ("la 12", MISSING_SLOT_ASKS[WriteSlot.NEW_STATUS]),
    )
    messages.append({"role": "user", "content": "muévela a en proceso"})

    response = _create(messages)

    assert response.stop_reason == "tool_use"
    block = _only_block(response)
    assert block["name"] == ToolName.UPDATE_ORDER_STATUS.value
    assert block["input"]["order_id"] == 12
    assert block["input"]["new_status"] == "in_progress"


def test_a_write_after_a_balance_question_is_a_new_request_not_the_answer_to_it():
    """A verb the pending tool does not own is a change of subject: 12 is an order, not a client."""
    messages = _clarified(("¿cuál es el saldo?", CLARIFICATIONS[ToolName.GET_CLIENT_BALANCE]))
    messages.append({"role": "user", "content": "cambia la orden 12 a entregada"})

    response = _create(messages)

    assert response.stop_reason == "tool_use"
    block = _only_block(response)
    assert block["name"] == ToolName.UPDATE_ORDER_STATUS.value
    assert block["input"]["order_id"] == 12
    assert block["input"]["new_status"] == "delivered"


def test_a_follow_up_that_supplies_nothing_repeats_the_question_it_already_asked():
    messages = _clarified(("quiero cambiar una orden", _WRITE_ASK))
    messages.append({"role": "user", "content": "la orden"})

    response = _create(messages)

    assert response.stop_reason == "end_turn"
    assert _text_of(response) == _WRITE_ASK


def test_an_order_from_an_already_answered_request_is_never_reused_by_a_later_one():
    """The memory reaches back through questions only, never through a request already served."""
    messages = _clarified(("quiero cambiar una orden", _WRITE_ASK))
    messages.append({"role": "user", "content": "la 12"})
    messages.append(
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "demo",
                    "name": "update_order_status",
                    "input": {"order_id": 12},
                }
            ],
        }
    )
    messages.extend(_clarified(("quiero cambiar otra orden", _WRITE_ASK)))
    messages.append({"role": "user", "content": "a entregada"})

    response = _create(messages)

    assert response.stop_reason == "end_turn"
    assert _text_of(response) == MISSING_SLOT_ASKS[WriteSlot.ORDER_ID]


def test_the_answer_to_a_balance_clarification_completes_the_balance_query():
    messages = _clarified(("¿cuál es el saldo?", CLARIFICATIONS[ToolName.GET_CLIENT_BALANCE]))
    messages.append({"role": "user", "content": "el 3"})

    response = _create(messages)

    assert response.stop_reason == "tool_use"
    block = _only_block(response)
    assert block["name"] == ToolName.GET_CLIENT_BALANCE.value
    assert block["input"] == {"client_id": 3}


def test_an_unrelated_question_after_a_clarification_is_answered_on_its_own_terms():
    """A new question is not the missing half: the pending intent must not swallow it."""
    messages = _clarified(("quiero cambiar una orden", _WRITE_ASK))
    messages.append({"role": "user", "content": "¿cuál es el saldo del cliente 3?"})

    response = _create(messages)

    assert response.stop_reason == "tool_use"
    block = _only_block(response)
    assert block["name"] == ToolName.GET_CLIENT_BALANCE.value
    assert block["input"] == {"client_id": 3}


def test_a_number_after_an_ordinary_answer_is_not_treated_as_a_follow_up():
    """Only the model's own question opens the follow-up path; a plain answer does not."""
    messages = _clarified(("dame las ordenes", "Encontré 2 órdenes."))
    messages.append({"role": "user", "content": "la 12"})

    response = _create(messages)

    assert response.stop_reason == "end_turn"
    assert _text_of(response) == CAPABILITIES_REPLY
