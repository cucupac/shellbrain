"""Claude Code CLI-backed inner-agent provider adapter."""

from __future__ import annotations

import json
import shutil
import subprocess
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
from app.infrastructure.host_apps.inner_agents.codex_cli import (
    _build_knowledge_result,
    _duration_ms,
    _estimate_tokens,
    _inner_agent_env,
    _result,
    _truncate,
    _usage_or_estimate,
    _wiki_summary_result,
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


class ClaudeCliInnerAgentRunner:
    """Run Shellbrain inner-agent work through the local Claude Code CLI."""

    def __init__(self, *, command: str) -> None:
        self._command = command

    def run(self, request: InnerAgentRunRequest) -> InnerAgentRunResult:
        """Run one Claude Code build_context request."""

        prompt = (
            render_build_context_synthesis_prompt(request)
            if request.synthesis_only
            else render_build_context_prompt(request)
        )
        run = self._run_claude(
            request,
            prompt=prompt,
            mode="build_context_synthesis" if request.synthesis_only else "build_context",
            tool_profile="none" if request.synthesis_only else "shellbrain",
        )
        if run["status"] != "ok":
            return _context_error_result(request, run)
        final_message = str(run["result"])
        try:
            brief, read_trace = parse_inner_agent_response_output(final_message)
        except InnerAgentOutputParseError as exc:
            return _result(
                request,
                status="invalid_output",
                fallback_used=True,
                duration_ms=int(run["duration_ms"]),
                **_usage_or_estimate(
                    prompt=prompt, output=final_message, usage=run.get("usage")
                ),
                error_code="invalid_output",
                error_message=str(exc),
            )
        return _result(
            request,
            status="ok",
            brief=brief,
            duration_ms=int(run["duration_ms"]),
            **_usage_or_estimate(
                prompt=prompt, output=final_message, usage=run.get("usage")
            ),
            read_trace=read_trace,
        )

    def run_build_knowledge(
        self, request: BuildKnowledgeAgentRequest
    ) -> BuildKnowledgeAgentResult:
        """Run one Claude Code build_knowledge request."""

        return self._run_knowledge(
            request,
            prompt=render_build_knowledge_prompt(request),
            mode="build_knowledge",
            tool_profile="knowledge",
        )

    def run_teach_knowledge(
        self, request: TeachKnowledgeAgentRequest
    ) -> BuildKnowledgeAgentResult:
        """Run one Claude Code teach request."""

        return self._run_knowledge(
            request,
            prompt=render_teach_knowledge_prompt(request),
            mode="teach",
            tool_profile="shellbrain",
        )

    def _run_knowledge(
        self,
        request: BuildKnowledgeAgentRequest | TeachKnowledgeAgentRequest,
        *,
        prompt: str,
        mode: str,
        tool_profile: str,
    ) -> BuildKnowledgeAgentResult:
        run = self._run_claude(
            request,
            prompt=prompt,
            mode=mode,
            tool_profile=tool_profile,
            knowledge_build_run_id=request.run_id,
        )
        if run["status"] != "ok":
            return _knowledge_error_result(request, run)
        final_message = str(run["result"])
        try:
            parsed = parse_build_knowledge_output(final_message)
        except InnerAgentOutputParseError as exc:
            return _build_knowledge_result(
                request,
                status="invalid_output",
                duration_ms=int(run["duration_ms"]),
                **_usage_or_estimate(
                    prompt=prompt, output=final_message, usage=run.get("usage")
                ),
                error_code="invalid_output",
                error_message=str(exc),
            )
        return _build_knowledge_result(
            request,
            status=parsed["status"],
            duration_ms=int(run["duration_ms"]),
            **_usage_or_estimate(
                prompt=prompt, output=final_message, usage=run.get("usage")
            ),
            write_count=int(parsed["write_count"]),
            skipped_item_count=int(parsed["skipped_item_count"]),
            run_summary=parsed["run_summary"],
            read_trace=parsed["read_trace"],
            code_trace=parsed["code_trace"],
        )

    def run_wiki_summary(
        self, request: WikiSummaryAgentRequest
    ) -> WikiSummaryAgentResult:
        """Run one Claude Code wiki_summary request."""

        prompt = render_wiki_summary_prompt(request)
        run = self._run_claude(
            request,
            prompt=prompt,
            mode="wiki_summary",
            tool_profile="none",
        )
        if run["status"] != "ok":
            return _wiki_error_result(request, run)
        final_message = str(run["result"])
        try:
            body = parse_wiki_summary_output(final_message)
        except InnerAgentOutputParseError as exc:
            return _wiki_summary_result(
                request,
                status="invalid_output",
                duration_ms=int(run["duration_ms"]),
                **_usage_or_estimate(
                    prompt=prompt, output=final_message, usage=run.get("usage")
                ),
                error_code="invalid_output",
                error_message=str(exc),
            )
        return _wiki_summary_result(
            request,
            status="ok",
            body=body,
            duration_ms=int(run["duration_ms"]),
            **_usage_or_estimate(
                prompt=prompt, output=final_message, usage=run.get("usage")
            ),
        )

    def _run_claude(
        self,
        request,
        *,
        prompt: str,
        mode: str,
        tool_profile: str,
        knowledge_build_run_id: str | None = None,
    ) -> dict[str, object]:
        command_path = shutil.which(self._command)
        if command_path is None:
            return {
                "status": "provider_unavailable",
                "error_code": "command_not_found",
                "error_message": f"Claude command not found: {self._command}",
            }
        started = perf_counter()
        try:
            completed = subprocess.run(
                _claude_args(
                    command_path=command_path,
                    model=request.model,
                    reasoning=request.reasoning,
                    tool_profile=tool_profile,
                ),
                input=prompt,
                text=True,
                capture_output=True,
                timeout=request.timeout_seconds,
                check=False,
                env=_inner_agent_env(
                    mode=mode,
                    knowledge_build_run_id=knowledge_build_run_id,
                ),
            )
        except subprocess.TimeoutExpired:
            return _claude_error(
                status="timeout",
                duration_ms=_duration_ms(started),
                prompt=prompt,
                error_code="timeout",
                error_message="Claude CLI timed out",
            )

        duration_ms = _duration_ms(started)
        if completed.returncode != 0:
            return _claude_error(
                status="error",
                duration_ms=duration_ms,
                prompt=prompt,
                error_code="claude_nonzero_exit",
                error_message=_truncate(completed.stderr or completed.stdout, 500),
            )
        envelope = _claude_envelope(completed.stdout, allowed_model=request.model)
        if envelope.get("error_code"):
            return _claude_error(
                status=str(envelope["status"]),
                duration_ms=duration_ms,
                prompt=prompt,
                error_code=str(envelope["error_code"]),
                error_message=str(envelope["error_message"]),
            )
        return {
            "status": "ok",
            "result": envelope["result"],
            "usage": envelope.get("usage"),
            "duration_ms": duration_ms,
        }


def _claude_error(
    *,
    status: str,
    duration_ms: int,
    prompt: str,
    error_code: str,
    error_message: str,
) -> dict[str, object]:
    return {
        "status": status,
        "duration_ms": duration_ms,
        "input_tokens": _estimate_tokens(prompt),
        "capture_quality": "estimated",
        "error_code": error_code,
        "error_message": error_message,
    }


def _context_error_result(
    request: InnerAgentRunRequest, run: dict[str, object]
) -> InnerAgentRunResult:
    return _result(
        request,
        status=str(run["status"]),
        fallback_used=True,
        duration_ms=int(run.get("duration_ms") or 0),
        input_tokens=run.get("input_tokens"),
        capture_quality=run.get("capture_quality"),
        error_code=str(run["error_code"]),
        error_message=str(run["error_message"]),
    )


def _knowledge_error_result(
    request: BuildKnowledgeAgentRequest | TeachKnowledgeAgentRequest,
    run: dict[str, object],
) -> BuildKnowledgeAgentResult:
    return _build_knowledge_result(
        request,
        status=str(run["status"]),
        duration_ms=int(run.get("duration_ms") or 0),
        input_tokens=run.get("input_tokens"),
        capture_quality=run.get("capture_quality"),
        error_code=str(run["error_code"]),
        error_message=str(run["error_message"]),
    )


def _wiki_error_result(
    request: WikiSummaryAgentRequest, run: dict[str, object]
) -> WikiSummaryAgentResult:
    return _wiki_summary_result(
        request,
        status=str(run["status"]),
        duration_ms=int(run.get("duration_ms") or 0),
        input_tokens=run.get("input_tokens"),
        capture_quality=run.get("capture_quality"),
        error_code=str(run["error_code"]),
        error_message=str(run["error_message"]),
    )


def _claude_args(
    *,
    command_path: str,
    model: str,
    reasoning: str,
    tool_profile: str,
) -> list[str]:
    """Return the Claude Code print-mode command for one inner-agent run."""

    args = [
        command_path,
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--safe-mode",
        "--model",
        model,
        "--settings",
        json.dumps(
            {
                "model": model,
                "availableModels": [model],
                "enforceAvailableModels": True,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        "--effort",
        _claude_effort(reasoning),
        "--strict-mcp-config",
        "--disallowedTools",
        "mcp__*",
    ]
    args.extend(_claude_tool_args(tool_profile))
    return args


def _claude_tool_args(tool_profile: str) -> list[str]:
    if tool_profile == "none":
        return ["--tools", ""]
    if tool_profile == "knowledge":
        return [
            "--tools",
            "Bash,Read,Grep,Glob",
            "--allowedTools",
            "Bash(shellbrain *)",
            "Read",
            "Grep",
            "Glob",
        ]
    return ["--tools", "Bash", "--allowedTools", "Bash(shellbrain *)"]


def _claude_effort(reasoning: str) -> str:
    if reasoning in {"low", "medium", "high", "xhigh"}:
        return reasoning
    return "low"


def _claude_envelope(output: str, *, allowed_model: str) -> dict[str, object]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return {
            "status": "invalid_output",
            "error_code": "claude_invalid_json",
            "error_message": "Claude output is not valid JSON",
        }
    if not isinstance(payload, dict):
        return {
            "status": "invalid_output",
            "error_code": "claude_invalid_json",
            "error_message": "Claude output must be a JSON object",
        }
    disallowed_model = _disallowed_reported_model(payload, allowed_model=allowed_model)
    if disallowed_model is not None:
        return {
            "status": "error",
            "error_code": "claude_disallowed_model",
            "error_message": f"Claude reported disallowed model: {disallowed_model}",
        }
    result = payload.get("result")
    if not isinstance(result, str):
        return {
            "status": "invalid_output",
            "error_code": "claude_missing_result",
            "error_message": "Claude output must include a string result",
        }
    return {"result": result, "usage": _claude_usage(payload)}


def _disallowed_reported_model(
    payload: dict[str, object], *, allowed_model: str
) -> str | None:
    for model in _reported_models(payload):
        normalized = model.lower()
        if allowed_model.lower() not in normalized:
            return model
    return None


def _reported_models(payload: dict[str, object]) -> list[str]:
    models: list[str] = []
    for key in ("model", "active_model", "activeModel"):
        value = payload.get(key)
        if isinstance(value, str):
            models.append(value)
    model_usage = payload.get("modelUsage")
    if isinstance(model_usage, dict):
        for key, value in model_usage.items():
            if isinstance(key, str) and "model" in key.lower() and isinstance(value, str):
                models.append(value)
    return models


def _claude_usage(payload: dict[str, object]) -> dict[str, int] | None:
    source = payload.get("usage")
    if not isinstance(source, dict):
        source = payload.get("modelUsage")
    if not isinstance(source, dict):
        return None
    usage = {
        "input_tokens": _first_int(source, "input_tokens", "inputTokens"),
        "output_tokens": _first_int(source, "output_tokens", "outputTokens"),
        "reasoning_output_tokens": _first_int(
            source,
            "reasoning_output_tokens",
            "reasoningOutputTokens",
            "thinking_tokens",
        ),
        "cached_input_tokens": _first_int(
            source,
            "cached_input_tokens",
            "cachedInputTokens",
            "cache_read_input_tokens",
        ),
    }
    return usage if any(value is not None for value in usage.values()) else None


def _first_int(value: dict[object, object], *names: str) -> int | None:
    for name in names:
        item = value.get(name)
        if isinstance(item, int) and item >= 0:
            return item
    return None
