"""Request-shape contracts for the events operation."""

from app.entrypoints.cli.request_parsing.hydration import hydrate_events_payload
from app.entrypoints.cli.request_parsing.payload_validation import validate_events_schema


def test_events_accepts_optional_limit() -> None:
    """events requests should always accept an optional limit without extra selectors."""

    request, errors = validate_events_schema({"limit": 5})

    assert errors == []
    assert request is not None
    assert request.limit == 5


def test_events_accepts_exact_episode_id() -> None:
    """events requests should accept an exact episode selector for builders."""

    request, errors = validate_events_schema({"episode_id": "episode-1", "limit": 5})

    assert errors == []
    assert request is not None
    assert request.episode_id == "episode-1"


def test_events_accepts_exact_episode_sequence_range() -> None:
    """events requests should accept exact sequence ranges for builders."""

    request, errors = validate_events_schema(
        {"episode_id": "episode-1", "after_seq": 3, "up_to_seq": 8}
    )

    assert errors == []
    assert request is not None
    assert request.after_seq == 3
    assert request.up_to_seq == 8


def test_events_rejects_range_without_episode_id() -> None:
    """event sequence ranges should be scoped to one exact episode."""

    request, errors = validate_events_schema({"after_seq": 3, "up_to_seq": 8})

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)


def test_events_enforces_limit_bounds() -> None:
    """events requests should always enforce configured limit bounds."""

    request, errors = validate_events_schema({"limit": 101})

    assert request is None
    assert any(error.field == "limit" for error in errors)


def test_events_rejects_unknown_fields() -> None:
    """events requests should always reject unknown fields."""

    request, errors = validate_events_schema({"host_app": "codex", "unknown": True})

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)


def test_events_hydration_infers_repo_and_default_limit() -> None:
    """events hydration should always infer repo_id and the default limit."""

    hydrated = hydrate_events_payload({}, inferred_repo_id="repo-inferred")

    assert hydrated == {
        "op": "events",
        "repo_id": "repo-inferred",
        "limit": 20,
    }


def test_events_hydration_preserves_exact_episode_id() -> None:
    """events hydration should preserve exact episode selectors."""

    hydrated = hydrate_events_payload(
        {"episode_id": "episode-1"},
        inferred_repo_id="repo-inferred",
    )

    assert hydrated == {
        "op": "events",
        "repo_id": "repo-inferred",
        "limit": 20,
        "episode_id": "episode-1",
    }


def test_events_hydration_preserves_exact_sequence_range() -> None:
    """events hydration should preserve builder watermark ranges."""

    hydrated = hydrate_events_payload(
        {"episode_id": "episode-1", "after_seq": 3, "up_to_seq": 8},
        inferred_repo_id="repo-inferred",
    )

    assert hydrated == {
        "op": "events",
        "repo_id": "repo-inferred",
        "limit": 20,
        "episode_id": "episode-1",
        "after_seq": 3,
        "up_to_seq": 8,
    }
