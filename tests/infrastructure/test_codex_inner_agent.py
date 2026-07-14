"""Unit coverage for the Codex inner-agent adapter."""

from __future__ import annotations

import subprocess

import pytest

from app.core.ports.host_apps.inner_agents import (
    BuildKnowledgeAgentRequest,
    InnerAgentRunRequest,
    TeachKnowledgeAgentRequest,
)
from app.infrastructure.host_apps.inner_agents.codex_cli import CodexCliInnerAgentRunner
from app.infrastructure.host_apps.inner_agents.output_parser import (
    InnerAgentOutputParseError,
    parse_build_knowledge_output,
    parse_inner_agent_brief_output,
    parse_inner_agent_response_output,
    parse_wiki_summary_output,
)
from app.infrastructure.host_apps.inner_agents.prompt import (
    render_build_context_prompt,
    render_build_context_synthesis_prompt,
    render_build_knowledge_prompt,
    render_teach_knowledge_prompt,
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
                '{"brief":{"summary":"Stub synthesis","constraints":["Keep core clean"]},'
                '"read_trace":{"commands":[{"command":"shellbrain read --json {}","source_ids":["mem-1"]}],"source_ids":["mem-1"]}}'
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
    assert result.brief == {
        "summary": "Stub synthesis",
        "constraints": ["Keep core clean"],
    }
    assert result.read_trace["source_ids"] == ["mem-1"]
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
            handle.write('{"brief":{"summary":"Synthesized from pack"}}')
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
            synthesis_only=True,
            deterministic_pack={"memories": [{"id": "mem-1", "text": "Fact"}]},
        )
    )

    assert result.status == "ok"
    assert result.brief == {"summary": "Synthesized from pack"}
    assert result.read_trace == {}


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


def test_wiki_summary_output_parser_requires_exact_summary_object() -> None:
    """wiki_summary output should keep a strict provider contract."""

    assert parse_wiki_summary_output('{"summary":"A concise article."}') == (
        "A concise article."
    )

    with pytest.raises(InnerAgentOutputParseError) as excinfo:
        parse_wiki_summary_output('{"summary":"A concise article.","trace":[]}')

    assert "unexpected keys: trace" in str(excinfo.value)


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


def test_teach_knowledge_runner_uses_teach_mode(monkeypatch, tmp_path) -> None:
    """Codex teach_knowledge runs with the explicit teaching inner-agent mode."""

    def _fake_which(command: str) -> str:
        assert command == "codex"
        return "/usr/bin/codex"

    def _fake_run(args, *, input, text, capture_output, timeout, check, env):
        assert "teaching_text" in input
        del text, capture_output, timeout, check
        assert env["SHELLBRAIN_INNER_AGENT_MODE"] == "teach"
        assert env["SHELLBRAIN_KNOWLEDGE_BUILD_RUN_ID"] == "run-1"
        assert "SHELLBRAIN_DB_ADMIN_DSN" not in env
        output_path = args[args.index("--output-last-message") + 1]
        assert args[args.index("--ask-for-approval") + 1] == "never"
        assert args[args.index("--sandbox") + 1] == "danger-full-access"
        assert 'model_reasoning_effort="medium"' in args
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(
                '{"status":"ok","run_summary":"Stored teaching.",'
                '"write_count":1,"skipped_items":[],'
                '"read_trace":{"commands":[]},"code_trace":{"files":[]}}'
            )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setenv("SHELLBRAIN_DB_ADMIN_DSN", "postgresql://admin")
    monkeypatch.setattr(
        "app.infrastructure.host_apps.inner_agents.codex_cli.shutil.which",
        _fake_which,
    )
    monkeypatch.setattr(
        "app.infrastructure.host_apps.inner_agents.codex_cli.subprocess.run",
        _fake_run,
    )
    runner = CodexCliInnerAgentRunner(command="codex")

    result = runner.run_teach_knowledge(_teach_knowledge_request(repo_root=str(tmp_path)))

    assert result.status == "ok"
    assert result.write_count == 1
    assert result.run_summary == "Stored teaching."
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
    assert "WRITE CLEARLY\n" in prompt
    assert "Lead with the answer" in prompt
    assert "Summary: max two sentences" in prompt
    assert "Lists: max three items" in prompt
    assert prompt.index("events --json") < prompt.index("read --json")
    assert "Shellbrain is a repo-scoped memory system" in prompt
    assert "# KNOWLEDGE MODEL" in prompt
    assert "Concepts are sparse orientation nodes, not tags" in prompt
    assert "claims become concept orientation" in prompt
    assert "memory_links connect abstract concepts" in prompt
    assert "Run events first" in prompt
    assert "Treat `query` as the\n   complete worker context" in prompt
    assert "Build a compact search text" in prompt
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
    assert '"sources":' not in prompt
    assert "used_in" not in prompt
    assert "must list only commands actually run" in prompt
    assert '\\"evidence\\"' in prompt
    assert "knowledge_builder_notes" not in prompt
    assert "preferred_source_id" not in prompt
    assert "shellbrain --help" in prompt
    assert "read --help" in prompt
    assert "events --help" in prompt
    assert "concept show --help" in prompt
    assert "events --json" in prompt
    assert "read --json" in prompt
    assert "concept show --json" in prompt
    assert "shellbrain recall" in prompt
    assert "memory writes" in prompt
    assert "requested_" "expansions" not in prompt
    assert "candidate_" "context" not in prompt
    assert "expansion_" "handles" not in prompt


