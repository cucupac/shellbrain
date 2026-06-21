"""Unit coverage for the Claude Code inner-agent adapter."""

from __future__ import annotations

import json
import subprocess

import pytest

from app.core.ports.host_apps.inner_agents import (
    BuildKnowledgeAgentRequest,
    InnerAgentRunRequest,
)
from app.infrastructure.host_apps.inner_agents.claude_cli import (
    ClaudeCliInnerAgentRunner,
)


def test_claude_runner_parses_envelope_and_restricts_tools(monkeypatch) -> None:
    """Claude adapter should unwrap print-mode JSON and restrict built-in tools."""

    def _fake_which(command: str) -> str:
        assert command == "claude"
        return "/usr/bin/claude"

    def _fake_run(args, *, input, text, capture_output, timeout, check, env):
        del input, text, capture_output, timeout, check
        assert env["SHELLBRAIN_INNER_AGENT_MODE"] == "build_context"
        assert args[:2] == ["/usr/bin/claude", "-p"]
        assert _arg_value(args, "--output-format") == "json"
        assert "--no-session-persistence" in args
        assert "--safe-mode" in args
        assert _arg_value(args, "--model") == "sonnet"
        assert "--fallback-model" not in args
        assert _arg_value(args, "--effort") == "medium"
        assert _arg_value(args, "--tools") == "Bash"
        assert "Bash(shellbrain *)" in args
        assert "--strict-mcp-config" in args
        assert _arg_value(args, "--disallowedTools") == "mcp__*"
        settings = json.loads(_arg_value(args, "--settings"))
        assert settings == {
            "availableModels": ["sonnet"],
            "enforceAvailableModels": True,
            "model": "sonnet",
        }
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps(
                {
                    "result": (
                        '{"brief":{"summary":"Claude synthesis"},'
                        '"read_trace":{"source_ids":["mem-1"]}}'
                    ),
                    "usage": {
                        "input_tokens": 13,
                        "output_tokens": 8,
                        "reasoning_output_tokens": 2,
                        "cached_input_tokens": 3,
                    },
                    "modelUsage": {"model": "claude-sonnet-4-6"},
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(
        "app.infrastructure.host_apps.inner_agents.claude_cli.shutil.which",
        _fake_which,
    )
    monkeypatch.setattr(
        "app.infrastructure.host_apps.inner_agents.claude_cli.subprocess.run",
        _fake_run,
    )
    runner = ClaudeCliInnerAgentRunner(command="claude")

    result = runner.run(_request())

    assert result.status == "ok"
    assert result.provider == "claude"
    assert result.model == "sonnet"
    assert result.brief == {"summary": "Claude synthesis"}
    assert result.read_trace == {"source_ids": ["mem-1"]}
    assert result.input_tokens == 13
    assert result.output_tokens == 8
    assert result.reasoning_output_tokens == 2
    assert result.cached_input_tokens_total == 3
    assert result.capture_quality == "exact"


def test_claude_synthesis_only_disables_tools(monkeypatch) -> None:
    """Synthesis-only recall should not grant Claude any tools."""

    def _fake_run(args, *, input, text, capture_output, timeout, check, env):
        del input, text, capture_output, timeout, check
        assert env["SHELLBRAIN_INNER_AGENT_MODE"] == "build_context_synthesis"
        assert _arg_value(args, "--tools") == ""
        assert "--allowedTools" not in args
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps({"result": '{"brief":{"summary":"From pack"}}'}),
            stderr="",
        )

    _patch_claude(monkeypatch, _fake_run)
    runner = ClaudeCliInnerAgentRunner(command="claude")

    result = runner.run(
        _request(
            synthesis_only=True,
            deterministic_pack={"memories": [{"id": "mem-1", "text": "Fact"}]},
        )
    )

    assert result.status == "ok"
    assert result.capture_quality == "estimated"


def test_claude_build_knowledge_allows_read_search_and_shellbrain_bash(
    monkeypatch,
) -> None:
    """Build knowledge may read/search files but Bash stays Shellbrain-scoped."""

    def _fake_run(args, *, input, text, capture_output, timeout, check, env):
        del input, text, capture_output, timeout, check
        assert env["SHELLBRAIN_INNER_AGENT_MODE"] == "build_knowledge"
        assert _arg_value(args, "--tools") == "Bash,Read,Grep,Glob"
        allowed = args[args.index("--allowedTools") + 1 :]
        assert "Bash(shellbrain *)" in allowed
        assert "Read" in allowed
        assert "Grep" in allowed
        assert "Glob" in allowed
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps(
                {
                    "result": (
                        '{"status":"ok","run_summary":"Wrote knowledge.",'
                        '"write_count":1,"skipped_items":[]}'
                    )
                }
            ),
            stderr="",
        )

    _patch_claude(monkeypatch, _fake_run)
    runner = ClaudeCliInnerAgentRunner(command="claude")

    result = runner.run_build_knowledge(_build_knowledge_request())

    assert result.status == "ok"
    assert result.write_count == 1
    assert result.capture_quality == "estimated"


