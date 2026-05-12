"""Codex CLI-backed inner-agent provider adapter."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from time import perf_counter

from app.core.ports.host_apps.inner_agents import InnerAgentRunRequest, InnerAgentRunResult
from app.infrastructure.host_apps.inner_agents.output_parser import (
    InnerAgentOutputParseError,
    parse_inner_agent_response_output,
)
from app.infrastructure.host_apps.inner_agents.prompt import render_build_context_prompt


class CodexCliInnerAgentRunner:
    """Run build_context synthesis through the local Codex CLI when explicitly allowed."""

    def __init__(
        self,
        *,
        command: str,
        working_directory: str,
        allow_shellbrain_cli: bool,
    ) -> None:
        """Store provider configuration."""

        self._command = command
        self._working_directory = working_directory
        self._allow_shellbrain_cli = allow_shellbrain_cli

    def run(self, request: InnerAgentRunRequest) -> InnerAgentRunResult:
        """Run one Codex CLI synthesis request or return a safe fallback status."""

        if not self._allow_shellbrain_cli:
            return _result(
                request,
                status="provider_unavailable",
                fallback_used=True,
                error_code="shellbrain_cli_not_allowed",
                error_message=(
                    "Codex CLI provider is configured, but Shellbrain CLI access "
                    "is not allowed"
                ),
            )

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
        cwd = _working_directory(request, configured=self._working_directory)
        started = perf_counter()
        try:
            with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as output_file:
                completed = subprocess.run(
                    [
                        command_path,
                        "exec",
                        "--ephemeral",
                        "--ignore-rules",
                        "--skip-git-repo-check",
                        "--sandbox",
                        "read-only",
                        "--ask-for-approval",
                        "never",
                        "--model",
                        request.model,
                        "-c",
                        f'model_reasoning_effort="{request.reasoning}"',
                        "--cd",
                        str(cwd),
                        "--output-last-message",
                        output_file.name,
                        "-",
                    ],
                    input=prompt,
                    text=True,
                    capture_output=True,
                    timeout=request.timeout_seconds,
                    check=False,
                    env=_inner_agent_env(),
                )
                output_file.seek(0)
                final_message = output_file.read()
        except subprocess.TimeoutExpired:
            return _result(
                request,
                status="timeout",
                fallback_used=True,
                duration_ms=_duration_ms(started),
                input_token_estimate=_estimate_tokens(prompt),
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
                input_token_estimate=_estimate_tokens(prompt),
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
                input_token_estimate=_estimate_tokens(prompt),
                output_token_estimate=_estimate_tokens(final_message),
                error_code="invalid_output",
                error_message=str(exc),
            )
        return _result(
            request,
            status="ok",
            brief=brief,
            duration_ms=duration_ms,
            input_token_estimate=_estimate_tokens(prompt),
            output_token_estimate=_estimate_tokens(final_message),
            read_trace=read_trace,
        )


def _result(
    request: InnerAgentRunRequest,
    *,
    status,
    brief: dict | None = None,
    fallback_used: bool = False,
    duration_ms: int = 0,
    input_token_estimate: int | None = None,
    output_token_estimate: int | None = None,
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
        input_token_estimate=input_token_estimate,
        output_token_estimate=output_token_estimate,
        error_code=error_code,
        error_message=error_message,
        read_trace=read_trace or {},
    )


def _working_directory(request: InnerAgentRunRequest, *, configured: str) -> Path:
    """Resolve the adapter working directory."""

    if configured == "repo_root" and request.repo_root is not None:
        return Path(request.repo_root)
    return Path.cwd()


def _duration_ms(started: float) -> int:
    """Return elapsed milliseconds from one perf-counter timestamp."""

    return int((perf_counter() - started) * 1000)


def _inner_agent_env() -> dict[str, str]:
    """Return the subprocess environment with Shellbrain read-only mode enabled."""

    env = dict(os.environ)
    env["SHELLBRAIN_INNER_AGENT_READ_ONLY"] = "1"
    return env


def _estimate_tokens(value: str) -> int:
    """Return a stable rough token estimate for telemetry."""

    return max(0, (len(value) + 3) // 4)


def _truncate(value: str, max_chars: int) -> str:
    """Return compact diagnostic text."""

    collapsed = " ".join(value.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return f"{collapsed[: max_chars - 3].rstrip()}..."
