"""Anthropic tool declarations, generated from the same models `policy.py` validates against."""

from typing import Any

from app.application.agent.prompts import TOOL_DESCRIPTIONS
from app.application.policy import visible_tools_for
from app.application.tool_args import TOOL_SCHEMAS


def tool_schemas_for(role: str) -> list[dict[str, Any]]:
    """Anthropic tool declarations for the tools this role may use.

    Sorted by name: an unstable order would change the prompt bytes on every request.
    """
    return [
        {
            "name": tool.value,
            "description": TOOL_DESCRIPTIONS[tool],
            "input_schema": TOOL_SCHEMAS[tool].model_json_schema(),
        }
        for tool in sorted(visible_tools_for(role), key=lambda t: t.value)
    ]
