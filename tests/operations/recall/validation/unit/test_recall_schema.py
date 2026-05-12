"""Schema contracts for worker recall requests."""

from app.entrypoints.cli.request_parsing.payload_validation import validate_recall_schema


def test_recall_rejects_missing_current_problem() -> None:
    """recall should require structured worker problem context."""

    request, errors = validate_recall_schema({"query": "find migration context"})

    assert request is None
    assert errors
    assert any(error.field == "current_problem" for error in errors)


def test_recall_accepts_current_problem_context() -> None:
    """recall should accept required worker problem context for synthesis."""

    request, errors = validate_recall_schema(
        {
            "query": "find migration context",
            "current_problem": {
                "goal": "fix migration",
                "surface": "db admin",
                "obstacle": "lock timeout",
                "hypothesis": "missing timeout guard",
            },
        }
    )

    assert errors == []
    assert request is not None
    assert request.current_problem is not None
    assert request.current_problem.goal == "fix migration"


def test_recall_rejects_blank_current_problem_fields() -> None:
    """recall should reject missing or blank problem context fields."""

    request, errors = validate_recall_schema(
        {
            "query": "find migration context",
            "current_problem": {
                "goal": "fix migration",
                "surface": "db admin",
                "obstacle": " ",
                "hypothesis": "none yet",
            },
        }
    )

    assert request is None
    assert errors
    assert any(error.field == "current_problem.obstacle" for error in errors)


def test_recall_accepts_limit_with_read_bounds() -> None:
    """recall limit should use the same hard bounds as read limits."""

    request, errors = validate_recall_schema(
        {
            "query": "find migration context",
            "limit": 100,
            "current_problem": _current_problem(),
        }
    )

    assert errors == []
    assert request is not None
    assert request.limit == 100


def test_recall_rejects_limit_above_read_bounds() -> None:
    """recall should reject limits above the read maximum."""

    request, errors = validate_recall_schema(
        {
            "query": "find migration context",
            "limit": 101,
            "current_problem": _current_problem(),
        }
    )

    assert request is None
    assert errors
    assert any(error.field == "limit" for error in errors)


def test_recall_rejects_internal_agent_runtime_fields() -> None:
    """recall should reject provider/model/reasoning runtime fields from workers."""

    payload = {
        "query": "find migration context",
        "current_problem": _current_problem(),
        "mode": "targeted",
        "expand": {"concepts": {"mode": "auto"}},
        "token_budget": 1200,
        "synthesis": {"model": "stub"},
        "provider": "codex",
        "model": "gpt-5.4-mini",
        "reasoning": "low",
        "unknown": "nope",
    }

    request, errors = validate_recall_schema(payload)

    assert request is None
    fields = {error.field for error in errors}
    assert {
        "mode",
        "expand",
        "token_budget",
        "synthesis",
        "provider",
        "model",
        "reasoning",
        "unknown",
    }.issubset(fields)


def _current_problem() -> dict[str, str]:
    return {
        "goal": "fix migration",
        "surface": "db admin",
        "obstacle": "lock timeout",
        "hypothesis": "none yet",
    }
