"""Verify the Inception trust boundary without network access."""

import io
import json
from urllib.error import HTTPError, URLError

import pytest

from app.core.ports.host_apps.inner_agents import InnerAgentRunRequest
from app.infrastructure.host_apps.inner_agents.inception_api import (
    InceptionApiInnerAgentRunner,
)
from app.infrastructure.host_apps.inner_agents import inception_api


def request():
    return InnerAgentRunRequest(
        agent_name="build_context",
        provider="inception",
        model="mercury-2.5",
        reasoning="instant",
        timeout_seconds=10,
        max_brief_tokens=500,
        query="Fix write timeouts",
        deterministic_pack={"memories": []},
    )


def response():
    brief = {"memories": ["Check the lock owner first."], "code": []}
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": json.dumps(brief)},
            }
        ],
        "usage": {
            "prompt_tokens": 200,
            "completion_tokens": 80,
            "completion_tokens_details": {"reasoning_tokens": 30},
            "prompt_tokens_details": {"cached_tokens": 100},
        },
    }


def test_request_and_usage(monkeypatch):
    def send(req, *, timeout):
        payload = json.loads(req.data)
        assert req.full_url == "https://api.inceptionlabs.ai/v1/chat/completions"
        assert req.get_header("Authorization") == "Bearer test-key"
        assert timeout == 10
        assert payload["reasoning_effort"] == "instant"
        assert payload["max_completion_tokens"] > 500
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["strict"] is True
        return io.BytesIO(json.dumps(response()).encode())

    monkeypatch.setattr(inception_api, "urlopen", send)
    result = InceptionApiInnerAgentRunner(api_key="test-key").run(request())
    assert result.status == "ok" and not result.fallback_used
    assert result.reasoning == "instant"
    assert result.input_tokens == 200
    assert result.output_tokens == 80
    assert result.reasoning_output_tokens == 30
    assert result.cached_input_tokens_total == 100
    assert result.capture_quality == "exact"


@pytest.mark.parametrize(
    "error,code",
    [
        (HTTPError("url", 401, "secret response", {}, None), "authentication_failed"),
        (HTTPError("url", 429, "secret response", {}, None), "rate_limited"),
        (TimeoutError("secret"), "timeout"),
        (URLError("secret"), "provider_unavailable"),
    ],
)
def test_failures_are_explicit_and_redacted(monkeypatch, error, code):
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise error

    monkeypatch.setattr(inception_api, "urlopen", fail)
    result = InceptionApiInnerAgentRunner(api_key="test-key").run(request())
    assert result.error_code == code and not result.fallback_used
    assert "secret" not in result.error_message
    assert len(calls) == 1


@pytest.mark.parametrize(
    "invalid",
    [
        "truncated",
        "missing_section",
        "wrong_section_type",
        "invalid_json",
        "missing_choices",
    ],
)
def test_invalid_output_is_rejected(monkeypatch, invalid):
    data = response()
    if invalid == "truncated":
        data["choices"][0]["finish_reason"] = "length"
    elif invalid == "missing_choices":
        data = {}
    elif invalid == "invalid_json":
        data["choices"][0]["message"]["content"] = "not json"
    else:
        content = json.loads(data["choices"][0]["message"]["content"])
        if invalid == "missing_section":
            del content["memories"]
        else:
            content["memories"] = "not a list"
        data["choices"][0]["message"]["content"] = json.dumps(content)
    monkeypatch.setattr(
        inception_api, "urlopen", lambda *a, **kw: io.BytesIO(json.dumps(data).encode())
    )
    result = InceptionApiInnerAgentRunner(api_key="test-key").run(request())
    assert result.status == "invalid_output" and not result.fallback_used
