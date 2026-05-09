"""Pytest plugin that writes a markdown visualization report for the full test suite."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


TESTS_ROOT = Path("tests")
SUBCATEGORY_ORDER = ("validation", "execution")
MAJOR_CATEGORY_ORDER = (
    "config",
    "create",
    "episodes",
    "events",
    "guidance",
    "identity",
    "persistence",
    "protection",
    "read",
    "recovery",
    "resilience",
    "session_state",
    "telemetry",
    "update",
)
MAJOR_CATEGORY_LABELS = {
    "config": "Config Tests",
    "create": "Create Tests",
    "episodes": "Episodes Tests",
    "events": "Events Tests",
    "guidance": "Guidance Tests",
    "identity": "Identity Tests",
    "persistence": "Persistence Tests",
    "protection": "Protection Tests",
    "read": "Read Tests",
    "recovery": "Recovery Tests",
    "resilience": "Resilience Tests",
    "session_state": "Session State Tests",
    "telemetry": "Telemetry Tests",
    "update": "Update Tests",
}

ARTIFACT_PATH = Path("tests/visualization/artifacts/tests_status.md")

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_NOT_RUN = "not_run"


@dataclass
class DiscoveredTest:
    """Metadata describing one discovered test function and its report category."""

    key: str
    category_parts: tuple[str, ...]
    function_name: str
    description: str
    file_path: str


class VisualizationReportPlugin:
    """Collect pytest outcomes and write a markdown report grouped by major test area."""

    def __init__(self, root_path: Path) -> None:
        self._root_path = root_path
        self._discovered = self._discover_tests()
        self._nodeid_to_key: dict[str, str] = {}
        self._status_by_key: dict[str, str] = {}

    @property
    def discovered(self) -> list[DiscoveredTest]:
        """Return all discovered tests in stable report order."""

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
        """Apply precedence rules while updating one test status."""

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
        """Discover all reportable test functions and their one-line docstrings."""

        tests_root = (self._root_path / TESTS_ROOT).resolve()
        if not tests_root.exists():
            return []

        discovered: list[DiscoveredTest] = []
        for path in sorted(tests_root.rglob("*.py")):
            if path.name in {"conftest.py", "__init__.py"}:
                continue
            category_parts = _category_from_path(path, tests_root)
            if category_parts is None:
                continue
            discovered.extend(self._extract_test_functions(path, category_parts))
        return discovered

    def _extract_test_functions(
        self, path: Path, category_parts: tuple[str, ...]
    ) -> list[DiscoveredTest]:
        """Extract test functions and one-line docstrings from one Python module."""

        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        results: list[DiscoveredTest] = []
        for node in tree.body:
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and node.name.startswith("test_"):
                key = f"{path.relative_to(self._root_path).as_posix()}::{node.name}"
                results.append(
                    DiscoveredTest(
                        key=key,
                        category_parts=category_parts,
                        function_name=node.name,
                        description=_first_docstring_line(ast.get_docstring(node)),
                        file_path=path.relative_to(self._root_path).as_posix(),
                    )
                )
        return results

    def _render_markdown(self) -> str:
        """Render a deterministic markdown report grouped by major test categories."""

        rows = [
            (discovered, self._status_by_key.get(discovered.key, STATUS_NOT_RUN))
            for discovered in self._discovered
        ]

        total = len(rows)
        passed = sum(1 for _, status in rows if status == STATUS_PASSED)
        failed = sum(1 for _, status in rows if status == STATUS_FAILED)
        skipped_or_not_run = sum(
            1 for _, status in rows if status in (STATUS_SKIPPED, STATUS_NOT_RUN)
        )
        generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

        grouped_by_major: dict[str, list[tuple[DiscoveredTest, str]]] = {
            key: [] for key in MAJOR_CATEGORY_ORDER
        }
        for row in rows:
            grouped_by_major.setdefault(row[0].category_parts[0], []).append(row)

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

        for major_category in MAJOR_CATEGORY_ORDER:
            category_rows = grouped_by_major.get(major_category, [])
            if not category_rows:
                continue
            lines.append(f"# {MAJOR_CATEGORY_LABELS[major_category]}")
            lines.append("")
            lines.extend(_render_major_category(category_rows))
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"


def pytest_configure(config: Any) -> None:
    """Register visualization plugin with pytest."""

    root_path = Path(str(config.rootpath)).resolve()
    plugin = VisualizationReportPlugin(root_path)
    config.pluginmanager.register(plugin, name="visualization-report-plugin")


def _build_key_from_item(item: Any, root_path: Path) -> str | None:
    """Build canonical discovery key from one collected pytest item."""

    try:
        relative_path = (
            Path(str(item.fspath)).resolve().relative_to(root_path).as_posix()
        )
    except Exception:
        return None

    test_name = getattr(item, "originalname", None) or item.name.split("[", 1)[0]
    return f"{relative_path}::{test_name}"


def _render_major_category(
    category_rows: list[tuple[DiscoveredTest, str]],
) -> list[str]:
    """Render one major category block with nested headings."""

    lines: list[str] = []
    direct_rows: list[tuple[DiscoveredTest, str]] = []
    first_level_groups: dict[str, list[tuple[DiscoveredTest, str]]] = {}

    for record, status in category_rows:
        remaining_parts = record.category_parts[1:]
        if not remaining_parts:
            direct_rows.append((record, status))
            continue
        first_level_groups.setdefault(remaining_parts[0], []).append((record, status))

    if direct_rows:
        lines.extend(_render_test_bullets(direct_rows))
        lines.append("")

    for group_name in sorted(first_level_groups, key=_first_level_sort_key):
        group_rows = first_level_groups[group_name]
        lines.append(f"## {_humanize_heading(group_name)}")
        lines.append("")

        nested_direct_rows: list[tuple[DiscoveredTest, str]] = []
        nested_groups: dict[tuple[str, ...], list[tuple[DiscoveredTest, str]]] = {}
        for record, status in group_rows:
            tail = record.category_parts[2:]
            if not tail:
                nested_direct_rows.append((record, status))
                continue
            nested_groups.setdefault(tail, []).append((record, status))

        if nested_direct_rows:
            lines.extend(_render_test_bullets(nested_direct_rows))
            lines.append("")

        for tail in sorted(nested_groups, key=_tail_sort_key):
            lines.append(f"### {_humanize_parts(tail)}")
            lines.append("")
            lines.extend(_render_test_bullets(nested_groups[tail]))
            lines.append("")

    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _render_test_bullets(rows: list[tuple[DiscoveredTest, str]]) -> list[str]:
    """Render one flat bullet list for the provided tests."""

    lines: list[str] = []
    for record, status in rows:
        lines.append(
            f"- {_status_display(status)} {_escape_markdown(record.description)}"
        )
    return lines


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


def _category_from_path(path: Path, tests_root: Path) -> tuple[str, ...] | None:
    """Resolve report category parts from one test file path."""

    try:
        parts = path.resolve().relative_to(tests_root).parts
    except Exception:
        return None

    if not parts or any(part.startswith("_") for part in parts):
        return None
    if parts[0] == "visualization":
        return None
    if parts[0] == "config":
        return ("config", *parts[1:-1])
    if parts[0] != "operations" or len(parts) < 3:
        return None

    operation = parts[1]
    if operation.startswith("_"):
        return None
    if len(parts) >= 4 and parts[2] in SUBCATEGORY_ORDER:
        return (operation, parts[2], *parts[3:-1])
    return (operation, *parts[2:-1])


def _first_level_sort_key(group_name: str) -> tuple[int, str]:
    """Return deterministic order for first nested headings under one major category."""

    if group_name in SUBCATEGORY_ORDER:
        return (SUBCATEGORY_ORDER.index(group_name), group_name)
    return (len(SUBCATEGORY_ORDER), group_name)


def _tail_sort_key(parts: tuple[str, ...]) -> tuple[int, tuple[str, ...]]:
    """Return deterministic order for deeper nested headings."""

    return (len(parts), parts)


def _humanize_heading(value: str) -> str:
    """Convert a slug-like heading token into title case."""

    return value.replace("_", " ").title()


def _humanize_parts(parts: tuple[str, ...]) -> str:
    """Convert one or more heading tokens into a human-readable title."""

    return " / ".join(_humanize_heading(part) for part in parts)
