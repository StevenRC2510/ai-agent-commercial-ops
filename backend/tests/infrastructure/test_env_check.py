"""Tests for the environment validator derived from app.config.Settings."""

from app.config import Settings
from app.infrastructure import env_check


def test_find_problems_is_empty_for_the_current_environment():
    assert env_check.find_problems() == []


def test_main_prints_a_confirmation_and_exits_zero_on_success(capsys):
    exit_code = env_check.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "OK" in captured.out


def test_find_problems_reports_an_invalid_log_level(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "NOT_A_LEVEL")

    problems = env_check.find_problems()

    assert any("LOG_LEVEL" in problem for problem in problems)


def test_find_problems_reports_an_unknown_llm_model(monkeypatch):
    """A typo'd or unpriced model must fail at startup, not mid-turn in `estimate_cost`."""
    monkeypatch.setenv("LLM_MODEL", "claude-imaginary-9")

    problems = env_check.find_problems()

    assert any("LLM_MODEL" in problem for problem in problems)


def test_find_problems_reports_a_malformed_seed_anchor_date(monkeypatch):
    monkeypatch.setenv("SEED_ANCHOR_DATE", "not-a-date")

    problems = env_check.find_problems()

    assert any("SEED_ANCHOR_DATE" in problem for problem in problems)


def test_find_problems_reports_test_database_url_equal_to_database_url(monkeypatch):
    monkeypatch.setenv("TEST_DATABASE_URL", Settings().database_url)

    problems = env_check.find_problems()

    assert any("TEST_DATABASE_URL" in problem for problem in problems)


def test_main_prints_every_problem_and_exits_non_zero_on_failure(monkeypatch, capsys):
    monkeypatch.setenv("LOG_LEVEL", "NOT_A_LEVEL")

    exit_code = env_check.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "LOG_LEVEL" in captured.err
