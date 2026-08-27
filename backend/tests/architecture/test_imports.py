"""AST-based checks on the import graph of application-layer modules."""

import ast
from pathlib import Path

import pytest

_APP_DIR = Path(__file__).resolve().parents[2] / "app"
_PERMISSIONS_PATH = _APP_DIR / "application" / "permissions.py"
_POLICY_PATH = _APP_DIR / "application" / "policy.py"
_PRESENTATION_PATH = _APP_DIR / "application" / "presentation.py"

# Pure type constructors: no config, I/O, or state, so importing one adds no dependency.
_ALLOWED_PERMISSIONS_IMPORTS = frozenset({"types", "enum"})

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

_FORBIDDEN_POLICY_IMPORT_PREFIXES = ("app.infrastructure", "app.api", "app.application.agent")


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
