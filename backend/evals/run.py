"""`python -m evals.run` — the entry point behind `make eval`.

Runs the cases against the real Anthropic API. It never falls back to a fake client:
scoring DemoClient or ScriptedClient would measure our own code and call it a model
result. When it cannot run, it says why and produces nothing.
"""

import argparse
import sys
from datetime import UTC, datetime
from enum import IntEnum

from app.application.agent.prompts import PROMPT_VERSION
from app.application.constants import Model
from evals.cases import CaseFileError, load_cases
from evals.cases_constants import CASES_PATH
from evals.preflight import (
    EvalBlockedError,
    EvalSettings,
    SettingsLoader,
    blocking_problems,
    load_settings,
    render_blocked,
)
from evals.report import render_report
from evals.scoring import CaseRun

PROGRESS = "[{index}/{total}] {case_id}"


class ExitCode(IntEnum):
    OK = 0
    FAILURES = 1
    BLOCKED = 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="evals.run", description=__doc__)
    parser.add_argument(
        "--model",
        choices=[model.value for model in Model],
        default=None,
        help="override LLM_MODEL for this run; must be a model estimate_cost can price",
    )
    return parser.parse_args(argv)


def _execute(model: Model, settings: EvalSettings) -> tuple[CaseRun, ...]:
    """Run every case against the real API, reporting progress on stderr."""
    # Imported here: these modules read app.config, which is what the gate above protects.
    from app.infrastructure.db import SessionLocal
    from app.infrastructure.llm.anthropic import AnthropicClient
    from app.infrastructure.obs import new_trace_id
    from app.infrastructure.pending.memory import InMemoryPendingActionStore
    from evals.runner import check_preconditions, run_case

    cases = load_cases(CASES_PATH)
    client = AnthropicClient(
        api_key=settings.anthropic_api_key,
        model=model.value,
        temperature=settings.llm_temperature,
        timeout_seconds=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_tokens,
    )
    store = InMemoryPendingActionStore(
        ttl_seconds=settings.pending_action_ttl_seconds, clock=lambda: datetime.now(UTC)
    )
    runs = []
    with SessionLocal() as db:
        check_preconditions(db)
        for index, case in enumerate(cases, start=1):
            print(
                PROGRESS.format(index=index, total=len(cases), case_id=case.id),
                file=sys.stderr,
                flush=True,
            )
            runs.append(
                run_case(case, db=db, llm=client, pending_store=store, trace_id=new_trace_id())
            )
    return tuple(runs)


def main(argv: list[str] | None = None, *, settings_loader: SettingsLoader = load_settings) -> int:
    args = parse_args(argv)
    problems = blocking_problems(settings_loader)
    if problems:
        print(render_blocked(problems), file=sys.stderr)
        return ExitCode.BLOCKED

    settings = settings_loader()
    model = Model(args.model) if args.model else settings.llm_model
    try:
        runs = _execute(model, settings)
    except (CaseFileError, EvalBlockedError) as exc:
        print(f"make eval cannot run: {exc}", file=sys.stderr)
        return ExitCode.BLOCKED

    print(
        render_report(
            runs,
            model=model,
            prompt_version=PROMPT_VERSION,
            temperature=settings.llm_temperature,
            generated_at=datetime.now(UTC),
        )
    )
    return ExitCode.OK if all(run.outcome.passed for run in runs) else ExitCode.FAILURES


if __name__ == "__main__":
    raise SystemExit(main())
