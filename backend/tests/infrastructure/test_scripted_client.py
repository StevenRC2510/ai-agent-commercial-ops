import pytest

from app.application.message_contract import MessageContractError
from app.application.ports import LLMResponse
from app.infrastructure.llm.scripted import ScriptedClient, ScriptExhaustedError

_ORPHANED_TOOL_USE = [
    {"role": "user", "content": "cambia la orden"},
    {
        "role": "assistant",
        "content": [{"type": "tool_use", "id": "tu-1", "name": "t", "input": {}}],
    },
    {"role": "user", "content": "gracias"},
]


def _message(text: str) -> LLMResponse:
    return LLMResponse(
        stop_reason="end_turn",
        content=[{"type": "text", "text": text}],
        input_tokens=10,
        output_tokens=5,
        model="scripted",
    )


def test_responses_come_back_in_order() -> None:
    client = ScriptedClient([_message("uno"), _message("dos")])
    assert client.create(system="s", messages=[], tools=[]).content[0]["text"] == "uno"
    assert client.create(system="s", messages=[], tools=[]).content[0]["text"] == "dos"


def test_running_out_of_script_raises_rather_than_repeating() -> None:
    """A silent repeat would make a test loop forever and look like a hang."""
    client = ScriptedClient([_message("uno")])
    client.create(system="s", messages=[], tools=[])
    with pytest.raises(ScriptExhaustedError):
        client.create(system="s", messages=[], tools=[])


def test_the_client_records_what_it_was_asked() -> None:
    """Behaviour tests assert on the prompt and tool list the orchestrator sent."""
    client = ScriptedClient([_message("uno")])
    client.create(system="system text", messages=[{"role": "user"}], tools=[{"name": "t"}])
    assert client.calls[0].system == "system text"
    assert client.calls[0].tools == [{"name": "t"}]


def test_a_conversation_the_real_api_would_reject_is_rejected_here_too() -> None:
    """The double used to ignore `messages`, so no test could ever see a malformed one."""
    client = ScriptedClient([_message("uno")])
    with pytest.raises(MessageContractError):
        client.create(system="s", messages=_ORPHANED_TOOL_USE, tools=[])


def test_a_refused_conversation_is_still_recorded_for_the_post_mortem() -> None:
    client = ScriptedClient([_message("uno")])
    with pytest.raises(MessageContractError):
        client.create(system="s", messages=_ORPHANED_TOOL_USE, tools=[])
    assert client.calls[0].messages == _ORPHANED_TOOL_USE


def test_a_refused_conversation_does_not_consume_the_script() -> None:
    """Otherwise a contract failure would cascade into a confusing ScriptExhaustedError."""
    client = ScriptedClient([_message("uno")])
    with pytest.raises(MessageContractError):
        client.create(system="s", messages=_ORPHANED_TOOL_USE, tools=[])
    assert client.create(system="s", messages=[], tools=[]).content[0]["text"] == "uno"


def test_a_scripted_exception_is_raised_instead_of_returned() -> None:
    """Lets a test simulate a timeout without touching the network."""
    client = ScriptedClient([TimeoutError("simulated")])
    with pytest.raises(TimeoutError):
        client.create(system="s", messages=[], tools=[])
