"""Unit coverage for the Codex inner-agent adapter."""

from __future__ import annotations

import subprocess

from app.core.ports.host_apps.inner_agents import InnerAgentRunRequest
from app.infrastructure.host_apps.inner_agents.codex_cli import CodexCliInnerAgentRunner
from app.infrastructure.host_apps.inner_agents.output_parser import (
    parse_inner_agent_brief_output,
    parse_inner_agent_response_output,
)
from app.infrastructure.host_apps.inner_agents.prompt import render_build_context_prompt


def test_codex_runner_requires_shellbrain_cli_access() -> None:
    """Codex adapter should not launch when Shellbrain CLI access is disabled."""

    runner = CodexCliInnerAgentRunner(
        command="codex",
        working_directory="repo_root",
        allow_shellbrain_cli=False,
    )

    result = runner.run(_request())

    assert result.status == "provider_unavailable"
    assert result.fallback_used is True
    assert result.error_code == "shellbrain_cli_not_allowed"


def test_codex_runner_parses_stubbed_last_message(monkeypatch, tmp_path) -> None:
    """Codex adapter happy path should work with a stubbed subprocess."""

    def _fake_which(command: str) -> str:
        assert command == "codex"
        return "/usr/bin/codex"

    def _fake_run(args, *, input, text, capture_output, timeout, check, env):
        del input, text, capture_output, timeout, check
        assert env["SHELLBRAIN_INNER_AGENT_READ_ONLY"] == "1"
        output_path = args[args.index("--output-last-message") + 1]
        assert "--model" in args
        assert 'model_reasoning_effort="low"' in args
        tmp_path.joinpath("seen.txt").write_text("ran", encoding="utf-8")
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(
                '{"brief":{"summary":"Stub synthesis","constraints":["Keep core clean"]},'
                '"read_trace":{"commands":[{"command":"shellbrain read --json {}","source_ids":["mem-1"]}],"source_ids":["mem-1"]}}'
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
        allow_shellbrain_cli=True,
    )

    result = runner.run(_request(repo_root=str(tmp_path)))

    assert result.status == "ok"
    assert result.brief == {
        "summary": "Stub synthesis",
        "constraints": ["Keep core clean"],
    }
    assert result.read_trace["source_ids"] == ["mem-1"]
    assert result.input_token_estimate is not None
    assert result.output_token_estimate is not None


def test_inner_agent_output_parser_accepts_json_fenced_brief() -> None:
    """Output parser should accept common fenced JSON responses."""

    brief = parse_inner_agent_brief_output(
        '```json\n{"brief":{"summary":"Context found","gaps":[]}}\n```'
    )

    assert brief["summary"] == "Context found"


def test_inner_agent_output_parser_accepts_read_trace() -> None:
    """Output parser should accept provider read trace metadata."""

    brief, read_trace = parse_inner_agent_response_output(
        '{"brief":{"summary":"Context found"},"read_trace":{"source_ids":["mem-1"]}}'
    )

    assert brief == {"summary": "Context found"}
    assert read_trace == {"source_ids": ["mem-1"]}


def test_build_context_prompt_allows_read_only_shellbrain_commands() -> None:
    """Prompt should instruct Codex to query Shellbrain directly without expansion loops."""

    prompt = render_build_context_prompt(_request())

    assert "ROLE\n" in prompt
    assert "REQUIRED WORKFLOW\n" in prompt
    assert "READINESS TO SYNTHESIZE\n" in prompt
    assert prompt.index("shellbrain events") < prompt.index("shellbrain read")
    assert "Run `shellbrain events" in prompt
    assert "Run at least one targeted `shellbrain read`" in prompt
    assert "using both the query and current_problem" in prompt
    assert "If read results include concept refs" in prompt
    assert "Synthesize only when" in prompt
    assert "no_context_reason" in prompt
    assert "shellbrain --help" in prompt
    assert "shellbrain read --help" in prompt
    assert "shellbrain events --help" in prompt
    assert "shellbrain concept show --help" in prompt
    assert "shellbrain events" in prompt
    assert "shellbrain read" in prompt
    assert "shellbrain concept show" in prompt
    assert "shellbrain recall" in prompt
    assert "requested_" "expansions" not in prompt
    assert "candidate_" "context" not in prompt
    assert "expansion_" "handles" not in prompt


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
        current_problem={
            "goal": "solve problem",
            "surface": "tests",
            "obstacle": "unknown",
            "hypothesis": "none yet",
        },
        repo_root=repo_root,
    )
