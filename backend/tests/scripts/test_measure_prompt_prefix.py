import json
from datetime import date

import pytest

from app.application.agent.prompts import SYSTEM_PROMPT
from app.application.agent.tool_schemas import tool_schemas_for
from app.application.constants import Model
from app.application.permissions import Role
from scripts.measure_prompt_prefix import (
    Verdict,
    chars_per_token_at_floor,
    measure_prefix,
    render_report,
    verdict_for,
)
from scripts.measure_prompt_prefix_constants import MIN_CACHEABLE_TOKENS


def test_a_prefix_under_the_floor_at_every_ratio_is_below_the_floor():
    """400 chars cannot reach 512 tokens under any plausible tokenization."""
    assert verdict_for(400, 512) is Verdict.BELOW_FLOOR


def test_a_prefix_over_the_floor_at_every_ratio_is_cacheable():
    assert verdict_for(4000, 512) is Verdict.CACHEABLE


def test_a_band_that_straddles_the_floor_refuses_to_conclude():
    """1200 chars falls either side of 400 tokens depending on the rate, so there is no answer."""
    assert verdict_for(1200, 400) is Verdict.INCONCLUSIVE


def test_reaching_the_floor_exactly_counts_as_cacheable():
    assert verdict_for(2048, 512) is Verdict.CACHEABLE


def test_the_configured_model_cannot_cache_this_prefix():
    """The measurement behind ADR 0011: haiku's floor is far above the real prefix."""
    assert measure_prefix(Role.SUPERVISOR, Model.HAIKU_4_5).verdict is Verdict.BELOW_FLOOR


def test_the_same_prefix_would_cache_on_opus_5():
    """What would change the answer: the model, with the prompt untouched."""
    assert measure_prefix(Role.SUPERVISOR, Model.OPUS_5).verdict is Verdict.CACHEABLE


def test_the_verdict_survives_the_widest_error_bar():
    """It would take roughly one token per character to flip this — no tokenizer is that dense."""
    measurement = measure_prefix(Role.SUPERVISOR, Model.HAIKU_4_5)
    assert chars_per_token_at_floor(measurement.total_chars, measurement.threshold_tokens) < 1.0


def test_the_operator_prefix_is_shorter_because_it_declares_fewer_tools():
    operator = measure_prefix(Role.OPERATOR, Model.HAIKU_4_5)
    supervisor = measure_prefix(Role.SUPERVISOR, Model.HAIKU_4_5)
    assert operator.tool_count < supervisor.tool_count
    assert operator.total_chars < supervisor.total_chars


def test_the_measurement_is_the_prefix_the_orchestrator_actually_sends():
    """Measuring anything other than the real prefix would be worse than not measuring."""
    measurement = measure_prefix(Role.SUPERVISOR, Model.HAIKU_4_5)
    sent_system = SYSTEM_PROMPT.format(role=Role.SUPERVISOR.value, today=date.today().isoformat())
    sent_tools = tool_schemas_for(Role.SUPERVISOR.value)
    assert measurement.system_chars == len(sent_system)
    assert measurement.tools_chars == len(json.dumps(sent_tools, ensure_ascii=False))


@pytest.mark.parametrize("model", list(Model))
def test_every_model_the_project_can_run_has_a_cache_floor(model):
    """A model missing from the table would raise mid-report instead of reporting."""
    assert MIN_CACHEABLE_TOKENS[model] > 0


def test_the_report_states_the_model_the_floor_and_a_verdict_per_role():
    measurements = [measure_prefix(role, Model.HAIKU_4_5) for role in Role]
    report = render_report(Model.HAIKU_4_5, measurements)
    assert Model.HAIKU_4_5.value in report
    assert str(MIN_CACHEABLE_TOKENS[Model.HAIKU_4_5]) in report
    for role in Role:
        assert role.value in report
    assert report.count(Verdict.BELOW_FLOOR.value) == len(Role)