def test_build_context_prompt_targets_repo_root_when_available(tmp_path) -> None:
    """Inner-agent prompt should make nested Codex target the parent repo explicitly."""

    prompt = render_build_context_prompt(_request(repo_root=str(tmp_path)))

    assert f"shellbrain --no-sync --repo-root {tmp_path}" in prompt
    assert f"shellbrain --no-sync --repo-root {tmp_path} events --json" in prompt
    assert f"shellbrain --no-sync --repo-root {tmp_path} read --json" in prompt


def test_build_context_synthesis_prompt_uses_only_deterministic_pack() -> None:
    """synthesis prompt should explain graph semantics without Shellbrain commands."""

    prompt = render_build_context_synthesis_prompt(
        _request(
            synthesis_only=True,
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
    assert "Use only the text and metadata present in the pack" in prompt
    assert "The query is the complete worker request" in prompt
    assert '"sources":' not in prompt
    assert "deterministic source provenance" not in prompt
    assert "mem-1" in prompt
    assert "shellbrain read --json" not in prompt


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
    assert "snapshot-backed solution delta" in prompt
    assert "code_delta_context" in prompt
    assert "sharpen solution/change memories" in prompt
    assert "Do not dump raw\n  changed-file lists" in prompt
    assert "`shellbrain snapshot`" in prompt
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
    assert "structural_memory_relations" in prompt
    assert "problem_attempts" not in prompt
    assert "links.problem_id" in prompt
    assert "Treat idle-stable episodes as partial" in prompt
    assert "Do not mark historically true memories wrong" in " ".join(prompt.split())
    assert "do not vote on ordinary" in prompt.lower()
    assert "leave the memory unlinked" in prompt
    assert "update_lifecycle" in prompt
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
    assert "snapshot" not in prompt.split('"help_commands"')[1].split('"command_lexicon"')[0]
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


def test_teach_knowledge_prompt_is_separate_and_immediate(tmp_path) -> None:
    """Teach prompt should not reuse the session build protocol."""

    prompt = render_teach_knowledge_prompt(
        _teach_knowledge_request(repo_root=str(tmp_path))
    )

    assert "# IDENTITY" in prompt
    assert "teach_knowledge" in prompt
    assert "teaching text is already the evidence" in prompt
    assert "Do not run the session build_knowledge" in prompt
    assert "shellbrain events --json" not in prompt
    assert "scenario record --json" not in prompt
    assert "Forbidden: `shellbrain events`, `shellbrain scenario record`" in prompt
    assert "teaching_event_id" in prompt
    assert "teaching-evt-1" in prompt
    assert f"shellbrain --repo-root {tmp_path} read --json" in prompt
    assert f"shellbrain --repo-root {tmp_path} memory add --json" in prompt
    assert f"shellbrain --repo-root {tmp_path} concept update --json" in prompt
    assert "Run the exact `first_command`" not in prompt
    assert "Segment the episode into memory boundaries" not in prompt
    assert "Concept graph records:" in prompt
    assert "definition, behavior, invariant" in prompt
    assert "contains, involves" in prompt
    assert "Use memory links for concept-to-memory bridges" in prompt
    assert "created_by `manual`" in prompt
    assert "Use current_problem only to interpret" in prompt
    assert "If max_shellbrain_reads allows it" in prompt
    assert "read budget is zero" in prompt
    assert "Prefer updating aliases or scope_note" in prompt
    assert "source_kind\":\"transcript_event" in prompt
    assert "memory update` sparingly" in prompt
    assert "stale or disputed item is a concept claim" in prompt
    assert "Do not mark historically true memories wrong" in " ".join(prompt.split())
    assert "You may write Shellbrain only through:" in prompt
    assert "`shellbrain memory add`" in prompt
    assert "`shellbrain concept update`" in prompt
    assert "Before `add_relation`, ensure both subject and object concepts exist" in prompt
    assert "not framed as a revision" in prompt
    assert "Write both a memory and a concept claim only when each has independent future" in prompt
    assert "multiple independent durable instructions" in prompt
    assert "Prefer pytest-style tests" in prompt
    assert "Failed deposit address lookups must not be cached" in prompt
    assert "Concept container with scope and alias" in prompt
    assert '"type":"add_concept"' in prompt
    assert '"aliases":["deposit lookup","depository lookup"]' in prompt
    assert "Concept relation when the teaching explicitly relates two concepts" in prompt
    assert '"type":"add_relation"' in prompt
    assert "Grounding after narrow verification of a named anchor" in prompt
    assert '"type":"add_grounding"' in prompt
    assert "Concept-memory link when the memory explains the concept" in prompt
    assert '"type":"link_memory"' in prompt


def _request(
    *,
    repo_root: str | None = None,
    synthesis_only: bool = False,
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
        synthesis_only=synthesis_only,
        deterministic_pack=deterministic_pack,
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


def _teach_knowledge_request(*, repo_root: str = "/tmp/repo") -> TeachKnowledgeAgentRequest:
    return TeachKnowledgeAgentRequest(
        run_id="run-1",
        provider="codex",
        model="gpt-5.4-mini",
        reasoning="medium",
        timeout_seconds=600,
        repo_id="repo-a",
        repo_root=repo_root,
        episode_id="episode-1",
        teaching_event_id="teaching-evt-1",
        teaching_event_seq=4,
        teaching_text="Startup wires dependencies but should not own workflow behavior.",
        current_problem={
            "goal": "record architecture preference",
            "surface": "startup",
            "obstacle": "agents may put behavior in startup",
            "hypothesis": "store a preference",
        },
        max_shellbrain_reads=6,
        max_code_files=5,
        max_write_commands=12,
    )


def _disabled_feature(args: list[str], feature: str) -> bool:
    return any(
        left == "--disable" and right == feature
        for left, right in zip(args, args[1:], strict=False)
    )
