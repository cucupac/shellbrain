"""Schema contracts for read-path requests."""

from app.core.contracts.agent_requests import validate_read_schema


def test_read_rejects_unknown_fields() -> None:
    """read requests should always reject unknown fields."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "unknown": "nope",
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)


def test_read_rejects_invalid_operation() -> None:
    """read requests should always reject op values other than read."""

    payload = {
        "op": "create",
        "query": "find deployment issue memory",
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)


def test_read_requires_non_empty_query() -> None:
    """read requests should always require non-empty query text."""

    payload = {
        "op": "read",
        "query": "",
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)
    assert any(error.field == "query" for error in errors)


def test_read_kinds_reject_non_ratified_values() -> None:
    """read requests should always limit kinds filters to ratified shellbrain kinds."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "kinds": ["problem", "unknown_kind"],
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)
    assert any((error.field or "").startswith("kinds") for error in errors)


def test_read_kinds_reject_duplicates() -> None:
    """read requests should always require unique kinds filters."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "kinds": ["problem", "problem"],
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)
    assert any((error.field or "").startswith("kinds") for error in errors)


def test_read_kinds_reject_empty_lists() -> None:
    """read requests should always require at least one kind when kinds is provided."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "kinds": [],
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)
    assert any((error.field or "").startswith("kinds") for error in errors)


def test_read_kinds_accept_frontier() -> None:
    """read requests should always accept frontier in explicit kinds filters."""

    payload = {
        "op": "read",
        "query": "open questions about retrieval",
        "kinds": ["frontier"],
    }

    request, errors = validate_read_schema(payload)

    assert errors == []
    assert request is not None


def test_read_accepts_concept_expansion_at_agent_interface() -> None:
    """read requests should accept worker-facing concept expansion controls."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "expand": {
            "concepts": {
                "mode": "explicit",
                "refs": ["deposit-addresses"],
                "facets": ["groundings"],
                "max_auto": 2,
            }
        },
    }

    request, errors = validate_read_schema(payload)

    assert errors == []
    assert request is not None
    assert request.expand is not None
    assert request.expand.concepts is not None
    assert request.expand.concepts.mode == "explicit"


def test_read_rejects_hidden_expansion_override_knobs_at_agent_interface() -> None:
    """read requests should reject hidden memory expansion knobs at the agent interface."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "mode": "ambient",
        "include_global": False,
        "limit": 99,
        "expand": {
            "semantic_hops": 0,
        },
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    fields = {error.field for error in errors}
    assert "expand.semantic_hops" in fields


def test_read_rejects_explicit_concept_expansion_without_refs() -> None:
    """explicit concept expansion should require at least one concept ref."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "expand": {"concepts": {"mode": "explicit"}},
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert errors


def test_read_rejects_invalid_concept_facets() -> None:
    """concept facets should stay inside the ratified progressive-disclosure set."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "expand": {"concepts": {"mode": "explicit", "refs": ["deposit-addresses"], "facets": ["files"]}},
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert errors


def test_read_rejects_concept_max_auto_above_hard_cap() -> None:
    """auto concept selection should enforce the hard max cap."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "expand": {"concepts": {"mode": "auto", "max_auto": 6}},
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert errors


def test_read_rejects_too_many_explicit_concept_refs() -> None:
    """explicit concept expansion should enforce the same hard concept cap."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "expand": {
            "concepts": {
                "mode": "explicit",
                "refs": ["one", "two", "three", "four", "five", "six"],
            }
        },
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert errors


def test_read_rejects_blank_explicit_concept_refs() -> None:
    """explicit concept refs should be real refs, not blank strings."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "expand": {"concepts": {"mode": "explicit", "refs": [""]}},
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert errors
