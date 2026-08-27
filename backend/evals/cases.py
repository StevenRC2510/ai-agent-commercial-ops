"""The case file's closed schema and its loader. Data in, validated cases out."""

from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.application.permissions import Role, ToolName
from evals.cases_constants import REQUIRED_FIELDS, AssertionKind, Category


class CaseFileError(ValueError):
    """The case file is unusable. Never recovered from: a silent skip would fake a pass."""


class Assertion(BaseModel):
    """One observable claim about a turn. `extra="forbid"` so a typo is never ignored."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: AssertionKind
    tool: ToolName | None = None
    argument: str | None = None
    value: str | int | None = None
    order_id: int | None = Field(default=None, gt=0)
    client_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_the_fields_this_kind_needs(self) -> "Assertion":
        missing = [name for name in REQUIRED_FIELDS[self.kind] if getattr(self, name) is None]
        if missing:
            raise ValueError(f"{self.kind.value} requires {missing}")
        return self


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    category: Category
    role: Role
    message: str = Field(min_length=1)
    rationale: str = ""
    asserts: tuple[Assertion, ...] = Field(min_length=1)

    def order_ids(self) -> tuple[int, ...]:
        """Orders whose status the run has to snapshot before the model can touch them."""
        return tuple(sorted({a.order_id for a in self.asserts if a.order_id is not None}))

    def client_ids(self) -> tuple[int, ...]:
        """Clients whose real balance a grounding assertion will be checked against."""
        return tuple(sorted({a.client_id for a in self.asserts if a.client_id is not None}))


def load_cases(path: Path) -> tuple[EvalCase, ...]:
    """Read and validate the case file. Every failure is loud and names the case."""
    try:
        document: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CaseFileError(f"{path}: could not be read as YAML — {exc}") from exc

    if not isinstance(document, dict) or not isinstance(document.get("cases"), list):
        raise CaseFileError(f"{path}: expected a top-level 'cases:' list")

    cases = []
    for index, entry in enumerate(document["cases"], start=1):
        if not isinstance(entry, dict):
            raise CaseFileError(f"{path}: case #{index} is not a mapping")
        try:
            cases.append(EvalCase(**entry))
        except ValidationError as exc:
            raise CaseFileError(f"{path}: case #{index} is invalid — {exc}") from exc

    duplicates = sorted(name for name, count in Counter(c.id for c in cases).items() if count > 1)
    if duplicates:
        raise CaseFileError(f"{path}: duplicate case ids {duplicates}")
    if not cases:
        raise CaseFileError(f"{path}: holds no cases")
    return tuple(cases)
