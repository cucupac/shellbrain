"""This module defines helper constructors for write-policy side-effect descriptors."""

from typing import Any


def make_side_effect(effect_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """This function creates a normalized side-effect descriptor object."""

    return {"effect_type": effect_type, "params": params}


def make_memory_create_effect(*, memory_id: str, repo_id: str, scope: str, kind: str, text: str, confidence: float | None) -> dict[str, Any]:
    """This function creates a side effect that inserts a memory row."""

    return make_side_effect(
        "memory.create",
        {
            "memory_id": memory_id,
            "repo_id": repo_id,
            "scope": scope,
            "kind": kind,
            "text": text,
            "confidence": confidence,
        },
    )


def make_memory_evidence_effect(*, memory_id: str, repo_id: str, refs: list[str]) -> dict[str, Any]:
    """This function creates a side effect that attaches evidence refs to a memory."""

    return make_side_effect("memory_evidence.attach", {"memory_id": memory_id, "repo_id": repo_id, "refs": refs})
