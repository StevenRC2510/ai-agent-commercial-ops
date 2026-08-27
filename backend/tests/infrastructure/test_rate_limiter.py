"""In-memory fixed-window rate limiter: the budget, the reset, and per-key isolation."""

from datetime import UTC, datetime, timedelta

import pytest

from app.infrastructure.ratelimit.memory import InMemoryRateLimiter

_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
_WINDOW_SECONDS = 60
_BUDGET = 3


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(_NOW)


@pytest.fixture
def limiter(clock: FakeClock) -> InMemoryRateLimiter:
    return InMemoryRateLimiter(max_requests=_BUDGET, window_seconds=_WINDOW_SECONDS, clock=clock)


def test_every_request_inside_the_budget_is_allowed(limiter):
    assert [limiter.allow("u-1") for _ in range(_BUDGET)] == [True] * _BUDGET


def test_the_request_after_the_budget_is_refused(limiter):
    for _ in range(_BUDGET):
        limiter.allow("u-1")
    assert limiter.allow("u-1") is False


def test_the_budget_returns_once_the_window_has_elapsed(limiter, clock):
    for _ in range(_BUDGET + 1):
        limiter.allow("u-1")
    clock.now = _NOW + timedelta(seconds=_WINDOW_SECONDS)
    assert limiter.allow("u-1") is True


def test_the_budget_does_not_return_while_the_window_is_still_open(limiter, clock):
    for _ in range(_BUDGET + 1):
        limiter.allow("u-1")
    clock.now = _NOW + timedelta(seconds=_WINDOW_SECONDS - 1)
    assert limiter.allow("u-1") is False


def test_a_refused_request_does_not_push_the_window_forward(limiter, clock):
    """The window is anchored to the first request, so hammering cannot extend the lockout."""
    for _ in range(_BUDGET):
        limiter.allow("u-1")
    clock.now = _NOW + timedelta(seconds=_WINDOW_SECONDS - 1)
    assert limiter.allow("u-1") is False
    clock.now = _NOW + timedelta(seconds=_WINDOW_SECONDS)
    assert limiter.allow("u-1") is True


def test_two_keys_spend_independent_budgets(limiter):
    for _ in range(_BUDGET + 1):
        limiter.allow("u-1")
    assert [limiter.allow("u-2") for _ in range(_BUDGET)] == [True] * _BUDGET


def test_a_key_whose_window_elapsed_is_forgotten(limiter, clock):
    """Bounds memory to the callers active in one window, not to every caller ever seen."""
    limiter.allow("u-1")
    clock.now = _NOW + timedelta(seconds=_WINDOW_SECONDS)
    limiter.allow("u-2")
    assert limiter.tracked_keys() == 1
