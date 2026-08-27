"""HARNESS TESTS — the command line and its refusal path.

The refusal path is the one that matters most here: a silent fallback to the fake client
would turn `make eval` into a machine for producing confident, meaningless numbers.
"""

from dataclasses import dataclass

import pytest

from app.application.constants import Model
from evals.run import ExitCode, main, parse_args


@dataclass
class FakeSettings:
    demo_mode: bool = False
    anthropic_api_key: str = "placeholder-not-a-key"
    llm_model: Model = Model.HAIKU_4_5
    llm_temperature: float = 0.0
    llm_timeout_seconds: int = 30
    llm_max_tokens: int = 1024
    pending_action_ttl_seconds: int = 300


def loader_for(settings):
    return lambda: settings


def test_no_model_flag_means_the_configured_model():
    assert parse_args([]).model is None


def test_the_model_flag_accepts_a_priced_model():
    assert parse_args(["--model", "claude-sonnet-5"]).model == "claude-sonnet-5"


def test_an_unpriced_model_is_rejected_at_the_command_line():
    """estimate_cost has no row for it, so the run would report a cost it cannot compute."""
    with pytest.raises(SystemExit):
        parse_args(["--model", "gpt-4o"])


def test_demo_mode_stops_the_run_and_explains_why(capsys):
    code = main([], settings_loader=loader_for(FakeSettings(demo_mode=True)))
    captured = capsys.readouterr()
    assert code == ExitCode.BLOCKED
    assert "DEMO_MODE" in captured.err
    assert captured.out == ""


def test_a_missing_api_key_stops_the_run_and_explains_why(capsys):
    code = main([], settings_loader=loader_for(FakeSettings(anthropic_api_key="")))
    captured = capsys.readouterr()
    assert code == ExitCode.BLOCKED
    assert "ANTHROPIC_API_KEY" in captured.err
    assert captured.out == ""


def test_the_refusal_says_no_results_were_produced(capsys):
    """Not "0% passed": nothing ran, and the difference is the whole point."""
    main([], settings_loader=loader_for(FakeSettings(demo_mode=True)))
    assert "No cases were run" in capsys.readouterr().err


def test_the_exit_codes_are_distinct():
    """A CI wrapper has to tell "could not run" apart from "ran and something failed"."""
    assert len({ExitCode.OK, ExitCode.FAILURES, ExitCode.BLOCKED}) == 3
