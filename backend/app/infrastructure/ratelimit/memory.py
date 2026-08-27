"""In-memory fixed-window rate limiter, keyed by caller identity.

State lives in this process only: it resets on restart and is not shared across
replicas, so N replicas grant N times the configured budget.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class _Window:
    """One caller's current window: when it opened and how much it has spent."""

    started_at: datetime
    hits: int


class InMemoryRateLimiter:
    """Counts requests per key in fixed windows of a configured width."""

    def __init__(
        self, *, max_requests: int, window_seconds: int, clock: Callable[[], datetime]
    ) -> None:
        self._max_requests = max_requests
        self._window = timedelta(seconds=window_seconds)
        self._clock = clock
        self._windows: dict[str, _Window] = {}

    def allow(self, key: str) -> bool:
        """Charge one request to `key` and answer whether it fitted in the budget."""
        now = self._clock()
        self._drop_elapsed(now)
        window = self._windows.get(key, _Window(started_at=now, hits=0))
        if window.hits >= self._max_requests:
            return False
        self._windows[key] = _Window(window.started_at, window.hits + 1)
        return True

    def tracked_keys(self) -> int:
        """Callers holding an open window right now — the limiter's whole memory footprint."""
        return len(self._windows)

    def _drop_elapsed(self, now: datetime) -> None:
        """Keeps memory proportional to the callers active in one window, not to every caller."""
        elapsed = [key for key, w in self._windows.items() if now - w.started_at >= self._window]
        for key in elapsed:
            del self._windows[key]
