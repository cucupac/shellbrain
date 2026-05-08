"""Schema contracts for minimal recall requests."""

from app.periphery.cli.schema_validation import validate_recall_schema


def test_recall_accepts_query_only() -> None:
    """recall should accept the minimal Phase 1 public input."""

    request, errors = validate_recall_schema({"query": "find migration context"})

    assert errors == []
    assert request is not None
    assert request.query == "find migration context"
    assert request.limit is None


def test_recall_accepts_limit_with_read_bounds() -> None:
    """recall limit should use the same hard bounds as read limits."""

    request, errors = validate_recall_schema({"query": "find migration context", "limit": 100})

    assert errors == []
    assert request is not None
    assert request.limit == 100


def test_recall_rejects_limit_above_read_bounds() -> None:
    """recall should reject limits above the read maximum."""

    request, errors = validate_recall_schema({"query": "find migration context", "limit": 101})

    assert request is None
    assert errors
    assert any(error.field == "limit" for error in errors)


def test_recall_rejects_unused_phase_one_fields() -> None:
    """recall should reject every public field not used by the Phase 1 stub."""

    payload = {
        "query": "find migration context",
        "mode": "targeted",
        "expand": {"concepts": {"mode": "auto"}},
        "token_budget": 1200,
        "synthesis": {"model": "stub"},
        "unknown": "nope",
    }

    request, errors = validate_recall_schema(payload)

    assert request is None
    fields = {error.field for error in errors}
    assert {"mode", "expand", "token_budget", "synthesis", "unknown"}.issubset(fields)
