"""REPORT — what was asserted, what happened, and what the run cost.

Pure: it takes CaseRun objects and returns text. It has no way of producing a number
that no run produced, which is the property that matters when an account is unfunded.
"""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.application.constants import Model
from evals.cases import Assertion
from evals.cases_constants import REFUSAL_CATEGORIES, TOOL_SELECTION_KINDS, Category
from evals.report_constants import ANSWER_EXCERPT_CHARS, NO_RESULTS, PROVENANCE, SEPARATOR, TITLE
from evals.scoring import CaseRun


@dataclass(frozen=True)
class Summary:
    total: int
    passed: int
    by_category: dict[Category, tuple[int, int]]
    tool_selection_passed: int
    tool_selection_total: int
    refusal_passed: int
    refusal_total: int
    median_latency_ms: int
    mean_input_tokens: int
    mean_output_tokens: int
    total_cost_usd: Decimal

    @property
    def pass_rate(self) -> float:
        return _rate(self.passed, self.total)


def _rate(passed: int, total: int) -> float:
    return round(100 * passed / total, 1) if total else 0.0


def _ratio(passed: int, total: int) -> str:
    return f"{passed}/{total}  ({_rate(passed, total):.1f}%)"


def summarise(runs: Sequence[CaseRun]) -> Summary:
    """Every headline number the model comparison table needs, computed in one place."""
    by_category: dict[Category, tuple[int, int]] = {}
    for run in runs:
        won, seen = by_category.get(run.case.category, (0, 0))
        by_category[run.case.category] = (won + int(run.outcome.passed), seen + 1)

    tool_results = [
        result
        for run in runs
        for result in run.outcome.results
        if result.assertion.kind in TOOL_SELECTION_KINDS
    ]
    refusals = [run for run in runs if run.case.category in REFUSAL_CATEGORIES]
    return Summary(
        total=len(runs),
        passed=sum(1 for run in runs if run.outcome.passed),
        by_category=by_category,
        tool_selection_passed=sum(1 for result in tool_results if result.passed),
        tool_selection_total=len(tool_results),
        refusal_passed=sum(1 for run in refusals if run.outcome.passed),
        refusal_total=len(refusals),
        median_latency_ms=int(statistics.median(run.latency_ms for run in runs)) if runs else 0,
        mean_input_tokens=round(statistics.mean(run.input_tokens for run in runs)) if runs else 0,
        mean_output_tokens=round(statistics.mean(run.output_tokens for run in runs)) if runs else 0,
        total_cost_usd=sum((run.cost_usd for run in runs), Decimal(0)),
    )


def _label(assertion: Assertion) -> str:
    """The assertion as a reader can check it against cases.yaml, without the None fields."""
    parts = [
        f"{name}={value}"
        for name, value in (
            ("tool", assertion.tool.value if assertion.tool else None),
            ("argument", assertion.argument),
            ("value", assertion.value),
            ("order_id", assertion.order_id),
            ("client_id", assertion.client_id),
        )
        if value is not None
    ]
    return f"{assertion.kind.value}({', '.join(parts)})" if parts else assertion.kind.value


def _excerpt(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= ANSWER_EXCERPT_CHARS else f"{flat[:ANSWER_EXCERPT_CHARS]}…"


def _call_lines(run: CaseRun) -> str:
    calls = run.observation.proposed_calls
    if not calls:
        return "proposed: (no tool)"
    rendered = "; ".join(f"{call.tool}({dict(call.arguments)})" for call in calls)
    return f"proposed: {rendered}"


def _case_block(run: CaseRun) -> list[str]:
    case = run.case
    verdict = "PASS" if run.outcome.passed else "FAIL"
    lines = [
        f"[{verdict}] {case.id} ({case.category.value}, {case.role.value})  "
        f"{run.latency_ms} ms  {run.input_tokens}/{run.output_tokens} tok  "
        f"${run.cost_usd:.6f}  trace {run.trace_id}",
        f"  message:  {_excerpt(case.message)}",
        f"  {_call_lines(run)}",
        f"  turn:     type={run.observation.result_type} "
        f"reason_code={run.observation.reason_code} denials={dict(run.observation.denials)}",
        f"  answer:   {_excerpt(run.observation.answer)}",
    ]
    if run.error:
        lines.append(f"  error:    {run.error}")
    lines += [
        f"    {'PASS' if result.passed else 'FAIL'} {_label(result.assertion)} — {result.detail}"
        for result in run.outcome.results
    ]
    return lines


def _summary_block(summary: Summary) -> list[str]:
    lines = [
        "SUMMARY",
        f"  overall               {_ratio(summary.passed, summary.total)}  cases",
        f"  tool selection        "
        f"{_ratio(summary.tool_selection_passed, summary.tool_selection_total)}  assertions",
        f"  correct refusal       "
        f"{_ratio(summary.refusal_passed, summary.refusal_total)}  "
        f"cases in {', '.join(sorted(c.value for c in REFUSAL_CATEGORIES))}",
        f"  median latency        {summary.median_latency_ms} ms",
        f"  mean tokens           {summary.mean_input_tokens} in / "
        f"{summary.mean_output_tokens} out",
        f"  total cost            ${summary.total_cost_usd:.6f}",
        "",
        "  by category",
    ]
    lines += [
        f"    {category.value:<20}{_ratio(passed, total)}"
        for category, (passed, total) in sorted(
            summary.by_category.items(), key=lambda item: item[0].value
        )
    ]
    return lines


def render_report(
    runs: Sequence[CaseRun],
    *,
    model: Model,
    prompt_version: str,
    temperature: float,
    generated_at: datetime,
) -> str:
    """The whole report. With no runs it says so and stops, rather than showing zeros."""
    header = [
        TITLE,
        SEPARATOR,
        f"model            {model.value}",
        f"prompt_version   {prompt_version}",
        f"temperature      {temperature}",
        f"generated        {generated_at.isoformat()}",
        f"cases            {len(runs)}",
        SEPARATOR,
        "",
    ]
    if not runs:
        return "\n".join([*header, NO_RESULTS, ""])

    blocks = [line for run in runs for line in [*_case_block(run), ""]]
    return "\n".join(
        [
            *header,
            *_summary_block(summarise(runs)),
            "",
            SEPARATOR,
            "",
            "CASES",
            "",
            *blocks,
            PROVENANCE,
            "",
        ]
    )
