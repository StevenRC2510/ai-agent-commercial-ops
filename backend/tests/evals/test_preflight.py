"""HARNESS TESTS — the gate that refuses to run without a real model.

Falling back to a fake client here would produce numbers that measure our own keyword
matcher. These tests pin that the harness stops instead.
"""

from dataclasses import dataclass

from pydantic import BaseModel, ValidationError, field_validator

from evals.preflight import blocking_problems, render_blocked


@dataclass
class FakeSettings:
    demo_mode: bool = False
    anthropic_api_key: str = "placeholder-not-a-key"


def loader_for(settings):
    return lambda: settings


def raising_loader(exc):
    def load():
        raise exc

    return load


def a_validation_error(message="required"):
    class Model(BaseModel):
        value: int = 0

        @field_validator("value")
        @classmethod
        def always_fails(cls, _):
            raise ValueError(message)

    try:
        Model(value=1)
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a ValidationError")


def test_a_fully_configured_environment_has_no_blocking_problem():
    assert blocking_problems(loader_for(FakeSettings())) == ()


def test_demo_mode_blocks_the_run():
    """The whole point of the suite is measuring the real model, not the demo client."""
    problems = blocking_problems(loader_for(FakeSettings(demo_mode=True)))
    assert len(problems) == 1
    assert "DEMO_MODE" in problems[0]


def test_a_missing_api_key_blocks_the_run():
    problems = blocking_problems(loader_for(FakeSettings(anthropic_api_key="")))
    assert len(problems) == 1
    assert "ANTHROPIC_API_KEY" in problems[0]


def test_both_problems_are_reported_together():
    """One run, one list: a developer fixes both before trying again, not one at a time."""
    problems = blocking_problems(loader_for(FakeSettings(demo_mode=True, anthropic_api_key="")))
    assert len(problems) == 2


def test_settings_that_refuse_to_load_are_reported_as_a_blocking_problem():
    """DEMO_MODE=false with no key makes app.config raise at import; that is not a crash."""
    problems = blocking_problems(raising_loader(a_validation_error()))
    assert len(problems) == 1
    assert "ANTHROPIC_API_KEY" in problems[0]


def test_the_blocked_message_names_what_to_set_and_says_nothing_ran():
    text = render_blocked(blocking_problems(loader_for(FakeSettings(demo_mode=True))))
    assert "DEMO_MODE" in text
    assert "ANTHROPIC_API_KEY" in text
    assert "No cases were run" in text


def test_a_configuration_error_never_echoes_what_it_was_validating():
    """Settings errors quote their input, and one of those inputs is a database password."""
    decoy = "MUST-NOT-BE-ECHOED-BACK"
    problems = blocking_problems(raising_loader(a_validation_error(decoy)))
    assert decoy not in render_blocked(problems)
