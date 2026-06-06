"""Codex CLI-backed inner-agent provider adapter."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from time import perf_counter

from app.core.ports.host_apps.inner_agents import (
    BuildKnowledgeAgentRequest,
    BuildKnowledgeAgentResult,
    InnerAgentRunRequest,
    InnerAgentRunResult,
    TeachKnowledgeAgentRequest,
    WikiSummaryAgentRequest,
    WikiSummaryAgentResult,
)
from app.infrastructure.host_apps.inner_agents.output_parser import (
    InnerAgentOutputParseError,
    parse_build_knowledge_output,
    parse_inner_agent_response_output,
    parse_wiki_summary_output,
)
from app.infrastructure.host_apps.inner_agents.prompt import (
    render_build_context_prompt,
    render_build_context_synthesis_prompt,
    render_build_knowledge_prompt,
    render_teach_knowledge_prompt,
    render_wiki_summary_prompt,
)


# Codex read-only/workspace-write sandboxes block Shellbrain's local Postgres TCP
# connection. Route allowlists are enforced by SHELLBRAIN_INNER_AGENT_MODE.
_CODEX_SANDBOX_MODE = "danger-full-access"
_CODEX_DISABLED_FEATURES = (
    "apps",
    "browser_use",
    "browser_use_external",
    "multi_agent",
    "plugins",
    "skill_mcp_dependency_install",
    "tool_search",
)


class CodexCliInnerAgentRunner:
    """Run build_context synthesis through the local Codex CLI when explicitly allowed."""

    def __init__(
        self,
        *,
        command: str,
    ) -> None:
        """Store provider configuration."""

        self._command = command

    def run(self, request: InnerAgentRunRequest) -> InnerAgentRunResult:
        """Run one Codex CLI synthesis request or return a safe fallback status."""

        command_path = shutil.which(self._command)
        if command_path is None:
            return _result(
                request,
                status="provider_unavailable",
                fallback_used=True,
                error_code="command_not_found",
                error_message=f"Codex command not found: {self._command}",
            )

        prompt = (
            render_build_context_synthesis_prompt(request)
            if request.synthesis_only
            else render_build_context_prompt(request)
        )
        started = perf_counter()
        try:
            with (
                tempfile.TemporaryDirectory(
                    prefix="shellbrain-inner-agent-"
                ) as workspace,
                tempfile.NamedTemporaryFile("w+", encoding="utf-8") as output_file,
            ):
                completed = subprocess.run(
                    _codex_exec_args(
                        command_path=command_path,
                        model=request.model,
                        reasoning=request.reasoning,
                        workspace=workspace,
                        output_path=output_file.name,
                    ),
                    input=prompt,
                    text=True,
                    capture_output=True,
                    timeout=request.timeout_seconds,
                    check=False,
                    env=_inner_agent_env(
                        mode="build_context_synthesis"
                        if request.synthesis_only
                        else "build_context"
                    ),
                )
                output_file.seek(0)
                final_message = output_file.read()
        except subprocess.TimeoutExpired:
            return _result(
                request,
                status="timeout",
                fallback_used=True,
                duration_ms=_duration_ms(started),
                input_tokens=_estimate_tokens(prompt),
                capture_quality="estimated",
                error_code="timeout",
                error_message="Codex CLI timed out",
            )

        duration_ms = _duration_ms(started)
        usage = _usage_from_jsonl(completed.stdout)
        if completed.returncode != 0:
            return _result(
                request,
                status="error",
                fallback_used=True,
                duration_ms=duration_ms,
                **_usage_or_estimate(prompt=prompt, output=final_message, usage=usage),
                error_code="codex_nonzero_exit",
                error_message=_truncate(completed.stderr or completed.stdout, 500),
            )
        try:
            brief, read_trace = parse_inner_agent_response_output(final_message)
        except InnerAgentOutputParseError as exc:
            return _result(
                request,
                status="invalid_output",
                fallback_used=True,
                duration_ms=duration_ms,
                **_usage_or_estimate(prompt=prompt, output=final_message, usage=usage),
                error_code="invalid_output",
                error_message=str(exc),
            )
        return _result(
            request,
            status="ok",
            brief=brief,
            duration_ms=duration_ms,
            **_usage_or_estimate(prompt=prompt, output=final_message, usage=usage),
            read_trace=read_trace,
        )

    def run_build_knowledge(
        self, request: BuildKnowledgeAgentRequest
    ) -> BuildKnowledgeAgentResult:
        """Run one Codex CLI build_knowledge request."""

        command_path = shutil.which(self._command)
        if command_path is None:
            return _build_knowledge_result(
                request,
                status="provider_unavailable",
                error_code="command_not_found",
                error_message=f"Codex command not found: {self._command}",
            )

        prompt = render_build_knowledge_prompt(request)
        started = perf_counter()
        try:
            with (
                tempfile.TemporaryDirectory(
                    prefix="shellbrain-inner-agent-"
                ) as workspace,
                tempfile.NamedTemporaryFile("w+", encoding="utf-8") as output_file,
            ):
                completed = subprocess.run(
                    _codex_exec_args(
                        command_path=command_path,
                        model=request.model,
                        reasoning=request.reasoning,
                        workspace=workspace,
                        output_path=output_file.name,
                    ),
                    input=prompt,
                    text=True,
                    capture_output=True,
                    timeout=request.timeout_seconds,
                    check=False,
                    env=_inner_agent_env(
                        mode="build_knowledge",
                        knowledge_build_run_id=request.run_id,
                    ),
                )
                output_file.seek(0)
                final_message = output_file.read()
        except subprocess.TimeoutExpired:
            return _build_knowledge_result(
                request,
                status="timeout",
                duration_ms=_duration_ms(started),
                input_tokens=_estimate_tokens(prompt),
                capture_quality="estimated",
                error_code="timeout",
                error_message="Codex CLI timed out",
            )

        duration_ms = _duration_ms(started)
        usage = _usage_from_jsonl(completed.stdout)
        if completed.returncode != 0:
            return _build_knowledge_result(
                request,
                status="error",
                duration_ms=duration_ms,
                **_usage_or_estimate(prompt=prompt, output=final_message, usage=usage),
                error_code="codex_nonzero_exit",
                error_message=_truncate(completed.stderr or completed.stdout, 500),
            )
        try:
            parsed = parse_build_knowledge_output(final_message)
        except InnerAgentOutputParseError as exc:
            return _build_knowledge_result(
                request,
                status="invalid_output",
                duration_ms=duration_ms,
                **_usage_or_estimate(prompt=prompt, output=final_message, usage=usage),
                error_code="invalid_output",
                error_message=str(exc),
            )
        return _build_knowledge_result(
            request,
            status=parsed["status"],
            duration_ms=duration_ms,
            **_usage_or_estimate(prompt=prompt, output=final_message, usage=usage),
            write_count=int(parsed["write_count"]),
            skipped_item_count=int(parsed["skipped_item_count"]),
            run_summary=parsed["run_summary"],
            read_trace=parsed["read_trace"],
            code_trace=parsed["code_trace"],
        )

    def run_teach_knowledge(
        self, request: TeachKnowledgeAgentRequest
    ) -> BuildKnowledgeAgentResult:
        """Run one Codex CLI teach_knowledge request."""

        command_path = shutil.which(self._command)
        if command_path is None:
            return _build_knowledge_result(
                request,
                status="provider_unavailable",
                error_code="command_not_found",
                error_message=f"Codex command not found: {self._command}",
            )

        prompt = render_teach_knowledge_prompt(request)
        started = perf_counter()
        try:
            with (
                tempfile.TemporaryDirectory(
                    prefix="shellbrain-inner-agent-"
                ) as workspace,
                tempfile.NamedTemporaryFile("w+", encoding="utf-8") as output_file,
            ):
                completed = subprocess.run(
                    _codex_exec_args(
                        command_path=command_path,
                        model=request.model,
                        reasoning=request.reasoning,
                        workspace=workspace,
                        output_path=output_file.name,
                    ),
                    input=prompt,
                    text=True,
                    capture_output=True,
                    timeout=request.timeout_seconds,
                    check=False,
                    env=_inner_agent_env(
                        mode="teach",
                        knowledge_build_run_id=request.run_id,
                    ),
                )
                output_file.seek(0)
                final_message = output_file.read()
        except subprocess.TimeoutExpired:
            return _build_knowledge_result(
                request,
                status="timeout",
                duration_ms=_duration_ms(started),
                input_tokens=_estimate_tokens(prompt),
                capture_quality="estimated",
                error_code="timeout",
                error_message="Codex CLI timed out",
            )

        duration_ms = _duration_ms(started)
        usage = _usage_from_jsonl(completed.stdout)
        if completed.returncode != 0:
            return _build_knowledge_result(
                request,
                status="error",
                duration_ms=duration_ms,
                **_usage_or_estimate(prompt=prompt, output=final_message, usage=usage),
                error_code="codex_nonzero_exit",
                error_message=_truncate(completed.stderr or completed.stdout, 500),
            )
        try:
            parsed = parse_build_knowledge_output(final_message)
        except InnerAgentOutputParseError as exc:
            return _build_knowledge_result(
                request,
                status="invalid_output",
                duration_ms=duration_ms,
                **_usage_or_estimate(prompt=prompt, output=final_message, usage=usage),
                error_code="invalid_output",
                error_message=str(exc),
            )
        return _build_knowledge_result(
            request,
            status=parsed["status"],
            duration_ms=duration_ms,
            **_usage_or_estimate(prompt=prompt, output=final_message, usage=usage),
            write_count=int(parsed["write_count"]),
            skipped_item_count=int(parsed["skipped_item_count"]),
            run_summary=parsed["run_summary"],
            read_trace=parsed["read_trace"],
            code_trace=parsed["code_trace"],
        )

    def run_wiki_summary(
        self, request: WikiSummaryAgentRequest
    ) -> WikiSummaryAgentResult:
        """Run one Codex CLI wiki_summary request."""

        command_path = shutil.which(self._command)
        if command_path is None:
            return _wiki_summary_result(
                request,
                status="provider_unavailable",
                error_code="command_not_found",
                error_message=f"Codex command not found: {self._command}",
            )

        prompt = render_wiki_summary_prompt(request)
        started = perf_counter()
        try:
            with (
                tempfile.TemporaryDirectory(
                    prefix="shellbrain-inner-agent-"
                ) as workspace,
                tempfile.NamedTemporaryFile("w+", encoding="utf-8") as output_file,
            ):
                completed = subprocess.run(
                    _codex_exec_args(
                        command_path=command_path,
                        model=request.model,
                        reasoning=request.reasoning,
                        workspace=workspace,
                        output_path=output_file.name,
                    ),
                    input=prompt,
                    text=True,
                    capture_output=True,
                    timeout=request.timeout_seconds,
                    check=False,
                    env=_inner_agent_env(mode="wiki_summary"),
                )
                output_file.seek(0)
                final_message = output_file.read()
        except subprocess.TimeoutExpired:
            return _wiki_summary_result(
                request,
                status="timeout",
                duration_ms=_duration_ms(started),
                input_tokens=_estimate_tokens(prompt),
                capture_quality="estimated",
                error_code="timeout",
                error_message="Codex CLI timed out",
            )

        duration_ms = _duration_ms(started)
        usage = _usage_from_jsonl(completed.stdout)
        if completed.returncode != 0:
            return _wiki_summary_result(
                request,
                status="error",
                duration_ms=duration_ms,
                **_usage_or_estimate(prompt=prompt, output=final_message, usage=usage),
                error_code="codex_nonzero_exit",
                error_message=_truncate(completed.stderr or completed.stdout, 500),
            )
        try:
            body = parse_wiki_summary_output(final_message)
        except InnerAgentOutputParseError as exc:
            return _wiki_summary_result(
                request,
                status="invalid_output",
                duration_ms=duration_ms,
                **_usage_or_estimate(prompt=prompt, output=final_message, usage=usage),
                error_code="invalid_output",
                error_message=str(exc),
            )
        return _wiki_summary_result(
            request,
            status="ok",
            body=body,
            duration_ms=duration_ms,
            **_usage_or_estimate(prompt=prompt, output=final_message, usage=usage),
        )


def _codex_exec_args(
    *,
    command_path: str,
    model: str,
    reasoning: str,
    workspace: str,
    output_path: str,
) -> list[str]:
    """Return the Codex exec command for a Shellbrain-controlled inner agent."""

    args = [
        command_path,
        "--ask-for-approval",
        "never",
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
    ]
    for feature in _CODEX_DISABLED_FEATURES:
        args.extend(["--disable", feature])
    args.extend(
        [
            "--sandbox",
            _CODEX_SANDBOX_MODE,
            "--model",
            model,
            "-c",
            f'model_reasoning_effort="{reasoning}"',
            "--cd",
            workspace,
            "--json",
            "--output-last-message",
            output_path,
            "-",
        ]
    )
    return args


def _result(
    request: InnerAgentRunRequest,
    *,
    status,
    brief: dict | None = None,
    fallback_used: bool = False,
    duration_ms: int = 0,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    reasoning_output_tokens: int | None = None,
    cached_input_tokens_total: int | None = None,
    capture_quality: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    read_trace: dict | None = None,
) -> InnerAgentRunResult:
    """Build one provider-neutral result."""

    return InnerAgentRunResult(
        status=status,
        provider=request.provider,
        model=request.model,
        reasoning=request.reasoning,
        brief=brief,
        fallback_used=fallback_used,
        timeout_seconds=request.timeout_seconds,
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_output_tokens=reasoning_output_tokens,
        cached_input_tokens_total=cached_input_tokens_total,
        capture_quality=capture_quality,
        error_code=error_code,
        error_message=error_message,
        read_trace=read_trace or {},
    )


def _build_knowledge_result(
    request: BuildKnowledgeAgentRequest | TeachKnowledgeAgentRequest,
    *,
    status,
    duration_ms: int = 0,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    reasoning_output_tokens: int | None = None,
    cached_input_tokens_total: int | None = None,
    capture_quality: str | None = None,
    write_count: int = 0,
    skipped_item_count: int = 0,
    error_code: str | None = None,
    error_message: str | None = None,
    run_summary: str | None = None,
    read_trace: dict | None = None,
    code_trace: dict | None = None,
) -> BuildKnowledgeAgentResult:
    """Build one provider-neutral build_knowledge result."""

    return BuildKnowledgeAgentResult(
        status=status,
        provider=request.provider,
        model=request.model,
        reasoning=request.reasoning,
        timeout_seconds=request.timeout_seconds,
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_output_tokens=reasoning_output_tokens,
        cached_input_tokens_total=cached_input_tokens_total,
        capture_quality=capture_quality,
        write_count=write_count,
        skipped_item_count=skipped_item_count,
        error_code=error_code,
        error_message=error_message,
        run_summary=run_summary,
        read_trace=read_trace or {},
        code_trace=code_trace or {},
    )


def _wiki_summary_result(
    request: WikiSummaryAgentRequest,
    *,
    status,
    body: str | None = None,
    duration_ms: int = 0,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    reasoning_output_tokens: int | None = None,
    cached_input_tokens_total: int | None = None,
    capture_quality: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> WikiSummaryAgentResult:
    """Build one provider-neutral wiki summary result."""

    return WikiSummaryAgentResult(
        status=status,
        provider=request.provider,
        model=request.model,
        reasoning=request.reasoning,
        timeout_seconds=request.timeout_seconds,
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_output_tokens=reasoning_output_tokens,
        cached_input_tokens_total=cached_input_tokens_total,
        capture_quality=capture_quality,
        body=body,
        error_code=error_code,
        error_message=error_message,
    )


def _duration_ms(started: float) -> int:
    """Return elapsed milliseconds from one perf-counter timestamp."""

    return int((perf_counter() - started) * 1000)


def _usage_from_jsonl(output: str) -> dict[str, int] | None:
    """Parse the final Codex JSON event usage payload when available."""

    usage: dict[str, int] | None = None
    for line in output.splitlines():
        text = line.strip()
        if not text.startswith("{"):
            continue
        try:
            event = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "turn.completed":
            continue
        payload = event.get("usage")
        if not isinstance(payload, dict):
            continue
        usage = {
            key: int(value)
            for key, value in payload.items()
            if isinstance(value, int) and value >= 0
        }
    return usage


def _usage_or_estimate(
    *, prompt: str, output: str, usage: dict[str, int] | None
) -> dict[str, int | str | None]:
    """Return exact Codex usage fields, falling back to local estimates."""

    if usage is not None:
        return {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "reasoning_output_tokens": usage.get("reasoning_output_tokens"),
            "cached_input_tokens_total": usage.get("cached_input_tokens"),
            "capture_quality": "exact",
        }
    return {
        "input_tokens": _estimate_tokens(prompt),
        "output_tokens": _estimate_tokens(output),
        "reasoning_output_tokens": None,
        "cached_input_tokens_total": None,
        "capture_quality": "estimated",
    }


def _inner_agent_env(
    *, mode: str, knowledge_build_run_id: str | None = None
) -> dict[str, str]:
    """Return the subprocess environment with inner-agent CLI mode enabled."""

    env = dict(os.environ)
    env["SHELLBRAIN_INNER_AGENT_MODE"] = mode
    _inherit_parent_caller_identity(env)
    if mode in {"build_knowledge", "teach", "wiki_summary"}:
        if knowledge_build_run_id:
            env["SHELLBRAIN_KNOWLEDGE_BUILD_RUN_ID"] = knowledge_build_run_id
        _scrub_admin_env(env)
    else:
        env.pop("SHELLBRAIN_KNOWLEDGE_BUILD_RUN_ID", None)
    return env


def _inherit_parent_caller_identity(env: dict[str, str]) -> None:
    """Preserve the outer host identity across a nested Codex inner-agent run."""

    if env.get("CODEX_THREAD_ID"):
        env["SHELLBRAIN_PARENT_HOST_APP"] = "codex"
        env["SHELLBRAIN_PARENT_HOST_SESSION_KEY"] = env["CODEX_THREAD_ID"]
        env.pop("SHELLBRAIN_PARENT_AGENT_KEY", None)
        env.pop("SHELLBRAIN_PARENT_TRANSCRIPT_PATH", None)
        return
    if env.get("SHELLBRAIN_HOST_APP") and env.get("SHELLBRAIN_HOST_SESSION_KEY"):
        env["SHELLBRAIN_PARENT_HOST_APP"] = env["SHELLBRAIN_HOST_APP"]
        env["SHELLBRAIN_PARENT_HOST_SESSION_KEY"] = env["SHELLBRAIN_HOST_SESSION_KEY"]
        if env.get("SHELLBRAIN_AGENT_KEY"):
            env["SHELLBRAIN_PARENT_AGENT_KEY"] = env["SHELLBRAIN_AGENT_KEY"]
        if env.get("SHELLBRAIN_TRANSCRIPT_PATH"):
            env["SHELLBRAIN_PARENT_TRANSCRIPT_PATH"] = env["SHELLBRAIN_TRANSCRIPT_PATH"]


def _scrub_admin_env(env: dict[str, str]) -> None:
    """Remove administrative/destructive DB credentials from provider env."""

    for name in (
        "SHELLBRAIN_DB_ADMIN_DSN",
        "SHELLBRAIN_ADMIN_DSN",
        "SHELLBRAIN_PROTECTED_LIVE_DSN",
        "SHELLBRAIN_ALLOW_DESTRUCTIVE",
        "SHELLBRAIN_CONFIRM_RESTORE",
    ):
        env.pop(name, None)


def _estimate_tokens(value: str) -> int:
    """Return a stable rough token estimate for telemetry."""

    return max(0, (len(value) + 3) // 4)


def _truncate(value: str, max_chars: int) -> str:
    """Return compact diagnostic text."""

    collapsed = " ".join(value.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return f"{collapsed[: max_chars - 3].rstrip()}..."
