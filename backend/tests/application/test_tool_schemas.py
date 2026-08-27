from app.application.agent.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from app.application.agent.tool_schemas import tool_schemas_for
from app.application.permissions import Role, ToolName
from app.application.tool_args import TOOL_SCHEMAS
from app.domain.constants import VALID_STATUSES


def test_an_operator_is_never_shown_the_write_tool() -> None:
    """Defence in depth and a shorter prompt from the same line."""
    names = {schema["name"] for schema in tool_schemas_for(Role.OPERATOR)}
    assert ToolName.UPDATE_ORDER_STATUS.value not in names
    assert ToolName.GET_SALES_ORDERS.value in names


def test_a_supervisor_is_shown_every_tool() -> None:
    names = {schema["name"] for schema in tool_schemas_for(Role.SUPERVISOR)}
    assert names == {tool.value for tool in ToolName}


def test_an_unknown_role_is_shown_nothing() -> None:
    assert tool_schemas_for("admin") == []


def test_every_declared_tool_has_a_validated_counterpart() -> None:
    """The model may only be told about tools the policy can validate."""
    declared = {schema["name"] for schema in tool_schemas_for(Role.SUPERVISOR)}
    assert declared == {tool.value for tool in TOOL_SCHEMAS}


def test_input_schemas_are_generated_not_written_by_hand() -> None:
    """Drift between declared and validated arguments is invisible at runtime."""
    for schema in tool_schemas_for(Role.SUPERVISOR):
        model = TOOL_SCHEMAS[ToolName(schema["name"])]
        assert schema["input_schema"] == model.model_json_schema()


def test_the_status_enum_reaches_the_model_from_a_single_source() -> None:
    update = next(
        s
        for s in tool_schemas_for(Role.SUPERVISOR)
        if s["name"] == ToolName.UPDATE_ORDER_STATUS.value
    )
    rendered = str(update["input_schema"])
    for status in VALID_STATUSES:
        assert status in rendered


def test_every_tool_description_says_when_not_to_use_it() -> None:
    """The model picks tools by reading these; a description with only the "does" invites misuse."""
    for schema in tool_schemas_for(Role.SUPERVISOR):
        assert len(schema["description"]) > 80


def test_the_system_prompt_carries_the_role_and_the_date() -> None:
    rendered = SYSTEM_PROMPT.format(role="operator", today="2026-06-15")
    assert "operator" in rendered
    assert "2026-06-15" in rendered


def test_the_prompt_version_is_a_plain_string() -> None:
    assert isinstance(PROMPT_VERSION, str)
    assert PROMPT_VERSION
