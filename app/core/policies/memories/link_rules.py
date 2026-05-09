"""Pure memory link rules."""

from app.core.contracts.errors import ErrorCode, ErrorDetail
from app.core.contracts.memories import (
    AssociationLinkUpdate,
    FactUpdateLinkUpdate,
    MemoryBatchUpdateRequest,
    MemoryAddRequest,
    MemoryUpdateRequest,
)
from app.core.entities.memories import MemoryKind, is_mature_memory_kind


def validate_create_semantics(request: MemoryAddRequest) -> list[ErrorDetail]:
    """Validate semantic constraints for create operations."""

    errors: list[ErrorDetail] = []
    kind = MemoryKind(request.memory.kind)
    problem_id = request.memory.links.problem_id
    if kind.requires_problem_link and not problem_id:
        errors.append(
            ErrorDetail(
                code=ErrorCode.SEMANTIC_ERROR,
                message="links.problem_id is required for solution and failed_tactic memories",
                field="memory.links.problem_id",
            )
        )
    if not kind.requires_problem_link and problem_id:
        errors.append(
            ErrorDetail(
                code=ErrorCode.SEMANTIC_ERROR,
                message="links.problem_id is only valid for solution and failed_tactic memories",
                field="memory.links.problem_id",
            )
        )

    seen_pairs: set[tuple[str, str]] = set()
    for index, association in enumerate(request.memory.links.associations):
        pair = (association.to_memory_id, association.relation_type)
        if pair in seen_pairs:
            errors.append(
                ErrorDetail(
                    code=ErrorCode.SEMANTIC_ERROR,
                    message="Duplicate association link entries are not allowed",
                    field=f"memory.links.associations.{index}",
                )
            )
        seen_pairs.add(pair)
    return errors


def validate_update_semantics(
    request: MemoryUpdateRequest | MemoryBatchUpdateRequest,
) -> list[ErrorDetail]:
    """Validate semantic constraints for update operations."""

    errors: list[ErrorDetail] = []
    if isinstance(request, MemoryBatchUpdateRequest):
        problem_ids = {item.update.problem_id for item in request.updates}
        if len(problem_ids) > 1:
            errors.append(
                ErrorDetail(
                    code=ErrorCode.SEMANTIC_ERROR,
                    message="Batch utility votes must share the same problem_id",
                    field="updates",
                )
            )
        return errors

    update = request.update
    if (
        isinstance(update, AssociationLinkUpdate)
        and update.to_memory_id == request.memory_id
    ):
        errors.append(
            ErrorDetail(
                code=ErrorCode.SEMANTIC_ERROR,
                message="association links cannot self-reference the source memory",
                field="update.to_memory_id",
            )
        )
    if isinstance(update, FactUpdateLinkUpdate):
        if update.old_fact_id == update.new_fact_id:
            errors.append(
                ErrorDetail(
                    code=ErrorCode.SEMANTIC_ERROR,
                    message="fact_update_link requires different old_fact_id and new_fact_id values",
                    field="update.new_fact_id",
                )
            )
        if (
            update.old_fact_id == request.memory_id
            or update.new_fact_id == request.memory_id
        ):
            errors.append(
                ErrorDetail(
                    code=ErrorCode.SEMANTIC_ERROR,
                    message="memory_id is the change shellbrain id and cannot equal old_fact_id/new_fact_id",
                    field="memory_id",
                )
            )
    return errors


def validate_matures_into_relation(
    *,
    source_kind: MemoryKind | str,
    target_kind: MemoryKind | str | None,
    relation_type: str,
    field: str,
) -> list[ErrorDetail]:
    """Validate the frontier-to-mature kind contract for matures_into relations."""

    if relation_type != "matures_into":
        return []

    normalized_source_kind = (
        source_kind if isinstance(source_kind, MemoryKind) else MemoryKind(source_kind)
    )
    errors: list[ErrorDetail] = []
    if normalized_source_kind != MemoryKind.FRONTIER:
        errors.append(
            ErrorDetail(
                code=ErrorCode.INTEGRITY_ERROR,
                message="matures_into requires the source memory to be a frontier memory",
                field=field,
            )
        )
    if target_kind is not None and not is_mature_memory_kind(target_kind):
        errors.append(
            ErrorDetail(
                code=ErrorCode.INTEGRITY_ERROR,
                message="matures_into requires the target memory to be a mature durable memory",
                field=field,
            )
        )
    return errors
