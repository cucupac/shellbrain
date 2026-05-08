"""Read execution contracts for context-pack builder selection rules."""

from app.core.policies.memory_read_policy.context_pack_builder import assemble_context_pack


def test_context_pack_builder_should_always_fill_targeted_quotas_in_direct_first_order() -> None:
    """context pack builder should always fill targeted quotas in direct-first order."""

    pack = assemble_context_pack(
        _make_scored_candidates(direct=6, explicit=4, implicit=3),
        _make_payload(mode="targeted"),
    )

    assert _section_ids(pack, "direct") == ["direct-1", "direct-2", "direct-3", "direct-4"]
    assert _section_ids(pack, "explicit_related") == ["explicit-1", "explicit-2", "explicit-3"]
    assert _section_ids(pack, "implicit_related") == ["implicit-1"]
    assert pack["meta"]["counts"] == {"direct": 4, "explicit_related": 3, "implicit_related": 1}


def test_context_pack_builder_should_always_fill_ambient_quotas_with_more_related_context_than_targeted_mode() -> None:
    """context pack builder should always fill ambient quotas with more related context than targeted mode."""

    pack = assemble_context_pack(
        _make_scored_candidates(direct=6, explicit=6, implicit=5),
        _make_payload(mode="ambient"),
    )

    assert _section_ids(pack, "direct") == ["direct-1", "direct-2", "direct-3", "direct-4"]
    assert _section_ids(pack, "explicit_related") == [
        "explicit-1",
        "explicit-2",
        "explicit-3",
        "explicit-4",
        "explicit-5",
    ]
    assert _section_ids(pack, "implicit_related") == ["implicit-1", "implicit-2", "implicit-3"]
    assert pack["meta"]["counts"] == {"direct": 4, "explicit_related": 5, "implicit_related": 3}


def test_context_pack_builder_should_always_deduplicate_repeated_memories_across_sections() -> None:
    """context pack builder should always deduplicate repeated memories across sections."""

    pack = assemble_context_pack(
        {
            "direct": [
                _candidate("shared", 0.99, "problem", "Shared direct memory.", "direct_match"),
                _candidate("direct-2", 0.95, "fact", "Second direct memory.", "direct_match"),
            ],
            "explicit": [
                _candidate(
                    "shared",
                    0.98,
                    "problem",
                    "Shared explicit memory.",
                    "problem_attempt",
                    anchor_memory_id="direct-1",
                ),
                _candidate(
                    "explicit-2",
                    0.94,
                    "solution",
                    "Second explicit memory.",
                    "problem_attempt",
                    anchor_memory_id="direct-1",
                ),
            ],
            "implicit": [
                _candidate(
                    "shared",
                    0.93,
                    "fact",
                    "Shared implicit memory.",
                    "semantic_neighbor",
                    anchor_memory_id="direct-1",
                ),
                _candidate(
                    "implicit-2",
                    0.92,
                    "fact",
                    "Second implicit memory.",
                    "semantic_neighbor",
                    anchor_memory_id="direct-1",
                ),
            ],
        },
        _make_payload(mode="targeted", limit=6),
    )

    assert _all_ids(pack).count("shared") == 1


def test_context_pack_builder_should_always_let_earlier_sections_win_dedupe_ties() -> None:
    """context pack builder should always let earlier sections win dedupe ties."""

    pack = assemble_context_pack(
        {
            "direct": [
                _candidate("shared", 0.90, "problem", "Shared direct memory.", "direct_match"),
            ],
            "explicit": [
                _candidate(
                    "shared",
                    0.99,
                    "solution",
                    "Shared explicit memory.",
                    "problem_attempt",
                    anchor_memory_id="direct-1",
                ),
                _candidate(
                    "explicit-2",
                    0.98,
                    "solution",
                    "Second explicit memory.",
                    "problem_attempt",
                    anchor_memory_id="direct-1",
                ),
            ],
            "implicit": [],
        },
        _make_payload(mode="targeted", limit=4),
    )

    assert _section_ids(pack, "direct") == ["shared"]
    assert _section_ids(pack, "explicit_related") == ["explicit-2"]


def test_context_pack_builder_should_always_shrink_a_small_custom_limit_in_direct_first_order() -> None:
    """context pack builder should always shrink a small custom limit in direct-first order."""

    pack = assemble_context_pack(
        _make_scored_candidates(direct=6, explicit=4, implicit=3),
        _make_payload(mode="targeted", limit=5),
    )

    assert _section_ids(pack, "direct") == ["direct-1", "direct-2", "direct-3", "direct-4"]
    assert _section_ids(pack, "explicit_related") == ["explicit-1"]
    assert _section_ids(pack, "implicit_related") == []
    assert len(_all_ids(pack)) == 5


