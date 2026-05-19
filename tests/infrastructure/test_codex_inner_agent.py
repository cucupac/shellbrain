"""Unit coverage for the Codex inner-agent adapter."""

from __future__ import annotations

import subprocess

from app.core.ports.host_apps.inner_agents import (
    BuildKnowledgeAgentRequest,
    InnerAgentRunRequest,
)
from app.infrastructure.host_apps.inner_agents.codex_cli import CodexCliInnerAgentRunner
from app.infrastructure.host_apps.inner_agents.output_parser import (
    parse_build_knowledge_output,
    parse_inner_agent_brief_output,
    parse_inner_agent_response_output,
)
from app.infrastructure.host_apps.inner_agents.prompt import (
    render_build_context_prompt,
    render_build_knowledge_prompt,
)


def test_codex_runner_parses_stubbed_last_message(monkeypatch, tmp_path) -> None:
    """Codex adapter happy path should work with a stubbed subprocess."""

    def _fake_which(command: str) -> str:
        assert command == "codex"
        return "/usr/bin/codex"

    def _fake_run(args, *, input, text, capture_output, timeout, check, env):
        del input, text, capture_output, timeout, check
        assert env["SHELLBRAIN_INNER_AGENT_MODE"] == "build_context"
        assert env["SHELLBRAIN_PARENT_HOST_APP"] == "codex"
        assert env["SHELLBRAIN_PARENT_HOST_SESSION_KEY"] == "outer-thread"
        output_path = args[args.index("--output-last-message") + 1]
        assert args[args.index("--ask-for-approval") + 1] == "never"
        assert args.index("--ask-for-approval") < args.index("exec")
        assert args[args.index("--sandbox") + 1] == "danger-full-access"
        assert args[args.index("--cd") + 1] != str(tmp_path)
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
    monkeypatch.setenv("CODEX_THREAD_ID", "outer-thread")
    runner = CodexCliInnerAgentRunner(command="codex")

    result = runner.run(_request(repo_root=str(tmp_path)))

    assert result.status == "ok"
    assert result.brief == {
        "summary": "Stub synthesis",
        "constraints": ["Keep core clean"],
    }
    assert result.read_trace["source_ids"] == ["mem-1"]
    assert result.input_tokens is not None
    assert result.output_tokens is not None
    assert result.capture_quality == "estimated"


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


def test_build_knowledge_runner_uses_build_knowledge_mode(monkeypatch, tmp_path) -> None:
    """Codex build_knowledge runs with the writer-scoped inner-agent mode."""

    def _fake_which(command: str) -> str:
        assert command == "codex"
        return "/usr/bin/codex"

    def _fake_run(args, *, input, text, capture_output, timeout, check, env):
        del input, text, capture_output, timeout, check
        assert env["SHELLBRAIN_INNER_AGENT_MODE"] == "build_knowledge"
        assert env["SHELLBRAIN_KNOWLEDGE_BUILD_RUN_ID"] == "run-1"
        assert env["SHELLBRAIN_PARENT_HOST_APP"] == "codex"
        assert env["SHELLBRAIN_PARENT_HOST_SESSION_KEY"] == "outer-thread"
        assert "SHELLBRAIN_DB_ADMIN_DSN" not in env
        output_path = args[args.index("--output-last-message") + 1]
        assert args[args.index("--ask-for-approval") + 1] == "never"
        assert args.index("--ask-for-approval") < args.index("exec")
        assert args[args.index("--sandbox") + 1] == "danger-full-access"
        assert args[args.index("--cd") + 1] != str(tmp_path)
        assert 'model_reasoning_effort="medium"' in args
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(
                '{"status":"ok","run_summary":"Wrote durable knowledge.",'
                '"write_count":2,"skipped_items":[{"summary":"unclear","reason":"low confidence"}],'
                '"read_trace":{"commands":[]},"code_trace":{"files":[]}}'
            )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setenv("SHELLBRAIN_DB_ADMIN_DSN", "postgresql://admin")
    monkeypatch.setenv("CODEX_THREAD_ID", "outer-thread")
    monkeypatch.setattr(
        "app.infrastructure.host_apps.inner_agents.codex_cli.shutil.which",
        _fake_which,
    )
    monkeypatch.setattr(
        "app.infrastructure.host_apps.inner_agents.codex_cli.subprocess.run",
        _fake_run,
    )
    runner = CodexCliInnerAgentRunner(command="codex")

    result = runner.run_build_knowledge(_build_knowledge_request(repo_root=str(tmp_path)))

    assert result.status == "ok"
    assert result.write_count == 2
    assert result.skipped_item_count == 1
    assert result.run_summary == "Wrote durable knowledge."
    assert result.input_tokens is not None
    assert result.output_tokens is not None
    assert result.capture_quality == "estimated"


