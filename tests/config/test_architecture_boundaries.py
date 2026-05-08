"""Architecture boundary checks for the app package layout."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "app"


def _python_files(package_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in package_dir.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _imported_modules(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def _assert_no_forbidden_imports(package: str, forbidden_prefixes: tuple[str, ...]) -> None:
    violations: list[str] = []
    for path in _python_files(APP_ROOT / package):
        for line_no, module_name in _imported_modules(path):
            if module_name.startswith(forbidden_prefixes):
                rel_path = path.relative_to(REPO_ROOT)
                violations.append(f"{rel_path}:{line_no} imports {module_name}")

    assert not violations, "Forbidden architecture imports:\n" + "\n".join(violations)


def test_core_does_not_import_edge_packages() -> None:
    _assert_no_forbidden_imports(
        "core",
        (
            "app.startup",
            "app.infrastructure",
            "app.entrypoints",
        ),
    )


def test_infrastructure_does_not_import_startup_or_entrypoints() -> None:
    _assert_no_forbidden_imports(
        "infrastructure",
        (
            "app.startup",
            "app.entrypoints",
        ),
    )


def test_entrypoints_do_not_import_infrastructure_directly() -> None:
    _assert_no_forbidden_imports(
        "entrypoints",
        ("app.infrastructure",),
    )
