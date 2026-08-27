"""In-memory pending action store: single-use, time-limited, actor-bound consent (ADR 0009)."""

import secrets
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from app.application.pending import PendingAction


class PendingActionError(Exception):
    """Base for every reason a pending action cannot be consumed."""


class PendingNotFoundError(PendingActionError):
    """No pending action exists for this identifier."""


class PendingExpiredError(PendingActionError):
    """The pending action's time-to-live has elapsed."""


class PendingAlreadyUsedError(PendingActionError):
    """The pending action was already consumed once."""


class PendingActorMismatchError(PendingActionError):
    """The consuming actor or role does not match the one the action was proposed for."""


@dataclass(frozen=True)
class _Entry:
    """The store's own record: the action plus the expiry it decided, not the action's."""

    action: PendingAction
    expires_at: datetime


class InMemoryPendingActionStore:
    """Holds pending actions in memory, keyed by an opaque, single-use identifier."""

    def __init__(self, ttl_seconds: int, clock: Callable[[], datetime]) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._pending: dict[str, _Entry] = {}
        self._consumed: set[str] = set()

    def create(self, action: PendingAction) -> str:
        pending_id = secrets.token_urlsafe(16)
        expires_at = self._clock() + timedelta(seconds=self._ttl_seconds)
        self._pending[pending_id] = _Entry(replace(action, pending_id=pending_id), expires_at)
        return pending_id

    def consume(self, pending_id: str, *, actor: str, role: str) -> PendingAction:
        if pending_id in self._consumed:
            raise PendingAlreadyUsedError(pending_id)
        entry = self._pending.get(pending_id)
        if entry is None:
            raise PendingNotFoundError(pending_id)
        if self._clock() >= entry.expires_at:
            raise PendingExpiredError(pending_id)
        if entry.action.actor != actor or entry.action.role != role:
            raise PendingActorMismatchError(pending_id)
        del self._pending[pending_id]
        self._consumed.add(pending_id)
        return entry.action
