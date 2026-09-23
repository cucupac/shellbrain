"""Synthesize recall briefs through Inception's hosted API."""

import json
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.ports.host_apps.inner_agents import (
    RecallBrief,
    InnerAgentRunRequest,
    InnerAgentRunResult,
)
from app.infrastructure.host_apps.inner_agents.output_parser import (
    InnerAgentOutputParseError,
    parse_inner_agent_brief_output,
)
from app.infrastructure.host_apps.inner_agents.prompt import (
    render_build_context_synthesis_prompt,
)


class InceptionApiInnerAgentRunner:
    """Perform one bounded, non-streaming synthesis request without retries."""

    def __init__(self, *, api_key: str) -> None:
        if not api_key.strip():
            raise ValueError("INCEPTION_API_KEY is required")
        self._api_key = api_key

    def run(self, request: InnerAgentRunRequest) -> InnerAgentRunResult:
        """Map HTTP failures and validated output into provider-neutral results."""
        started = perf_counter()
        result = InnerAgentRunResult(
            status="error",
            provider="inception",
            model=request.model,
            reasoning=request.reasoning,
            timeout_seconds=request.timeout_seconds,
        )
        payload = {
            "model": request.model,
            "messages": [
                {
                    "role": "user",
                    "content": render_build_context_synthesis_prompt(request),
                }
            ],
            "reasoning_effort": request.reasoning,
            # Reasoning consumes completion tokens in addition to the visible brief.
            "max_completion_tokens": 2048,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "recall_brief",
                    "strict": True,
                    "schema": RecallBrief.model_json_schema(),
                },
            },
            "stream": False,
        }
        http_request = Request(
            "https://api.inceptionlabs.ai/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            # ponytail: socket timeout only; use a deadline-aware transport if responses trickle.
            with urlopen(http_request, timeout=request.timeout_seconds) as response:
                data = json.load(response)
            choice = data["choices"][0]
            if choice["finish_reason"] != "stop":
                raise InnerAgentOutputParseError("Inception did not complete the brief")
            result.brief = parse_inner_agent_brief_output(choice["message"]["content"])
            usage = data.get("usage", {})
            result.input_tokens = usage.get("prompt_tokens")
            result.output_tokens = usage.get("completion_tokens")
            result.reasoning_output_tokens = usage.get(
                "completion_tokens_details", {}
            ).get("reasoning_tokens")
            result.cached_input_tokens_total = usage.get(
                "prompt_tokens_details", {}
            ).get("cached_tokens")
            result.capture_quality = (
                "exact"
                if result.input_tokens is not None and result.output_tokens is not None
                else None
            )
            result = InnerAgentRunResult.model_validate(result.model_dump())
            result.status = "ok"
        except HTTPError as exc:
            result.error_code = {
                401: "authentication_failed",
                403: "authentication_failed",
                429: "rate_limited",
            }.get(exc.code, "http_error")
            result.error_message = f"Inception returned HTTP {exc.code}"
        except (TimeoutError, URLError) as exc:
            timed_out = isinstance(exc, TimeoutError) or isinstance(
                getattr(exc, "reason", None), TimeoutError
            )
            result.status = "timeout" if timed_out else "provider_unavailable"
            result.error_code = result.status
            result.error_message = (
                "Inception request timed out"
                if timed_out
                else "Inception connection failed"
            )
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            result.status = "invalid_output"
            result.error_code = "invalid_output"
            result.error_message = "Inception returned an invalid or incomplete brief"
        result.duration_ms = int((perf_counter() - started) * 1000)
        return result
