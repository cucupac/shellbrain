"""Core evidence entity invariant tests."""

import pytest

from app.core.entities.evidence import (
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceTarget,
    EvidenceTargetType,
)


def test_episode_event_source_should_normalize_ref_aliases() -> None:
    """Episode-event evidence should expose the same canonical ref in both fields."""

    source = EvidenceSource(
        source_kind=EvidenceSourceKind.EPISODE_EVENT, episode_event_id="event-1"
    )

    assert source.ref == "event-1"
    assert source.episode_event_id == "event-1"


def test_evidence_source_should_reject_extra_reference_fields() -> None:
    """Each source kind should accept only its one required reference field."""

    with pytest.raises(ValueError, match="does not accept"):
        EvidenceSource(
            source_kind=EvidenceSourceKind.MANUAL,
            note="Manual review.",
            memory_id="memory-1",
        )


def test_evidence_source_should_require_kind_specific_reference() -> None:
    """Source kinds should fail without their required reference field."""

    with pytest.raises(ValueError, match="memory evidence requires memory_id"):
        EvidenceSource(source_kind=EvidenceSourceKind.MEMORY)


def test_evidence_target_should_require_target_id() -> None:
    """Evidence targets should not allow blank target identifiers."""

    with pytest.raises(ValueError, match="target_id"):
        EvidenceTarget(target_type=EvidenceTargetType.MEMORY, target_id=" ")
