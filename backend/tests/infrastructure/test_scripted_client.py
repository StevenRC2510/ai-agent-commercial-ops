import pytest

from app.application.ports import LLMResponse
from app.infrastructure.llm.scripted import ScriptedClient, ScriptExhaustedError


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


def test_a_scripted_exception_is_raised_instead_of_returned() -> None:
    """Lets a test simulate a timeout without touching the network."""
    client = ScriptedClient([TimeoutError("simulated")])
    with pytest.raises(TimeoutError):
        client.create(system="s", messages=[], tools=[])
