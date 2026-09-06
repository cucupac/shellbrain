"""Expose shared evidence selection to knowledge-building agents."""

from app.core.entities.settings import ThresholdSettings
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.use_cases.retrieval.deterministic_graph_recall import (
    build_deterministic_graph_pack,
    source_items_from_graph_pack,
)
from app.core.use_cases.retrieval.read.request import MemoryReadRequest
from app.core.use_cases.retrieval.read.result import ReadMemoryResult


def execute_read_memory(
    request: MemoryReadRequest,
    uow: IUnitOfWork,
    *,
    threshold_settings: ThresholdSettings | None = None,
) -> ReadMemoryResult:
    """Return selected records using the existing read and telemetry envelope."""
    selected = build_deterministic_graph_pack(
        request=request, uow=uow, threshold_settings=threshold_settings
    )
    sections = {name: [] for name in ("direct", "explicit_related", "implicit_related")}
    sources = {
        row["source_id"]: row
        for row in source_items_from_graph_pack(selected)
        if row["source_kind"] == "memory"
    }
    for priority, memory in enumerate(selected["memories"], start=1):
        section = sources[memory["id"]]["input_section"]
        sections[section].append(
            {
                **memory,
                "memory_id": memory["id"],
                "priority": priority,
                "why_included": ", ".join(memory["why"]),
            }
        )
    for priority, memory in enumerate(
        (item for items in sections.values() for item in items), start=1
    ):
        memory["priority"] = priority
    return ReadMemoryResult(
        pack={
            "meta": {
                "mode": request.mode,
                "limit": request.limit,
                "counts": {
                    "direct": len(sections["direct"]),
                    "explicit_related": len(sections["explicit_related"]),
                    "implicit_related": len(sections["implicit_related"]),
                },
            },
            **sections,
            "concepts": {
                "mode": request.expand.concepts.mode,
                "items": selected["concepts"],
            },
            "relation_neighbors": selected["relation_neighbors"],
            "conflicts": selected["conflicts"],
        }
    )
