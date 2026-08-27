"""Validates the environment before the app or its tests run.

Every check derives from app.config.Settings; run via `python -m app.infrastructure.env_check`.
"""

import sys

from pydantic import ValidationError


def _pydantic_problems(exc: ValidationError) -> list[str]:
    """One "VARIABLE: what is wrong" line per error pydantic collected."""
    lines = []
    for error in exc.errors():
        variable = str(error["loc"][0]).upper() if error["loc"] else "settings"
        # Pydantic prefixes every raised ValueError with "Value error, "; drop it, it's noise here.
        message = str(error["msg"]).removeprefix("Value error, ")
        lines.append(f"{variable}: {message}")
    return lines


def find_problems() -> list[str]:
    """Return every configuration problem found; an empty list means it is valid.

    Imports Settings inside the try so a broken environment raises here, not at module import time.
    """
    try:
        from app.config import Settings

        settings = Settings()
    except ValidationError as exc:
        return _pydantic_problems(exc)

    problems = []
    if settings.test_database_url == settings.database_url:
        problems.append(
            "TEST_DATABASE_URL: must point at a different database than DATABASE_URL — "
            "the test suite deletes every row in it before running, and would wipe your "
            "application data if the two were the same"
        )
    return problems


def main() -> int:
    """Print every problem and return a non-zero exit code, or confirm success."""
    problems = find_problems()
    if problems:
        print("Environment validation failed:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("Environment OK — all required variables are present and valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
