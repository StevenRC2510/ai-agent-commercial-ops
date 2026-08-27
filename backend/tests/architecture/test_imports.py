"""AST-based checks on the import graph of application-layer modules."""

import ast
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_APP_DIR = _BACKEND_DIR / "app"
_PERMISSIONS_PATH = _APP_DIR / "application" / "permissions.py"
_POLICY_PATH = _APP_DIR / "application" / "policy.py"
_PRESENTATION_PATH = _APP_DIR / "application" / "presentation.py"
_TOOLS_PATH = _APP_DIR / "application" / "tools.py"

# Pure type constructors: no config, I/O, or state, so importing one adds no dependency.
_ALLOWED_PERMISSIONS_IMPORTS = frozenset({"types", "enum"})

# SPEC 2's orchestrator home. It does not exist yet; policy and tools must never reach it.
_AGENT_ORCHESTRATOR_PREFIX = "app.application.agent"

_ALLOWED_POLICY_IMPORT_PREFIXES = frozenset(
    {
        "dataclasses",
        "types",
        "typing",
        "pydantic",
        "sqlalchemy",
        "app.application.permissions",
        "app.application.tool_args",
        "app.domain",
    }
)

_FORBIDDEN_POLICY_IMPORT_PREFIXES = ("app.infrastructure", "app.api", _AGENT_ORCHESTRATOR_PREFIX)

_DOMAIN_FORBIDS = frozenset({"app.application", "app.infrastructure", "app.api"})
_APPLICATION_FORBIDS = frozenset({"app.infrastructure", "app.api"})
_INFRASTRUCTURE_FORBIDS = frozenset({"app.api"})

# (layer name, its directory, prefixes it may never import). Adding a layer is a new row.
_LAYER_RULES: tuple[tuple[str, Path, frozenset[str]], ...] = (
    ("domain", _APP_DIR / "domain", _DOMAIN_FORBIDS),
    ("application", _APP_DIR / "application", _APPLICATION_FORBIDS),
    ("infrastructure", _APP_DIR / "infrastructure", _INFRASTRUCTURE_FORBIDS),
    ("api", _APP_DIR / "api", frozenset()),  # outermost adapter: nothing is off-limits
)

# Composition root: wires every layer together, so it is exempt from the layer rule above.
_COMPOSITION_ROOT_FILES = frozenset({"app/config.py", "app/main.py", "app/__main__.py"})

# sqlalchemy is deliberately allowed here — see docs/adr/0005-persistence-aware-domain-models.md.
_FORBIDDEN_CORE_LIBRARY_ROOTS = frozenset(
    {"fastapi", "httpx", "requests", "anthropic", "openai", "uvicorn"}
)
_CORE_LAYER_DIRS = (_APP_DIR / "domain", _APP_DIR / "application")


def _imported_module_names(tree: ast.Module) -> set[str]:
    """Every module name a file imports, covering both plain and relative import forms."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
            elif node.level > 0:
                # `from . import x`: module is None, but each alias names a sibling module.
                names.update(alias.name for alias in node.names)
    return names


def _matches_any_prefix(name: str, prefixes: frozenset[str]) -> bool:
    return any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import os", {"os"}),
        ("import os.path", {"os.path"}),
        ("import os as o", {"os"}),
        ("from os import path", {"os"}),
        ("from os.path import join", {"os.path"}),
        ("from . import agent", {"agent"}),
        ("from .agent import run", {"agent"}),
    ],
)
def test_imported_module_names_handles_every_import_form(source, expected):
    """Pins the helper Task 13 reuses for the whole-backend architecture test."""
    assert _imported_module_names(ast.parse(source)) == expected


def test_permissions_module_is_pure_data() -> None:
    """The authorization table depends on nothing, so nothing can influence it."""
    tree = ast.parse(_PERMISSIONS_PATH.read_text())
    imported_modules = _imported_module_names(tree)
    disallowed = imported_modules - _ALLOWED_PERMISSIONS_IMPORTS
    assert imported_modules <= _ALLOWED_PERMISSIONS_IMPORTS, (
        "permissions.py may only import pure type constructors like `types` and `enum`: "
        "anything else could make the authorization table depend on configuration, "
        f"environment, or another module's state. Found beyond the allowed set: {disallowed}"
    )


def test_policy_module_only_imports_the_whitelist() -> None:
    """The docstring's whitelist is a contract, not a comment: this is what enforces it."""
    imported = _imported_module_names(ast.parse(_POLICY_PATH.read_text()))
    disallowed = {
        name for name in imported if not _matches_any_prefix(name, _ALLOWED_POLICY_IMPORT_PREFIXES)
    }
    assert not disallowed, (
        f"policy.py imported modules outside its whitelist: {disallowed}. The decision layer "
        "must stay independent of infrastructure, the API, and the future agent orchestrator."
    )
    for name in imported:
        assert not name.startswith(_FORBIDDEN_POLICY_IMPORT_PREFIXES), (
            f"policy.py must never import {name}: that would let infrastructure, the API "
            "layer, or the agent orchestrator influence an authorization decision."
        )


