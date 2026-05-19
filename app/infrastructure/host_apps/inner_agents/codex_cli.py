"""Codex CLI-backed inner-agent provider adapter."""

from __future__ import annotations

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
)
from app.infrastructure.host_apps.inner_agents.output_parser import (
    InnerAgentOutputParseError,
    parse_build_knowledge_output,
    parse_inner_agent_response_output,
)
from app.infrastructure.host_apps.inner_agents.prompt import (
    render_build_context_prompt,
    render_build_knowledge_prompt,
)


# Codex read-only/workspace-write sandboxes block Shellbrain's local Postgres TCP
# connection. Route allowlists are enforced by SHELLBRAIN_INNER_AGENT_MODE.
_CODEX_SANDBOX_MODE = "danger-full-access"


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

        prompt = render_build_context_prompt(request)
        started = perf_counter()
        try:
            with (
                tempfile.TemporaryDirectory(
                    prefix="shellbrain-inner-agent-"
                ) as workspace,
                tempfile.NamedTemporaryFile("w+", encoding="utf-8") as output_file,
            ):
                completed = subprocess.run(
                    [
                        command_path,
                        "--ask-for-approval",
                        "never",
                        "exec",
                        "--ephemeral",
                        "--ignore-rules",
                        "--skip-git-repo-check",
                        "--sandbox",
                        _CODEX_SANDBOX_MODE,
                        "--model",
                        request.model,
                        "-c",
                        f'model_reasoning_effort="{request.reasoning}"',
                        "--cd",
                        workspace,
                        "--output-last-message",
                        output_file.name,
                        "-",
                    ],
                    input=prompt,
                    text=True,
                    capture_output=True,
                    timeout=request.timeout_seconds,
                    check=False,
                    env=_inner_agent_env(mode="build_context"),
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
        if completed.returncode != 0:
            return _result(
                request,
                status="error",
                fallback_used=True,
                duration_ms=duration_ms,
                input_tokens=_estimate_tokens(prompt),
                capture_quality="estimated",
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
                input_tokens=_estimate_tokens(prompt),
                output_tokens=_estimate_tokens(final_message),
                capture_quality="estimated",
                error_code="invalid_output",
                error_message=str(exc),
            )
        return _result(
            request,
            status="ok",
            brief=brief,
            duration_ms=duration_ms,
            input_tokens=_estimate_tokens(prompt),
            output_tokens=_estimate_tokens(final_message),
            capture_quality="estimated",
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
                    [
                        command_path,
                        "--ask-for-approval",
                        "never",
                        "exec",
                        "--ephemeral",
                        "--ignore-rules",
                        "--skip-git-repo-check",
                        "--sandbox",
                        _CODEX_SANDBOX_MODE,
                        "--model",
                        request.model,
                        "-c",
                        f'model_reasoning_effort="{request.reasoning}"',
                        "--cd",
                        workspace,
                        "--output-last-message",
                        output_file.name,
                        "-",
                    ],
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
        if completed.returncode != 0:
            return _build_knowledge_result(
                request,
                status="error",
                duration_ms=duration_ms,
                input_tokens=_estimate_tokens(prompt),
                capture_quality="estimated",
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
                input_tokens=_estimate_tokens(prompt),
                output_tokens=_estimate_tokens(final_message),
                capture_quality="estimated",
                error_code="invalid_output",
                error_message=str(exc),
            )
        return _build_knowledge_result(
            request,
            status=parsed["status"],
            duration_ms=duration_ms,
            input_tokens=_estimate_tokens(prompt),
            output_tokens=_estimate_tokens(final_message),
            capture_quality="estimated",
            write_count=int(parsed["write_count"]),
            skipped_item_count=int(parsed["skipped_item_count"]),
            run_summary=parsed["run_summary"],
            read_trace=parsed["read_trace"],
            code_trace=parsed["code_trace"],
        )


def _result(
    request: InnerAgentRunRequest,
    *,
    status,
    brief: dict | None = None,
    fallback_used: bool = False,
    duration_ms: int = 0,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
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
        capture_quality=capture_quality,
        error_code=error_code,
        error_message=error_message,
        read_trace=read_trace or {},
    )


def _build_knowledge_result(
    request: BuildKnowledgeAgentRequest,
    *,
    status,
    duration_ms: int = 0,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
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
        capture_quality=capture_quality,
        write_count=write_count,
        skipped_item_count=skipped_item_count,
        error_code=error_code,
        error_message=error_message,
        run_summary=run_summary,
        read_trace=read_trace or {},
        code_trace=code_trace or {},
    )


def _duration_ms(started: float) -> int:
    """Return elapsed milliseconds from one perf-counter timestamp."""

    return int((perf_counter() - started) * 1000)


def _inner_agent_env(
    *, mode: str, knowledge_build_run_id: str | None = None
) -> dict[str, str]:
    """Return the subprocess environment with inner-agent CLI mode enabled."""

    env = dict(os.environ)
    env["SHELLBRAIN_INNER_AGENT_MODE"] = mode
    _inherit_parent_caller_identity(env)
    if mode == "build_knowledge":
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
