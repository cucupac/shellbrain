"""Unit coverage for the Codex inner-agent adapter."""

from __future__ import annotations

import subprocess

import pytest
from pydantic import ValidationError

from app.core.ports.host_apps.inner_agents import (
    BuildKnowledgeAgentRequest,
    InnerAgentRunRequest,
)
from app.infrastructure.host_apps.inner_agents.codex_cli import (
    CodexCliInnerAgentRunner,
    _codex_exec_args,
)
from app.infrastructure.host_apps.inner_agents.output_parser import (
    InnerAgentOutputParseError,
    parse_build_knowledge_output,
    parse_inner_agent_brief_output,
)
from app.infrastructure.host_apps.inner_agents.prompt import (
    render_build_context_synthesis_prompt,
    render_build_knowledge_prompt,
)


@pytest.mark.parametrize("model", ["gpt-5.6-luna", "gpt-6-luna"])
def test_codex_exec_uses_fast_service_tier_for_luna(model: str) -> None:
    """Luna inner-agent calls should use Codex Fast mode."""

    args = _codex_exec_args(
        command_path="/usr/bin/codex",
        model=model,
        reasoning="low",
        workspace="/tmp/workspace",
        output_path="/tmp/output.json",
    )

    assert 'service_tier="fast"' in args


def test_codex_exec_keeps_standard_service_tier_for_other_models() -> None:
    """Fast mode should remain limited to Luna inner-agent calls."""

    args = _codex_exec_args(
        command_path="/usr/bin/codex",
        model="gpt-5.4-mini",
        reasoning="low",
        workspace="/tmp/workspace",
        output_path="/tmp/output.json",
    )

    assert not any("service_tier" in arg for arg in args)


def test_codex_runner_parses_stubbed_last_message(monkeypatch, tmp_path) -> None:
    """Codex adapter happy path should work with a stubbed subprocess."""

    def _fake_which(command: str) -> str:
        assert command == "codex"
        return "/usr/bin/codex"

    def _fake_run(args, *, input, text, capture_output, timeout, check, env):
        del input, text, capture_output, timeout, check
        assert env["SHELLBRAIN_INNER_AGENT_MODE"] == "build_context_synthesis"
        assert env["SHELLBRAIN_PARENT_HOST_APP"] == "codex"
        assert env["SHELLBRAIN_PARENT_HOST_SESSION_KEY"] == "outer-thread"
        output_path = args[args.index("--output-last-message") + 1]
        assert args[args.index("--ask-for-approval") + 1] == "never"
        assert args.index("--ask-for-approval") < args.index("exec")
        assert "--ignore-user-config" in args
        assert "--json" in args
        assert _disabled_feature(args, "plugins")
        assert _disabled_feature(args, "tool_search")
        assert args[args.index("--sandbox") + 1] == "danger-full-access"
        assert args[args.index("--cd") + 1] != str(tmp_path)
        assert "--model" in args
        assert 'model_reasoning_effort="medium"' in args
        tmp_path.joinpath("seen.txt").write_text("ran", encoding="utf-8")
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(
                '{"brief": {"summary": "Stub synthesis", "constraints": ["Keep core clean"], "known_traps": [], "prior_cases": [], "concept_orientation": [], "anchors": [], "conflicts": [], "gaps": [], "next_checks": []}, "read_trace": {"commands": [{"command": "shellbrain read --json {}", "source_ids": ["mem-1"]}], "source_ids": ["mem-1"]}}'
            )
        return subprocess.CompletedProcess(
            args,
            0,
            stdout='{"type":"turn.completed","usage":{"input_tokens":11,"cached_input_tokens":3,"output_tokens":7,"reasoning_output_tokens":2}}\n',
            stderr="",
        )

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
    assert {k: v for k, v in result.brief.items() if v} == {
        "summary": "Stub synthesis",
        "constraints": ["Keep core clean"],
    }
    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert result.reasoning_output_tokens == 2
    assert result.cached_input_tokens_total == 3
    assert result.capture_quality == "exact"