def test_presentation_module_never_imports_policy() -> None:
    """Pinned before Task 10 adds render_summary and this module's first real import."""
    imported = _imported_module_names(ast.parse(_PRESENTATION_PATH.read_text()))
    forbidden = {"app.application.policy"}
    assert not any(
        _matches_any_prefix(name, frozenset(forbidden)) for name in imported
    ), f"presentation.py must never import app.application.policy. Found: {imported}"


def test_composition_root_files_are_named_exemptions_not_silent_gaps() -> None:
    """config.py, main.py, and __main__.py wire every layer together and skip the layer
    rule below; naming them here makes that a decision instead of a gap in the walk."""
    top_level_files = {
        f"app/{path.name}" for path in _APP_DIR.glob("*.py") if path.name != "__init__.py"
    }
    assert top_level_files == _COMPOSITION_ROOT_FILES, (
        f"app/ gained a top-level module not accounted for here: "
        f"{top_level_files - _COMPOSITION_ROOT_FILES}. Composition-level files are exempt "
        "from the hexagonal dependency rule, but each exemption must be named deliberately."
    )


def test_the_dependency_rule_holds_for_every_module_in_app() -> None:
    """The hexagonal rule, applied to every file under app/, not four hand-picked ones."""
    for layer_name, layer_dir, forbidden in _LAYER_RULES:
        for path in sorted(layer_dir.rglob("*.py")):
            imported = _imported_module_names(ast.parse(path.read_text()))
            for module in imported:
                assert not _matches_any_prefix(module, forbidden), (
                    f"{path.relative_to(_BACKEND_DIR)} imports {module!r}, which breaks the "
                    f"hexagonal dependency rule: the {layer_name} layer may not depend on "
                    f"{sorted(forbidden)}."
                )


def test_domain_and_application_never_import_framework_or_transport_libraries() -> None:
    """Keeps the core free of FastAPI, HTTP clients, and model SDKs; sqlalchemy is exempt."""
    for layer_dir in _CORE_LAYER_DIRS:
        for path in sorted(layer_dir.rglob("*.py")):
            imported = _imported_module_names(ast.parse(path.read_text()))
            roots = {name.split(".")[0] for name in imported}
            offending = roots & _FORBIDDEN_CORE_LIBRARY_ROOTS
            assert not offending, (
                f"{path.relative_to(_BACKEND_DIR)} imports {sorted(offending)}: the domain "
                "and application layers must stay free of framework and transport libraries."
            )


def test_policy_and_tools_never_import_the_future_agent_orchestrator() -> None:
    """SPEC-1 §16 criterion 8: the orchestrator module doesn't exist yet, and must stay that way."""
    forbidden = frozenset({_AGENT_ORCHESTRATOR_PREFIX})
    for path in (_POLICY_PATH, _TOOLS_PATH):
        imported = _imported_module_names(ast.parse(path.read_text()))
        offending = {m for m in imported if _matches_any_prefix(m, forbidden)}
        assert not offending, (
            f"{path.name} imports {offending}: policy and tools must never depend on the "
            "agent orchestrator — that direction of trust runs the other way."
        )
