"""Pytest plugin that writes a markdown visualization report for categorized tests."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


OPERATIONS_ROOT = Path("tests/operations")
SUBCATEGORY_ORDER = ("validation", "execution")

ARTIFACT_PATH = Path("tests/visualization/artifacts/tests_status.md")

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_NOT_RUN = "not_run"


@dataclass
class DiscoveredTest:
    """Metadata describing a discovered test function and its one-line description."""

    key: str
    category: str
    function_name: str
    description: str
    file_path: str


class VisualizationReportPlugin:
    """Collect pytest outcomes and write a markdown visualization report."""

    def __init__(self, root_path: Path) -> None:
        self._root_path = root_path
        self._categories = self._discover_categories()
        self._discovered = self._discover_tests()
        self._nodeid_to_key: dict[str, str] = {}
        self._status_by_key: dict[str, str] = {}

    @property
    def discovered(self) -> list[DiscoveredTest]:
        """Return all discovered categorized tests in stable order."""

        return self._discovered

    def pytest_collection_modifyitems(self, items: list[Any]) -> None:
        """Map collected pytest node IDs to canonical key format."""

        for item in items:
            node_key = _build_key_from_item(item, self._root_path)
            if node_key:
                self._nodeid_to_key[item.nodeid] = node_key

    def pytest_runtest_logreport(self, report: Any) -> None:
        """Capture test outcomes from pytest reports."""

        key = self._nodeid_to_key.get(report.nodeid)
        if key is None:
            return

        if report.when == "setup":
            if report.failed:
                self._set_status(key, STATUS_FAILED)
            elif report.skipped:
                self._set_status(key, STATUS_SKIPPED)
            return

        if report.when != "call":
            return

        if getattr(report, "wasxfail", False):
            self._set_status(key, STATUS_SKIPPED)
            return

        if report.failed:
            self._set_status(key, STATUS_FAILED)
        elif report.passed:
            self._set_status(key, STATUS_PASSED)
        elif report.skipped:
            self._set_status(key, STATUS_SKIPPED)

    def pytest_sessionfinish(self, session: Any, exitstatus: int) -> None:
        """Write report at end of session regardless of test outcomes."""

        _ = (session, exitstatus)
        ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(self._render_markdown(), encoding="utf-8")

    def _set_status(self, key: str, new_status: str) -> None:
        """Apply precedence rules while updating a test status."""

        current = self._status_by_key.get(key)
        if current == STATUS_FAILED:
            return
        if new_status == STATUS_FAILED:
            self._status_by_key[key] = STATUS_FAILED
            return
        if current == STATUS_PASSED and new_status == STATUS_SKIPPED:
            return
        self._status_by_key[key] = new_status

    def _discover_tests(self) -> list[DiscoveredTest]:
        """Discover categorized test functions and first-line docstrings from source files."""

        discovered: list[DiscoveredTest] = []
        operations_root = (self._root_path / OPERATIONS_ROOT).resolve()
        if not operations_root.exists():
            return discovered
        allowed_categories = set(self._categories)

        for path in sorted(operations_root.rglob("*.py")):
            if path.name in {"conftest.py", "__init__.py"}:
                continue
            category = _category_from_path(path, operations_root)
            if category is None or category not in allowed_categories:
                continue
            discovered.extend(self._extract_test_functions(path, category))

        return discovered

    def _discover_categories(self) -> list[str]:
        """Discover section categories deterministically from operation folder paths."""

        operations_root = (self._root_path / OPERATIONS_ROOT).resolve()
        if not operations_root.exists():
            return []

        categories: set[str] = set()
        for path in sorted(operations_root.rglob("*.py")):
            if path.name in {"conftest.py", "__init__.py"}:
                continue
            category = _category_from_path(path, operations_root)
            if category is not None:
                categories.add(category)
        return sorted(categories, key=_category_sort_key)

    def _extract_test_functions(self, path: Path, category: str) -> list[DiscoveredTest]:
        """Extract test functions and one-line docstrings from a Python module."""

        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        results: list[DiscoveredTest] = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                key = f"{path.relative_to(self._root_path).as_posix()}::{node.name}"
                description = _first_docstring_line(ast.get_docstring(node))
                results.append(
                    DiscoveredTest(
                        key=key,
                        category=category,
                        function_name=node.name,
                        description=description,
                        file_path=path.relative_to(self._root_path).as_posix(),
                    )
                )
        return results

    def _render_markdown(self) -> str:
        """Render a terse deterministic markdown report grouped by category."""

        rows = []
        for discovered in self._discovered:
            status = self._status_by_key.get(discovered.key, STATUS_NOT_RUN)
            rows.append((discovered, status))

        total = len(rows)
        passed = sum(1 for _, status in rows if status == STATUS_PASSED)
        failed = sum(1 for _, status in rows if status == STATUS_FAILED)
        skipped_or_not_run = sum(
            1 for _, status in rows if status in (STATUS_SKIPPED, STATUS_NOT_RUN)
        )
        generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

        lines: list[str] = []
        lines.append("# Tests Status")
        lines.append("")
        lines.append(f"Generated: {generated}")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- Total: {total}")
        lines.append(f"- Passed: {passed}")
        lines.append(f"- Failed: {failed}")
        lines.append(f"- Skipped/Not Run: {skipped_or_not_run}")
        lines.append("")

        for category in self._categories:
            lines.append(f"## {category}")
            lines.append("")
            category_rows = [(record, status) for record, status in rows if record.category == category]
            if not category_rows:
                lines.append("No tests discovered.")
                lines.append("")
                continue

            for record, status in category_rows:
                status_text = _status_display(status)
                description = _escape_markdown(record.description)
                lines.append(f"- {status_text} {description}")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"


def pytest_configure(config: Any) -> None:
    """Register visualization plugin with pytest."""

    root_path = Path(str(config.rootpath)).resolve()
    plugin = VisualizationReportPlugin(root_path)
    config.pluginmanager.register(plugin, name="visualization-report-plugin")


def _build_key_from_item(item: Any, root_path: Path) -> str | None:
    """Build canonical key from collected pytest item."""

    try:
        relative_path = Path(str(item.fspath)).resolve().relative_to(root_path).as_posix()
    except Exception:
        return None

    test_name = getattr(item, "originalname", None) or item.name.split("[", 1)[0]
    return f"{relative_path}::{test_name}"


def _first_docstring_line(docstring: str | None) -> str:
    """Return the first line of a docstring or a fallback marker."""

    if not docstring:
        return "[missing docstring]"
    first = docstring.strip().splitlines()[0].strip()
    return first or "[missing docstring]"


def _status_display(status: str) -> str:
    """Map internal status names to markdown display values."""

    if status == STATUS_PASSED:
        return "✅"
    if status == STATUS_FAILED:
        return "❌"
    if status == STATUS_SKIPPED:
        return "⚪"
    return "⚪ not run"


def _escape_markdown(value: str) -> str:
    """Escape markdown characters used by list syntax."""

    return value.replace("|", "\\|")


def _category_from_path(path: Path, operations_root: Path) -> str | None:
    """Resolve category from a test file path under tests/operations."""

    try:
        parts = path.resolve().relative_to(operations_root).parts
    except Exception:
        return None

    if len(parts) < 2:
        return None
    operation = parts[0]
    if operation.startswith("_"):
        return None
    if len(parts) >= 3 and parts[1] in SUBCATEGORY_ORDER:
        suffix_parts = [operation, parts[1], *parts[2:-1]]
        return "/".join(suffix_parts)
    return operation


def _category_sort_key(category: str) -> tuple[object, ...]:
    """Return a stable sort key that keeps parent sections before nested sections."""

    parts = category.split("/")
    operation = parts[0]
    remainder = parts[1:]
    subcategory = remainder[0] if remainder else ""
    subcategory_index = SUBCATEGORY_ORDER.index(subcategory) if subcategory in SUBCATEGORY_ORDER else len(SUBCATEGORY_ORDER)
    nested = remainder[1:] if len(remainder) > 1 else []
    return (operation, subcategory_index, len(nested), tuple(nested))
