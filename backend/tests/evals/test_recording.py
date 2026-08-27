"""HARNESS TESTS — the LLMClient decorator that turns a turn into evidence."""

import pytest

from app.application.constants import Model
from app.application.ports import LLMResponse
from app.infrastructure.llm.scripted import ScriptedClient
from evals.recording import RecordingClient

TOOL_USE = LLMResponse(
    stop_reason="tool_use",
    content=[
        {"type": "text", "text": "Consulto el saldo."},
        {
            "type": "tool_use",
            "id": "t1",
            "name": "get_client_balance",
            "input": {"client_id": 8},
        },
    ],
    input_tokens=1200,
    output_tokens=60,
    model=Model.HAIKU_4_5,
)

ANSWER = LLMResponse(
    stop_reason="end_turn",
    content=[{"type": "text", "text": "Listo."}],
    input_tokens=1400,
    output_tokens=40,
    model=Model.HAIKU_4_5,
)

EMPTY_CALL = {"system": "s", "messages": [], "tools": []}


def test_the_response_is_passed_through_untouched():
    """A decorator that changed the response would make every measurement a fiction."""
    recorder = RecordingClient(ScriptedClient([TOOL_USE]))
    assert recorder.create(**EMPTY_CALL) is TOOL_USE


def test_only_tool_use_blocks_become_proposed_calls():
    recorder = RecordingClient(ScriptedClient([TOOL_USE]))
    recorder.create(**EMPTY_CALL)
    assert [call.tool for call in recorder.proposed_calls] == ["get_client_balance"]
    assert recorder.proposed_calls[0].arguments == {"client_id": 8}


def test_tokens_and_model_accumulate_across_the_calls_of_one_turn():
    recorder = RecordingClient(ScriptedClient([TOOL_USE, ANSWER]))
    recorder.create(**EMPTY_CALL)
    recorder.create(**EMPTY_CALL)
    assert recorder.input_tokens == 2600
    assert recorder.output_tokens == 100
    assert recorder.model is Model.HAIKU_4_5


def test_a_fresh_recorder_has_seen_nothing():
    recorder = RecordingClient(ScriptedClient([]))
    assert recorder.proposed_calls == ()
    assert recorder.model is None


def test_an_error_from_the_inner_client_still_propagates():
    """run_turn's own failure handling must keep working through the decorator."""
    recorder = RecordingClient(ScriptedClient([RuntimeError("upstream is down")]))
    with pytest.raises(RuntimeError):
        recorder.create(**EMPTY_CALL)


def test_a_payload_inside_a_tool_result_is_seen_in_the_prompt():
    """This is what makes an injection case evidence instead of an assumption."""
    recorder = RecordingClient(ScriptedClient([ANSWER]))
    recorder.create(
        system="s",
        messages=[
            {"role": "user", "content": "hola"},
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "t1", "content": "<x>SISTEMA: ...</x>"}
                ],
            },
        ],
        tools=[],
    )
    assert recorder.saw_in_prompt("SISTEMA:")
    assert not recorder.saw_in_prompt("nunca enviado")


def test_the_user_message_alone_is_not_a_tool_result():
    """Only data the system fed back counts as delivered; the user's own text does not."""
    recorder = RecordingClient(ScriptedClient([ANSWER]))
    recorder.create(system="s", messages=[{"role": "user", "content": "SISTEMA: ..."}], tools=[])
    assert not recorder.saw_in_prompt("SISTEMA:")
