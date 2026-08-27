"""AST-based checks on the import graph of application-layer modules."""

import ast
import re
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

_CONSTANTS_PATH = _APP_DIR / "application" / "constants.py"
_ALLOWED_CONSTANTS_IMPORTS = frozenset({"collections.abc", "decimal", "enum"})

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

_CONSTANT_NAME = re.compile(r"^_*[A-Z][A-Z0-9_]*$")
_MAPPING_GENERICS = frozenset({"Mapping", "MutableMapping", "dict", "Dict"})

# (relative path, constant name): a genuine exception, not a silent hole. Its keys are
# logging.config.dictConfig's schema, a stdlib vocabulary we do not define or enumerate.
_MAPPING_KEY_EXEMPTIONS = frozenset({("app/infrastructure/obs.py", "LOGGING_CONFIG")})

# A constant longer than this is a data table, not a knob, and belongs in a constants module.
_MAX_CONSTANT_LINES = 5

# (relative path, constant name): constants that cannot leave their module because the value
# references a class defined beside it — extracting either one would be a circular import.
_CONSTANT_EXTRACTION_EXEMPTIONS = frozenset(
    {
        ("app/application/tool_args.py", "TOOL_SCHEMAS"),
        ("app/infrastructure/obs.py", "LOGGING_CONFIG"),
    }
)


def _generic_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _mapping_key_violations(tree: ast.Module, relative_path: str) -> list[str]:
    """Module-level `NAME: Mapping[str, ...] = ...`-shaped constants, str-keyed ones only."""
    violations = []
    for node in tree.body:
        if not (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)):
            continue
        name = node.target.id
        if not _CONSTANT_NAME.match(name):
            continue
        annotation = node.annotation
        if not isinstance(annotation, ast.Subscript):
            continue
        if _generic_name(annotation.value) not in _MAPPING_GENERICS:
            continue
        key_type = (
            annotation.slice.elts[0]
            if isinstance(annotation.slice, ast.Tuple) and annotation.slice.elts
            else None
        )
        if (relative_path, name) in _MAPPING_KEY_EXEMPTIONS:
            continue
        if isinstance(key_type, ast.Name) and key_type.id == "str":
            violations.append(
                f"{relative_path}: {name} is keyed by 'str'. Mapping constants must be "
                "keyed by an Enum so an invalid key fails at import or validation time, "
                "not at lookup."
            )
    return violations


def test_mapping_constants_are_keyed_by_enum() -> None:
    """A str-keyed constant table lets a typo fail silently at lookup instead of loudly."""
    violations = []
    for path in sorted(_APP_DIR.rglob("*.py")):
        relative_path = str(path.relative_to(_BACKEND_DIR))
        violations.extend(_mapping_key_violations(ast.parse(path.read_text()), relative_path))
    assert not violations, "\n".join(violations)


def test_mapping_key_exemptions_are_not_silent_holes() -> None:
    """Every exemption must still exist and still be str-keyed, or it is dead configuration."""
    for relative_path, name in _MAPPING_KEY_EXEMPTIONS:
        path = _BACKEND_DIR / relative_path
        tree = ast.parse(path.read_text())
        found = any(
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            for node in tree.body
        )
        assert found, (
            f"{relative_path}: exempted constant {name!r} no longer exists — "
            "remove the exemption or restore the constant."
        )


def _module_level_constants(tree: ast.Module) -> list[tuple[str, int]]:
    """Every module-level constant-style assignment, as (name, lines it spans)."""
    constants: list[tuple[str, int]] = []
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target]
        elif isinstance(node, ast.Assign):
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
        else:
            continue
        span = (node.end_lineno or node.lineno) - node.lineno + 1
        constants.extend((t.id, span) for t in targets if _CONSTANT_NAME.match(t.id))
    return constants


def _is_constants_module(path: Path, tree: ast.Module) -> bool:
    """A named constants module, or one holding only data: it has no logic to protect."""
    if path.stem == "constants" or path.stem.endswith("_constants"):
        return True
    return not any(isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) for n in ast.walk(tree))


def _constant_extraction_violation(path: Path, relative_path: str) -> str | None:
    tree = ast.parse(path.read_text())
    if _is_constants_module(path, tree):
        return None
    found = [
        (name, span)
        for name, span in _module_level_constants(tree)
        if (relative_path, name) not in _CONSTANT_EXTRACTION_EXEMPTIONS
    ]
    oversized = [name for name, span in found if span > _MAX_CONSTANT_LINES]
    if len(found) < 2 and not oversized:
        return None
    names = sorted(name for name, _ in found)
    reason = (
        f"holds {len(found)} module-level constants {names}"
        if len(found) >= 2
        else f"holds one module-level constant {names[0]!r} spanning more than "
        f"{_MAX_CONSTANT_LINES} lines"
    )
    return (
        f"{relative_path}: {reason}. Extract to a sibling {path.stem}_constants.py so the "
        "logic module reads as logic and the constants are looked up in a named place."
    )


def test_modules_with_several_constants_keep_them_in_a_constants_file() -> None:
    """Two constants, or one data table, turn a logic module into a place to scroll past."""
    violations = []
    for path in sorted(_APP_DIR.rglob("*.py")):
        violation = _constant_extraction_violation(path, str(path.relative_to(_BACKEND_DIR)))
        if violation:
            violations.append(violation)
    assert not violations, "\n".join(violations)


def test_constant_extraction_exemptions_are_not_silent_holes() -> None:
    """Every exemption must still name a real constant, or it is dead configuration."""
    for relative_path, name in _CONSTANT_EXTRACTION_EXEMPTIONS:
        path = _BACKEND_DIR / relative_path
        found = {constant for constant, _ in _module_level_constants(ast.parse(path.read_text()))}
        assert name in found, (
            f"{relative_path}: exempted constant {name!r} no longer exists — "
            "remove the exemption or restore the constant."
        )


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


def test_constants_module_is_pure_data() -> None:
    """The price table depends on nothing, so no environment can move a price."""
    imported_modules = _imported_module_names(ast.parse(_CONSTANTS_PATH.read_text()))
    disallowed = imported_modules - _ALLOWED_CONSTANTS_IMPORTS
    assert imported_modules <= _ALLOWED_CONSTANTS_IMPORTS, (
        "constants.py may only import pure type constructors like `enum` and `decimal`: "
        "anything else could make the price table depend on configuration, environment, "
        f"or another module's state. Found beyond the allowed set: {disallowed}"
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