@pytest.mark.parametrize(
    ("stdout", "error_code"),
    [
        ("not json", "claude_invalid_json"),
        ("{}", "claude_missing_result"),
        (json.dumps({"result": {"summary": "wrong"}}), "claude_missing_result"),
    ],
)
def test_claude_runner_rejects_bad_outer_envelope(
    monkeypatch,
    stdout: str,
    error_code: str,
) -> None:
    """Malformed Claude envelopes should fail before Shellbrain output parsing."""

    def _fake_run(args, *, input, text, capture_output, timeout, check, env):
        del input, text, capture_output, timeout, check, env
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    _patch_claude(monkeypatch, _fake_run)
    runner = ClaudeCliInnerAgentRunner(command="claude")

    result = runner.run(_request())

    assert result.status == "invalid_output"
    assert result.error_code == error_code


def test_claude_runner_reports_nonzero_exit(monkeypatch) -> None:
    """Nonzero Claude exits should not fall through to output parsing."""

    def _fake_run(args, *, input, text, capture_output, timeout, check, env):
        del input, text, capture_output, timeout, check, env
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="auth failed")

    _patch_claude(monkeypatch, _fake_run)
    runner = ClaudeCliInnerAgentRunner(command="claude")

    result = runner.run(_request())

    assert result.status == "error"
    assert result.error_code == "claude_nonzero_exit"
    assert result.error_message == "auth failed"


def test_claude_runner_rejects_disallowed_reported_model(monkeypatch) -> None:
    """Reported non-Sonnet usage should fail the run."""

    def _fake_run(args, *, input, text, capture_output, timeout, check, env):
        del input, text, capture_output, timeout, check, env
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps(
                {
                    "result": '{"brief":{"summary":"Too expensive"}}',
                    "modelUsage": {"model": "claude-haiku-4-5"},
                }
            ),
            stderr="",
        )

    _patch_claude(monkeypatch, _fake_run)
    runner = ClaudeCliInnerAgentRunner(command="claude")

    result = runner.run(_request())

    assert result.status == "error"
    assert result.error_code == "claude_disallowed_model"


def _request(
    *,
    synthesis_only: bool = False,
    deterministic_pack: dict | None = None,
) -> InnerAgentRunRequest:
    return InnerAgentRunRequest(
        agent_name="build_context",
        provider="claude",
        model="sonnet",
        reasoning="medium",
        timeout_seconds=90,
        max_brief_tokens=1_800,
        query="what matters?",
        current_problem={
            "goal": "solve problem",
            "surface": "tests",
            "obstacle": "unknown",
            "hypothesis": "none yet",
        },
        synthesis_only=synthesis_only,
        deterministic_pack=deterministic_pack,
    )


def _build_knowledge_request() -> BuildKnowledgeAgentRequest:
    return BuildKnowledgeAgentRequest(
        run_id="run-1",
        provider="claude",
        model="sonnet",
        reasoning="xhigh",
        timeout_seconds=600,
        repo_id="repo-a",
        repo_root="/tmp/repo",
        episode_id="episode-1",
        trigger="watermark_stable",
        event_watermark=8,
        previous_event_watermark=3,
        max_shellbrain_reads=8,
        max_code_files=24,
        max_write_commands=20,
    )


def _patch_claude(monkeypatch, fake_run) -> None:
    monkeypatch.setattr(
        "app.infrastructure.host_apps.inner_agents.claude_cli.shutil.which",
        lambda command: f"/usr/bin/{command}",
    )
    monkeypatch.setattr(
        "app.infrastructure.host_apps.inner_agents.claude_cli.subprocess.run",
        fake_run,
    )


def _arg_value(args: list[str], flag: str) -> str:
    return args[args.index(flag) + 1]
