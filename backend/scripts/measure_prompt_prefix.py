"""Measures the cacheable prompt prefix — system prompt plus declared tool schemas — against
the configured model's minimum cacheable length (docs/SPEC-2.md §5.2, docs/adr/0011).

Character-based, so it reports a band and a verdict, never a token count it cannot know.
"""

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum

from app.application.agent.prompts import SYSTEM_PROMPT
from app.application.agent.tool_schemas import tool_schemas_for
from app.application.constants import Model
from app.application.permissions import Role
from app.config import settings
from scripts.measure_prompt_prefix_constants import CHARS_PER_TOKEN_BAND, MIN_CACHEABLE_TOKENS


class Verdict(str, Enum):
    """INCONCLUSIVE is the honest third answer when the estimate band crosses the floor."""

    CACHEABLE = "cacheable"
    BELOW_FLOOR = "below_floor"
    INCONCLUSIVE = "inconclusive"


def token_band(chars: int) -> tuple[int, int]:
    """Fewest and most tokens the prefix could occupy, over the whole chars-per-token band."""
    densest, sparsest = CHARS_PER_TOKEN_BAND
    return math.ceil(chars / sparsest), math.ceil(chars / densest)


def verdict_for(chars: int, threshold_tokens: int) -> Verdict:
    """Concludes only where the whole band agrees; a straddling band has no answer to give."""
    fewest, most = token_band(chars)
    if most < threshold_tokens:
        return Verdict.BELOW_FLOOR
    if fewest >= threshold_tokens:
        return Verdict.CACHEABLE
    return Verdict.INCONCLUSIVE


def chars_per_token_at_floor(chars: int, threshold_tokens: int) -> float:
    """The chars-per-token rate at which this prefix would exactly reach the floor."""
    return chars / threshold_tokens


@dataclass(frozen=True)
class PrefixMeasurement:
    role: Role
    model: Model
    tool_count: int
    system_chars: int
    tools_chars: int

    @property
    def total_chars(self) -> int:
        return self.system_chars + self.tools_chars

    @property
    def threshold_tokens(self) -> int:
        return MIN_CACHEABLE_TOKENS[self.model]

    @property
    def verdict(self) -> Verdict:
        return verdict_for(self.total_chars, self.threshold_tokens)


def measure_prefix(role: Role, model: Model) -> PrefixMeasurement:
    """Composes the prefix `run_turn` sends on every turn: formatted system prompt + tools."""
    system = SYSTEM_PROMPT.format(role=role.value, today=date.today().isoformat())
    schemas = tool_schemas_for(role.value)
    return PrefixMeasurement(
        role=role,
        model=model,
        tool_count=len(schemas),
        system_chars=len(system),
        tools_chars=len(json.dumps(schemas, ensure_ascii=False)),
    )


def render_report(model: Model, measurements: Sequence[PrefixMeasurement]) -> str:
    densest, sparsest = CHARS_PER_TOKEN_BAND
    threshold = MIN_CACHEABLE_TOKENS[model]
    header = (
        f"{'role':<11}{'tools':>6}{'system':>8}{'schemas':>9}{'total':>7}"
        f"{'est. tokens':>14}{'floor at':>10}  verdict"
    )
    lines = [
        "Cacheable prompt prefix = system prompt + the tool schemas declared to the model.",
        f"Model {model.value}: minimum cacheable prefix {threshold} tokens (docs/SPEC-2.md 5.2).",
        f"Tokens estimated at {densest}-{sparsest} chars/token: the tokenizer is not public.",
        "",
        header,
        "-" * len(header),
    ]
    for measurement in measurements:
        fewest, most = token_band(measurement.total_chars)
        rate = chars_per_token_at_floor(measurement.total_chars, measurement.threshold_tokens)
        lines.append(
            f"{measurement.role.value:<11}{measurement.tool_count:>6}"
            f"{measurement.system_chars:>8}{measurement.tools_chars:>9}"
            f"{measurement.total_chars:>7}{f'{fewest}-{most}':>14}{rate:>10.3f}"
            f"  {measurement.verdict.value}"
        )
    lines += [
        "",
        "'floor at' is the chars/token rate at which a prefix would exactly reach the "
        f"{threshold}-token floor.",
        f"Outside the {densest}-{sparsest} band, the verdict does not depend on the tokenizer.",
        "",
        "cache_control is not enabled: see docs/adr/0011-no-prompt-caching.md.",
    ]
    return "\n".join(lines)


def main() -> None:
    model = settings.llm_model
    print(render_report(model, [measure_prefix(role, model) for role in Role]))


if __name__ == "__main__":
    main()
