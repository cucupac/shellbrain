"""Hydration contracts for update-path requests."""

from app.infrastructure.cli.protocol.hydration import hydrate_update_payload


def test_update_hydration_infers_missing_repo_id() -> None:
    """update hydration should always infer repo_id when omitted."""

    payload = {
        "memory_id": "memory-1",
        "update": {
            "type": "archive_state",
            "archived": True,
        },
    }

    hydrated = hydrate_update_payload(payload, inferred_repo_id="repo-inferred")

    assert hydrated == {
        "op": "update",
        "repo_id": "repo-inferred",
        "memory_id": "memory-1",
        "update": {
            "type": "archive_state",
            "archived": True,
        },
    }


def test_update_hydration_preserves_explicit_repo_id() -> None:
    """update hydration should always preserve explicit repo_id over inferred defaults."""

    payload = {
        "op": "update",
        "repo_id": "repo-explicit",
        "memory_id": "memory-1",
        "update": {
            "type": "archive_state",
            "archived": True,
        },
    }

    hydrated = hydrate_update_payload(payload, inferred_repo_id="repo-inferred")

    assert hydrated == payload