def test_build_knowledge_output_parser_accepts_no_write_skips() -> None:
    """Parser should accept valid no-write builder output."""

    parsed = parse_build_knowledge_output(
        '{"status":"skipped","run_summary":"No durable write justified.",'
        '"write_count":0,"skipped_items":[{"summary":"duplicate","reason":"already stored"}]}'
    )

    assert parsed["status"] == "skipped"
    assert parsed["write_count"] == 0
    assert parsed["skipped_item_count"] == 1


def test_build_knowledge_output_parser_counts_scenario_writes() -> None:
    """Parser should include scenario writes in derived write counts."""

    parsed = parse_build_knowledge_output(
        '{"status":"ok","run_summary":"Recorded scenario.",'
        '"read_trace":{"commands":[{"command":"shellbrain scenario record --json {}"}]},'
        '"skipped_items":[]}'
    )

    assert parsed["write_count"] == 1


def test_build_context_prompt_allows_read_only_shellbrain_commands() -> None:
    """Prompt should instruct Codex to query Shellbrain directly without expansion loops."""

    prompt = render_build_context_prompt(_request())

    assert "IDENTITY\n" in prompt
    assert "AUTHORITY\n" in prompt
    assert "PROTOCOL\n" in prompt
    assert "JUDGMENT\n" in prompt
    assert prompt.index("shellbrain events") < prompt.index("shellbrain read")
    assert "Shellbrain is a repo-scoped memory system" in prompt
    assert "# KNOWLEDGE MODEL" in prompt
    assert "Concepts are sparse orientation nodes, not tags" in prompt
    assert "claims become concept orientation" in prompt
    assert "memory_links connect abstract concepts" in prompt
    assert "Run events first" in prompt
    assert "Build a compact search text" in prompt
    assert 'Omit placeholders\n   such as "none yet"' in prompt
    assert "current_problem.goal" in prompt
    assert "Run at least one targeted read" in prompt
    assert "expand only the concepts likely to change" in prompt
    assert "Do not rely on\n   detailed concept claims" in prompt
    assert "Run extra reads only when" in prompt
    assert "Synthesize for the worker" in prompt
    assert "no_context_reason" in prompt
    assert "reduces worker time and token spend" in prompt
    assert "created_at" in prompt
    assert "updated_at" in prompt
    assert "Use recency as a tiebreaker" in prompt
    assert "Separate sourced facts from inference" in prompt
    assert "Do not inspect repository files directly" in prompt
    assert "A relevant memory does not need a concept home" in prompt
    assert "do not provide generic coding" in prompt
    assert "conflicts" in prompt
    assert "next_checks" in prompt
    assert "used_in" in prompt
    assert "must list only commands actually run" in prompt
    assert '\\"evidence\\"' in prompt
    assert "knowledge_builder_notes" not in prompt
    assert "preferred_source_id" not in prompt
    assert "shellbrain --help" in prompt
    assert "shellbrain read --help" in prompt
    assert "shellbrain events --help" in prompt
    assert "shellbrain concept show --help" in prompt
    assert "shellbrain events" in prompt
    assert "shellbrain read" in prompt
    assert "shellbrain concept show" in prompt
    assert "shellbrain recall" in prompt
    assert "memory writes" in prompt
    assert "requested_" "expansions" not in prompt
    assert "candidate_" "context" not in prompt
    assert "expansion_" "handles" not in prompt