def test_codex_runner_synthesis_only_uses_synthesis_mode(monkeypatch, tmp_path) -> None:
    """Codex synthesis-only runs should not grant Shellbrain command access."""

    def _fake_which(command: str) -> str:
        assert command == "codex"
        return "/usr/bin/codex"

    def _fake_run(args, *, input, text, capture_output, timeout, check, env):
        del text, capture_output, timeout, check
        assert env["SHELLBRAIN_INNER_AGENT_MODE"] == "build_context_synthesis"
        assert "Do not run commands" in input
        assert "mem-1" in input
        assert "shellbrain read --json" not in input
        output_path = args[args.index("--output-last-message") + 1]
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(
                '{"brief": {"summary": "Synthesized from pack", "constraints": [], "known_traps": [], "prior_cases": [], "concept_orientation": [], "anchors": [], "conflicts": [], "gaps": [], "next_checks": []}}'
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
    runner = CodexCliInnerAgentRunner(command="codex")

    result = runner.run(
        _request(
            repo_root=str(tmp_path),
            deterministic_pack={"memories": [{"id": "mem-1", "text": "Fact"}]},
        )
    )

    assert result.status == "ok"
    assert {k: v for k, v in result.brief.items() if v} == {
        "summary": "Synthesized from pack"
    }


def test_inner_agent_output_parser_accepts_json_fenced_brief() -> None:
    """Output parser should accept common fenced JSON responses."""

    brief = parse_inner_agent_brief_output(
        '```json\n{"brief": {"summary": "Context found", "gaps": [], "constraints": [], "known_traps": [], "prior_cases": [], "concept_orientation": [], "anchors": [], "conflicts": [], "next_checks": []}}\n```'
    )

    assert brief["summary"] == "Context found"


def test_build_knowledge_runner_uses_build_knowledge_mode(
    monkeypatch, tmp_path
) -> None:
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

    result = runner.run_build_knowledge(
        _build_knowledge_request(repo_root=str(tmp_path))
    )

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


def test_recall_provider_requires_an_evidence_pack_and_brief_envelope() -> None:
    """Reject obsolete request and output shapes before treating synthesis as valid."""

    payload = _request().model_dump(exclude={"deterministic_pack"})
    with pytest.raises(ValidationError, match="deterministic_pack"):
        InnerAgentRunRequest.model_validate(payload)
    with pytest.raises(ValidationError, match="deterministic_pack"):
        InnerAgentRunRequest.model_validate({**payload, "deterministic_pack": None})
    with pytest.raises(InnerAgentOutputParseError, match="valid brief"):
        parse_inner_agent_brief_output('{"summary":"Missing the brief envelope"}')


def test_build_knowledge_output_parser_counts_scenario_writes() -> None:
    """Parser should include scenario writes in derived write counts."""

    parsed = parse_build_knowledge_output(
        '{"status":"ok","run_summary":"Recorded scenario.",'
        '"read_trace":{"commands":[{"command":"shellbrain scenario record --json {}"}]},'
        '"skipped_items":[]}'
    )

    assert parsed["write_count"] == 1


def test_build_context_synthesis_prompt_uses_only_deterministic_pack() -> None:
    """synthesis prompt should explain graph semantics without Shellbrain commands."""

    prompt = render_build_context_synthesis_prompt(
        _request(
            deterministic_pack={"memories": [{"id": "mem-1", "text": "Fact"}]},
        )
    )

    assert "build_context_synthesizer" in prompt
    assert "Do not run commands" in prompt
    assert "Memory links explain why" in prompt
    assert "# TEMPORAL AND LIFECYCLE JUDGMENT" in prompt
    assert "# PREFERENCES" in prompt
    assert "# CHANGE AND CONTRADICTION JUDGMENT" in prompt
    assert "# SECTION RULES" in prompt
    assert "# WRITE CLEARLY" in prompt
    assert "Lead with the answer" in prompt
    assert "Summary: max two sentences" in prompt
    assert "Lists: max three items" in prompt
    assert "Treat `max_brief_tokens` as the limit for the complete brief" in prompt
    assert "Keep every relevant constraint, trap, conflict, and warning" in prompt
    assert "Use only the text and metadata present in the pack" in prompt
    assert "The query is the complete worker request" in prompt
    assert (
        "facts, preferences, invariants, behavior claims, configuration rules" in prompt
    )
    assert '"sources":' not in prompt
    assert "deterministic source provenance" not in prompt
    assert "mem-1" in prompt
    assert "shellbrain read --json" not in prompt


def test_build_knowledge_prompt_defines_authority_and_readiness() -> None:
    """Build prompt should define write authority, code limits, help, and readiness."""

    prompt = render_build_knowledge_prompt(_build_knowledge_request())

    assert "# IDENTITY" in prompt
    assert "internal knowledge-builder agent" in prompt
    assert "# AUTHORITY" in prompt
    assert "# PROTOCOL" in prompt
    assert "# JUDGMENT" in prompt
    assert "memory add" in prompt
    assert "concept update" in prompt
    assert "scenario record" in prompt
    assert "snapshot-backed solution delta" in prompt
    assert "code_delta_context" in prompt
    assert "sharpen solution memories, change memories" in prompt
    assert "Do not copy raw changed-file lists" in prompt
    assert "`shellbrain snapshot`" in prompt
    assert "Do not edit files" in prompt
    assert "Run the exact `first_command`" in prompt
    assert "four record classes" in prompt
    assert "do not form a strict vertical stack" in prompt
    assert "Concepts are not tags" in prompt
    assert "Use `memory_link` to connect a concept to a memory" in prompt
    assert "Use `grounding` to connect a concept to an anchor" in prompt
    assert "`definition`, `behavior`, `invariant`" in prompt
    assert "`contains`, `involves`, `precedes`" in prompt
    assert "Use `involves` sparingly" in prompt
    assert "`created_by`: Use `librarian`" in prompt
    assert "`line_range`, `api_route`, `db_table`, and `config_key`" in prompt
    assert "Segment the episode into reusable memory boundaries" in prompt
    assert "Check for duplicates once per topic" in prompt
    assert "Do not create a problem memory without a reusable" in prompt
    assert "For a problem-solving slice" in prompt
    assert "structural_memory_relations" in prompt
    assert "problem_attempts" not in prompt
    assert "links.problem_id" in prompt
    assert "Treat idle-stable episodes as partial" in prompt
    assert "Do not mark historically true memories wrong" in " ".join(prompt.split())
    assert "do not vote on ordinary" in prompt.lower()
    assert "looked relevant enough to affect work" in prompt
    assert (
        "Utility votes support evaluation; they do not change current recall ranking"
        in prompt
    )
    assert "Leave the memory unlinked" in prompt
    assert "update_lifecycle" in prompt
    assert "final decisive solution" in prompt
    assert (
        "`failed_tactic` records that a tactic failed in this episode's context"
        in prompt
    )
    assert "closed_event_id" in prompt
    assert "terminal_event_id" not in prompt
    assert "event_watermark" in prompt
    assert (
        "Prefer an available `file_hash`, `symbol_hash`, or other supported source ref"
        in prompt
    )
    assert '\\"after_seq\\":3' in prompt
    assert '\\"up_to_seq\\":8' in prompt
    assert '\\"limit\\":100' not in prompt
    assert "shellbrain --help" in prompt
    assert "memory add --help" in prompt
    assert "scenario record --help" in prompt
    assert (
        "snapshot"
        not in prompt.split('"help_commands"')[1].split('"command_lexicon"')[0]
    )
    assert "Write fewer, stronger records" in prompt
    assert "Preserve product intent, decision reasons, failed approaches" in prompt
    assert "Skip routine implementation facts" in prompt
    assert "Reuse inspected results for related writes" in prompt
    assert "solved" in prompt
    assert "abandoned" in prompt
    assert "scenario.v1" in prompt
    assert "write_count" in prompt
    assert "memory/concept/scenario" in prompt


def test_knowledge_prompts_require_clear_targeted_writing() -> None:
    """Automatic learning and explicit teaching should receive the same writing rules."""

    for prompt in (render_build_knowledge_prompt(_build_knowledge_request()),):
        assert "Write one focused lesson per memory." in prompt
        assert "Use active voice." in prompt
        assert "Use one term for one meaning." in prompt
        assert "Use common, short words." in prompt
        assert "Write no more than 20 words in each sentence." in prompt


def test_build_knowledge_prompt_targets_repo_root_when_available(tmp_path) -> None:
    """Build prompt should make every internal command target the parent repo."""

    prompt = render_build_knowledge_prompt(
        _build_knowledge_request(repo_root=str(tmp_path))
    )

    assert f"shellbrain --repo-root {tmp_path} events --json" in prompt
    assert f"shellbrain --repo-root {tmp_path} memory add --json" in prompt
    assert f"shellbrain --repo-root {tmp_path} concept update --json" in prompt
    assert f"shellbrain --repo-root {tmp_path} scenario record --json" in prompt


def _request(
    *,
    repo_root: str | None = None,
    deterministic_pack: dict | None = None,
) -> InnerAgentRunRequest:
    return InnerAgentRunRequest(
        agent_name="build_context",
        provider="codex",
        model="gpt-5.4-mini",
        reasoning="medium",
        timeout_seconds=90,
        max_brief_tokens=1_800,
        query="what matters?",
        repo_root=repo_root,
        deterministic_pack=deterministic_pack
        if deterministic_pack is not None
        else {"memories": []},
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


def _disabled_feature(args: list[str], feature: str) -> bool:
    return any(
        left == "--disable" and right == feature
        for left, right in zip(args, args[1:], strict=False)
    )


def test_synthesis_resolves_similar_case_endpoints_without_mutating_input():
    """Relationship text stays paired even when candidate order differs."""
    import copy
    import json

    pack = {
        "memories": [
            {"id": "s2", "text": "Free disk space"},
            {"id": "p1", "text": "Writes time out with a lock held"},
            {"id": "p2", "text": "Writes time out with a full disk"},
            {"id": "s1", "text": "Release the lock"},
        ],
        "memory_relations": [
            {
                "subject_memory_id": "p2",
                "object_memory_id": "s2",
                "predicate": "solved_by",
                "status": "maybe_stale",
            },
            {
                "subject_memory_id": "p1",
                "object_memory_id": "s1",
                "predicate": "solved_by",
                "status": "active",
            },
        ],
    }
    original = copy.deepcopy(pack)
    prompt = render_build_context_synthesis_prompt(_request(deterministic_pack=pack))
    payload = json.loads(
        next(line for line in prompt.splitlines() if line.startswith('{"budgets"'))
    )
    cases = payload["deterministic_graph_pack"]["memory_relations"]
    assert cases[0]["subject_text"] == "Writes time out with a full disk"
    assert cases[0]["object_text"] == "Free disk space"
    assert cases[0]["status"] == "maybe_stale"
    assert cases[1]["object_text"] == "Release the lock"
    assert pack == original
