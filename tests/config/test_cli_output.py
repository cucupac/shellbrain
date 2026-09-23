"""Recall presentation preserves content and machine-readable output."""

import json
import re

import pytest

from app.entrypoints.cli.presenters.output import print_result, render_recall


@pytest.mark.parametrize(
    "terminal,no_color,term,colored",
    [
        (False, "", "xterm", False),
        (True, "", "xterm", True),
        (True, "1", "xterm", False),
        (True, "", "dumb", False),
    ],
)
def test_recall_output(monkeypatch, capsys, terminal, no_color, term, colored):
    """TTY output is readable while pipes keep the entire original JSON."""

    monkeypatch.setattr("sys.stdout.isatty", lambda: terminal)
    monkeypatch.setenv("NO_COLOR", no_color)
    monkeypatch.setenv("TERM", term)
    result = {
        "status": "ok",
        "data": {
            "brief": {
                "memories": ["Discovery selects edges."],
                "code": ["router/src/compute_route.rs"],
            },
            "fallback_reason": None,
        },
        "errors": [],
    }
    print_result(result, command="recall")
    output = capsys.readouterr().out
    assert ("\033[" in output) == colored
    if not terminal:
        assert output == json.dumps(result, separators=(",", ":")) + "\n"
        return
    plain = re.sub(r"\033\[[\d;]+m", "", output)
    assert plain == (
        "\n  SHELLBRAIN · RECALL\n\n  Memories\n    • Discovery selects edges.\n\n"
        "  Code\n    • router/src/compute_route.rs\n\n"
    )
    if colored:
        assert "\033[1;36m  Memories" in output
        assert "\033[1;36m  Code" in output


def test_recall_wrapping_and_controls():
    """Wrap bullets, preserve full paths, and escape terminal controls."""

    path = "rust-backends/crates/routing/router/src/compute_route.rs"
    output = render_recall(
        {
            "brief": {
                "memories": [
                    "A café memory.",
                    "Keep all delayed branches when the routes rejoin.",
                    "Escape \x1b[31m safely.",
                ],
                "code": [path],
            },
            "fallback_reason": None,
        },
        width=40,
        color=False,
    )
    assert "    • Keep all delayed branches when the\n      routes rejoin." in output
    assert path in output
    assert "A café memory." in output
    assert "Escape \\u001b[31m safely." in output
    assert "\033" not in output


@pytest.mark.parametrize("command,status", [("recall", "error"), ("snapshot", "ok")])
def test_other_results_keep_complete_json(monkeypatch, capsys, command, status):
    """Errors and non-recall responses must not lose envelope details."""

    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    result = {"status": status, "data": {}, "errors": ["detail"]}
    print_result(result, command=command)
    assert json.loads(capsys.readouterr().out) == result


def test_empty_recall_has_one_message():
    """Empty recall must not display headings or code references."""
    assert render_recall(
        {"brief": {"memories": [], "code": []}}, width=88, color=False
    ) == (
        "\n  SHELLBRAIN · RECALL\n\n    • No relevant memories found for this question.\n"
    )
