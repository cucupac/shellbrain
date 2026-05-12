"""Unit coverage for the Codex inner-agent adapter."""

from __future__ import annotations

import subprocess

from app.core.ports.host_apps.inner_agents import InnerAgentRunRequest
from app.infrastructure.host_apps.inner_agents.codex_cli import CodexCliInnerAgentRunner
from app.infrastructure.host_apps.inner_agents.output_parser import (
    parse_inner_agent_brief_output,
    parse_inner_agent_response_output,
)


def test_codex_runner_defaults_to_provider_unavailable_without_unbounded_cli() -> None:
    """Codex adapter should not launch unbounded CLI execution by default."""

    runner = CodexCliInnerAgentRunner(
        command="codex",
        working_directory="repo_root",
        allow_unbounded_cli=False,
    )

    result = runner.run(_request())

    assert result.status == "provider_unavailable"
    assert result.fallback_used is True
    assert result.error_code == "bounded_mode_unavailable"


def test_codex_runner_parses_stubbed_last_message(monkeypatch, tmp_path) -> None:
    """Codex adapter happy path should work with a stubbed subprocess."""

    def _fake_which(command: str) -> str:
        assert command == "codex"
        return "/usr/bin/codex"

    def _fake_run(args, *, input, text, capture_output, timeout, check):
        del input, text, capture_output, timeout, check
        output_path = args[args.index("--output-last-message") + 1]
        assert "--model" in args
        assert 'model_reasoning_effort="low"' in args
        tmp_path.joinpath("seen.txt").write_text("ran", encoding="utf-8")
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(
                '{"brief":{"summary":"Stub synthesis","constraints":["Keep core clean"]}}'
            )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "app.infrastructure.host_apps.inner_agents.codex_cli.shutil.which",
        _fake_which,
    )
    monkeypatch.setattr(
        "app.infrastructure.host_apps.inner_agents.codex_cli.subprocess.run",
        _fake_run,
    )
    runner = CodexCliInnerAgentRunner(
        command="codex",
        working_directory="repo_root",
        allow_unbounded_cli=True,
    )

    result = runner.run(_request(repo_root=str(tmp_path)))

    assert result.status == "ok"
    assert result.brief == {
        "summary": "Stub synthesis",
        "constraints": ["Keep core clean"],
    }
    assert result.input_token_estimate is not None
    assert result.output_token_estimate is not None


def test_inner_agent_output_parser_accepts_json_fenced_brief() -> None:
    """Output parser should accept common fenced JSON responses."""

    brief = parse_inner_agent_brief_output(
        '```json\n{"brief":{"summary":"Context found","gaps":[]}}\n```'
    )

    assert brief["summary"] == "Context found"


def test_inner_agent_output_parser_accepts_expansion_requests() -> None:
    """Output parser should accept structured private expansion requests."""

    brief, requested_expansions = parse_inner_agent_response_output(
        '{"requested_expansions":[{"read_payload":{"query":"more context"}}]}'
    )

    assert brief is None
    assert requested_expansions == [{"read_payload": {"query": "more context"}}]


def _request(*, repo_root: str | None = None) -> InnerAgentRunRequest:
    return InnerAgentRunRequest(
        agent_name="build_context",
        provider="codex",
        model="gpt-5.4-mini",
        reasoning="low",
        timeout_seconds=90,
        max_candidate_tokens=10_000,
        max_brief_tokens=1_800,
        query="what matters?",
        repo_root=repo_root,
        candidate_context={
            "direct": [],
            "explicit_related": [],
            "implicit_related": [],
            "concepts": {"items": []},
        },
    )
