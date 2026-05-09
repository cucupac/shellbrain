"""Unit contracts for deterministic read-pack token estimation."""

from __future__ import annotations

from app.infrastructure.telemetry.read_records import (
    estimate_read_pack_size,
)


def test_estimate_read_pack_size_should_always_be_stable_for_the_same_input_pack() -> (
    None
):
    """The read-pack estimator should be deterministic for identical input."""

    pack = {
        "meta": {
            "mode": "targeted",
            "limit": 8,
            "counts": {"direct": 1, "explicit_related": 0, "implicit_related": 0},
        },
        "direct": [
            {
                "memory_id": "mem-1",
                "kind": "problem",
                "text": "One memory.",
                "priority": 1,
                "why_included": "direct_match",
            }
        ],
        "explicit_related": [],
        "implicit_related": [],
    }

    first = estimate_read_pack_size(pack=pack)
    second = estimate_read_pack_size(pack=pack)

    assert first == second
    assert first["pack_token_estimate_method"] == "json_compact_chars_div4_v1"
    assert first["pack_char_count"] > 0
    assert first["pack_token_estimate"] > 0
    assert first["direct_token_estimate"] > 0
    assert first["explicit_related_token_estimate"] == 0
    assert first["implicit_related_token_estimate"] == 0