def test_context_pack_builder_should_always_use_spillover_when_a_section_underfills() -> None:
    """context pack builder should always use spillover when a section underfills."""

    pack = assemble_context_pack(
        _make_scored_candidates(direct=4, explicit=1, implicit=4),
        _make_payload(mode="targeted"),
    )

    assert _section_ids(pack, "direct") == ["direct-1", "direct-2", "direct-3", "direct-4"]
    assert _section_ids(pack, "explicit_related") == ["explicit-1"]
    assert _section_ids(pack, "implicit_related") == ["implicit-1", "implicit-2", "implicit-3"]
    assert len(_all_ids(pack)) == 8


def test_context_pack_builder_should_always_pick_the_highest_scoring_unselected_candidates_during_spillover() -> None:
    """context pack builder should always pick the highest-scoring unselected candidates during spillover."""

    pack = assemble_context_pack(
        {
            "direct": [_candidate("direct-1", 0.99, "problem", "Direct memory.", "direct_match")],
            "explicit": [],
            "implicit": [
                _candidate("implicit-1", 0.75, "fact", "Implicit one.", "semantic_neighbor", anchor_memory_id="direct-1"),
                _candidate("implicit-2", 0.74, "fact", "Implicit two.", "semantic_neighbor", anchor_memory_id="direct-1"),
                _candidate("implicit-3", 0.73, "fact", "Implicit three.", "semantic_neighbor", anchor_memory_id="direct-1"),
                _candidate("implicit-4", 0.72, "fact", "Implicit four.", "semantic_neighbor", anchor_memory_id="direct-1"),
            ],
        },
        _make_payload(mode="targeted", limit=4),
    )

    assert _section_ids(pack, "implicit_related") == ["implicit-1", "implicit-2", "implicit-3"]


def test_context_pack_builder_should_always_enforce_the_hard_limit_after_quotas_and_spill() -> None:
    """context pack builder should always enforce the hard limit after quotas and spill."""

    pack = assemble_context_pack(
        _make_scored_candidates(direct=8, explicit=8, implicit=8),
        _make_payload(mode="ambient", limit=7),
    )

    assert len(_all_ids(pack)) == 7
    assert pack["meta"]["limit"] == 7


def _make_payload(*, mode: str, limit: int | None = None) -> dict[str, object]:
    """Build a deterministic builder payload for context-pack tests."""

    payload: dict[str, object] = {
        "repo_id": "repo-a",
        "mode": mode,
        "query": "rollback deployment issue",
    }
    if limit is not None:
        payload["limit"] = limit
    return payload


def _make_scored_candidates(*, direct: int, explicit: int, implicit: int) -> dict[str, list[dict[str, object]]]:
    """Build scored bucket inputs with display metadata for builder tests."""

    return {
        "direct": [
            _candidate(
                f"direct-{index}",
                1.0 - (index * 0.01),
                "problem",
                f"Direct shellbrain {index}.",
                "direct_match",
            )
            for index in range(1, direct + 1)
        ],
        "explicit": [
            _candidate(
                f"explicit-{index}",
                0.8 - (index * 0.01),
                "solution",
                f"Explicit shellbrain {index}.",
                "problem_attempt",
                anchor_memory_id="direct-1",
            )
            for index in range(1, explicit + 1)
        ],
        "implicit": [
            _candidate(
                f"implicit-{index}",
                0.6 - (index * 0.01),
                "fact",
                f"Implicit shellbrain {index}.",
                "semantic_neighbor",
                anchor_memory_id="direct-1",
            )
            for index in range(1, implicit + 1)
        ],
    }


def _candidate(
    memory_id: str,
    score: float,
    kind: str,
    text: str,
    why_included: str,
    *,
    anchor_memory_id: str | None = None,
    relation_type: str | None = None,
) -> dict[str, object]:
    """Build one future-shaped candidate row for context-pack tests."""

    candidate: dict[str, object] = {
        "memory_id": memory_id,
        "score": score,
        "kind": kind,
        "text": text,
        "why_included": why_included,
    }
    if anchor_memory_id is not None:
        candidate["anchor_memory_id"] = anchor_memory_id
    if relation_type is not None:
        candidate["relation_type"] = relation_type
    return candidate


def _section_ids(pack: dict[str, object], section: str) -> list[str]:
    """Extract ordered shellbrain identifiers from a named pack section."""

    return [str(item["memory_id"]) for item in pack[section]]


def _all_ids(pack: dict[str, object]) -> list[str]:
    """Extract all ordered shellbrain identifiers from the grouped pack."""

    return _section_ids(pack, "direct") + _section_ids(pack, "explicit_related") + _section_ids(pack, "implicit_related")