def test_build_context_prompt_targets_repo_root_when_available(tmp_path) -> None:
    """Inner-agent prompt should make nested Codex target the parent repo explicitly."""

    prompt = render_build_context_prompt(_request(repo_root=str(tmp_path)))

    assert f"shellbrain --repo-root {tmp_path}" in prompt
    assert f"shellbrain --repo-root {tmp_path} events --json" in prompt
    assert f"shellbrain --repo-root {tmp_path} read --json" in prompt


def test_build_knowledge_prompt_defines_authority_and_readiness() -> None:
    """Build prompt should define write authority, code limits, help, and readiness."""

    prompt = render_build_knowledge_prompt(_build_knowledge_request())

    assert "# IDENTITY" in prompt
    assert "internal knowledge builder" in prompt
    assert "# AUTHORITY" in prompt
    assert "# PROTOCOL" in prompt
    assert "# JUDGMENT" in prompt
    assert "memory add" in prompt
    assert "concept update" in prompt
    assert "scenario record" in prompt
    assert "editing files" in prompt
    assert "Run the exact `first_command`" in prompt
    assert "four record classes, not a strict vertical stack" in prompt
    assert "Concepts are not\n   tags" in prompt
    assert "memory_link for concept-to-memory" in prompt
    assert "grounding for concept-to-anchor" in prompt
    assert "definition, behavior, invariant" in prompt
    assert "contains, involves, precedes" in prompt
    assert "Use `involves` sparingly" in prompt
    assert "created_by: use `librarian`" in prompt
    assert "Segment the episode into memory boundaries" in prompt
    assert "Dedupe before every write" in prompt
    assert "do not create a problem memory without a reusable" in prompt
    assert "For problem-solving slices" in prompt
    assert "problem_attempts" in prompt
    assert "links.problem_id" in prompt
    assert "Treat idle-stable episodes as partial" in prompt
    assert "Do not archive historically true memories" in prompt
    assert "do not vote on ordinary" in prompt.lower()
    assert "leave the memory unlinked" in prompt
    assert "stale graph record" in prompt
    assert "final decisive solution" in prompt
    assert "failed_tactic records that a tactic failed in this episode's context" in prompt
    assert "closed_event_id" in prompt
    assert "terminal_event_id" not in prompt
    assert "event_watermark" in prompt
    assert '\\"after_seq\\":3' in prompt
    assert '\\"up_to_seq\\":8' in prompt
    assert '\\"limit\\":100' not in prompt
    assert "shellbrain --help" in prompt
    assert "memory add --help" in prompt
    assert "scenario record --help" in prompt
    assert "Write fewer, stronger records" in prompt
    assert "solved" in prompt
    assert "abandoned" in prompt
    assert "scenario.v1" in prompt
    assert "write_count" in prompt
    assert "memory/concept/scenario" in prompt


def test_build_knowledge_prompt_targets_repo_root_when_available(tmp_path) -> None:
    """Build prompt should make every internal command target the parent repo."""

    prompt = render_build_knowledge_prompt(
        _build_knowledge_request(repo_root=str(tmp_path))
    )

    assert f"shellbrain --repo-root {tmp_path} events --json" in prompt
    assert f"shellbrain --repo-root {tmp_path} memory add --json" in prompt
    assert f"shellbrain --repo-root {tmp_path} concept update --json" in prompt
    assert f"shellbrain --repo-root {tmp_path} scenario record --json" in prompt


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


def _build_knowledge_request(
    *, repo_root: str = "/tmp/repo"
) -> BuildKnowledgeAgentRequest:
    return BuildKnowledgeAgentRequest(
        run_id="run-1",
        provider="codex",
        model="gpt-5.4",
        reasoning="medium",
        timeout_seconds=180,
        repo_id="repo-a",
        repo_root=repo_root,
        episode_id="episode-1",
        trigger="watermark_stable",
        event_watermark=8,
        previous_event_watermark=3,
        max_shellbrain_reads=8,
        max_code_files=24,
        max_write_commands=20,
    )
