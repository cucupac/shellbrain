"""Shared static architecture-test helpers."""

from __future__ import annotations

import ast
import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


IGNORED_PATH_PARTS = {
    ".git",
    ".local",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
}


@dataclass(frozen=True)
class ImportReference:
    """One import statement resolved to its imported module prefix."""

    path: Path
    line_no: int
    module_name: str


@dataclass(frozen=True)
class EffectImportRule:
    """Static rule for keeping an effect import inside its owner modules."""

    name: str
    forbidden_prefixes: tuple[str, ...]
    allowed_module_prefixes: tuple[str, ...]


def python_files(root: Path) -> list[Path]:
    """Return Python source files below root, excluding caches and local envs."""

    if root.is_file():
        return [root] if root.suffix == ".py" and not is_ignored_path(root) else []
    return sorted(
        path
        for path in root.rglob("*.py")
        if path.is_file() and not is_ignored_path(path)
    )


def production_python_files(
    repo_root: Path, package_roots: Iterable[str]
) -> list[Path]:
    """Return Python files for production package roots only."""

    files: list[Path] = []
    for package_root in package_roots:
        files.extend(python_files(repo_root / package_root))
    return sorted(set(files))


def is_ignored_path(path: Path) -> bool:
    return any(part in IGNORED_PATH_PARTS for part in path.parts)


def imported_modules(path: Path) -> list[tuple[int, str]]:
    """Return module prefixes imported by a Python source file."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def iter_import_references(paths: Iterable[Path]) -> list[ImportReference]:
    references: list[ImportReference] = []
    for path in paths:
        references.extend(
            ImportReference(path=path, line_no=line_no, module_name=module_name)
            for line_no, module_name in imported_modules(path)
        )
    return references


def module_name_for_path(path: Path, repo_root: Path) -> str:
    """Return the dotted module name for a Python file below the repo root."""

    rel_path = path.relative_to(repo_root).with_suffix("")
    parts = rel_path.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def module_matches_prefix(module_name: str, prefixes: tuple[str, ...]) -> bool:
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in prefixes
    )


def forbidden_import_violations(
    paths: Iterable[Path],
    forbidden_prefixes: tuple[str, ...],
    *,
    repo_root: Path,
) -> list[str]:
    violations: list[str] = []
    for ref in iter_import_references(paths):
        if module_matches_prefix(ref.module_name, forbidden_prefixes):
            violations.append(
                f"{ref.path.relative_to(repo_root)}:{ref.line_no} imports {ref.module_name}"
            )
    return violations


def effect_import_violations(
    paths: Iterable[Path],
    rules: Iterable[EffectImportRule],
    *,
    repo_root: Path,
) -> list[str]:
    violations: list[str] = []
    for ref in iter_import_references(paths):
        source_module = module_name_for_path(ref.path, repo_root)
        for rule in rules:
            if not module_matches_prefix(ref.module_name, rule.forbidden_prefixes):
                continue
            if module_matches_prefix(source_module, rule.allowed_module_prefixes):
                continue
            violations.append(
                f"{ref.path.relative_to(repo_root)}:{ref.line_no} imports "
                f"{ref.module_name} outside {rule.name} owners"
            )
    return violations


def pyproject_package_roots(pyproject_path: Path) -> set[str]:
    """Return top-level setuptools package roots declared in pyproject.toml."""

    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    include_patterns = (
        data.get("tool", {})
        .get("setuptools", {})
        .get("packages", {})
        .get("find", {})
        .get("include", [])
    )
    roots: set[str] = set()
    for pattern in include_patterns:
        root = pattern.split("*", 1)[0].rstrip(".")
        if root:
            roots.add(root.split(".", 1)[0])
    return roots


def pyproject_dependency_names(pyproject_path: Path) -> set[str]:
    """Return normalized project dependency names from pyproject.toml."""

    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    dependencies = data.get("project", {}).get("dependencies", [])
    return {_normalize_dependency_name(dependency) for dependency in dependencies}


def direct_package_dirs(package_root: Path) -> set[str]:
    """Return direct child package directory names under a package root."""

    return {
        path.name
        for path in package_root.iterdir()
        if path.is_dir() and not is_ignored_path(path)
    }


def text_occurrence_violations(
    paths: Iterable[Path],
    needles: tuple[str, ...],
    *,
    repo_root: Path,
) -> list[str]:
    violations: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in needles:
            if needle in text:
                violations.append(f"{path.relative_to(repo_root)} contains {needle!r}")
    return violations


def _normalize_dependency_name(dependency: str) -> str:
    raw_name = re.split(r"[<>=!~;\\[]", dependency, maxsplit=1)[0]
    return raw_name.strip().lower().replace("_", "-")
