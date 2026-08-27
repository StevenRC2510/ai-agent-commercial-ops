"""The gate in front of every eval run. Never imports `app.config` at module level.

DEMO_MODE=false with no key makes `app.config` raise on import, so loading settings is
the thing being guarded, not something the guard can assume already happened.
"""

from collections.abc import Callable
from typing import Protocol

from pydantic import ValidationError

from app.application.constants import Model
from evals.preflight_constants import (
    BLOCKED_FOOTER,
    BLOCKED_HEADER,
    CONFIG_UNAVAILABLE,
    DEMO_MODE_ACTIVE,
    KEY_MISSING,
)


class EvalBlockedError(RuntimeError):
    """This environment cannot produce a real measurement. Raised instead of guessing."""


class EvalSettings(Protocol):
    """The slice of `Settings` the suite reads. Lets a test substitute one without a .env."""

    demo_mode: bool
    anthropic_api_key: str
    llm_model: Model
    llm_temperature: float
    llm_timeout_seconds: int
    llm_max_tokens: int
    pending_action_ttl_seconds: int


SettingsLoader = Callable[[], EvalSettings]


def load_settings() -> EvalSettings:
    from app.config import settings

    return settings


def _safe_error_summary(exc: ValidationError) -> str:
    """Field and error type only: a Settings error quotes its input, and inputs are secrets."""
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or 'settings'}: {error['type']}"
        for error in exc.errors()
    )


def blocking_problems(loader: SettingsLoader = load_settings) -> tuple[str, ...]:
    """Every reason this environment cannot produce a real measurement, at once."""
    try:
        settings = loader()
    except ValidationError as exc:
        return (CONFIG_UNAVAILABLE.format(errors=_safe_error_summary(exc)),)

    problems = []
    if settings.demo_mode:
        problems.append(DEMO_MODE_ACTIVE)
    if not settings.anthropic_api_key:
        problems.append(KEY_MISSING)
    return tuple(problems)


def render_blocked(problems: tuple[str, ...]) -> str:
    reasons = "\n".join(f"  - {problem}" for problem in problems)
    return f"{BLOCKED_HEADER}\n{reasons}\n\n{BLOCKED_FOOTER}"
