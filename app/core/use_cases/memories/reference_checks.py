"""Repository-backed reference checks for memory write requests."""

from app.core.errors import ErrorCode, ErrorDetail
from app.core.use_cases.memories.add.request import MemoryAddRequest
from app.core.use_cases.memories.update.request import (
    AssociationLinkUpdate,
    FactUpdateLinkUpdate,
    MemoryBatchUpdateRequest,
    MemoryUpdateRequest,
    UtilityVoteUpdate,
)
from app.core.entities.memories import (
    Memory,
    MemoryKind,
)
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.policies.memories.link_rules import validate_matures_into_relation
from app.core.policies.memories.link_rules import (
    validate_create_semantics,
    validate_update_semantics,
)


def validate_create_request(
    request: MemoryAddRequest,
    *,
    uow: IUnitOfWork,
    gates: list[str] | tuple[str, ...],
) -> list[ErrorDetail]:
    """Run core semantic and repository-backed create validations."""

    if "semantic" in gates:
        semantic_errors = validate_create_semantics(request)
        if semantic_errors:
            return semantic_errors
    if "integrity" in gates:
        return validate_create_integrity(request, uow)
    return []


def validate_update_request(
    request: MemoryUpdateRequest | MemoryBatchUpdateRequest,
    *,
    uow: IUnitOfWork,
    gates: list[str] | tuple[str, ...],
) -> list[ErrorDetail]:
    """Run core semantic and repository-backed update validations."""

    if "semantic" in gates:
        semantic_errors = validate_update_semantics(request)
        if semantic_errors:
            return semantic_errors
    if "integrity" in gates:
        return validate_update_integrity(request, uow)
    return []


def _require_memory(
    uow: IUnitOfWork, *, memory_id: str, field: str
) -> tuple[Memory | None, list[ErrorDetail]]:
    """Fetch a memory row and return a not-found contract error when missing."""

    memory = uow.memories.get(memory_id)
    if memory is None:
        return None, [
            ErrorDetail(
                code=ErrorCode.NOT_FOUND,
                message=f"Memory not found: {memory_id}",
                field=field,
            )
        ]
    return memory, []


def _validate_evidence_refs(
    uow: IUnitOfWork,
    *,
    repo_id: str,
    refs: list[str],
    field_prefix: str,
) -> list[ErrorDetail]:
    """Validate that evidence refs resolve to repo-visible episode events."""

    if not refs:
        return []

    existing_ids = set(uow.episodes.list_existing_event_ids(event_ids=refs))
    visible_ids = set(
        uow.episodes.list_visible_event_ids(repo_id=repo_id, event_ids=refs)
    )
    errors: list[ErrorDetail] = []

    for index, ref in enumerate(refs):
        field = f"{field_prefix}.{index}"
        if ref not in existing_ids:
            errors.append(
                ErrorDetail(
                    code=ErrorCode.NOT_FOUND,
                    message=f"Episode event not found: {ref}",
                    field=field,
                )
            )
            continue
        if ref not in visible_ids:
            errors.append(
                ErrorDetail(
                    code=ErrorCode.INTEGRITY_ERROR,
                    message="Referenced episode event is not visible for this repo_id",
                    field=field,
                )
            )
    return errors


def validate_create_integrity(
    request: MemoryAddRequest, uow: IUnitOfWork
) -> list[ErrorDetail]:
    """Validate database integrity constraints for create operations."""

    errors = _validate_evidence_refs(
        uow,
        repo_id=request.repo_id,
        refs=list(request.memory.evidence_refs),
        field_prefix="memory.evidence_refs",
    )
    links = request.memory.links
    if links.problem_id:
        problem_memory, problem_errors = _require_memory(
            uow, memory_id=links.problem_id, field="memory.links.problem_id"
        )
        errors.extend(problem_errors)
        if problem_memory and not problem_memory.is_visible_in(request.repo_id):
            errors.append(
                ErrorDetail(
                    code=ErrorCode.INTEGRITY_ERROR,
                    message="Referenced problem memory is not visible for this repo_id",
                    field="memory.links.problem_id",
                )
            )
        if problem_memory and problem_memory.kind != MemoryKind.PROBLEM:
            errors.append(
                ErrorDetail(
                    code=ErrorCode.INTEGRITY_ERROR,
                    message="Referenced problem_id must point to a problem memory",
                    field="memory.links.problem_id",
                )
            )

    for index, association in enumerate(links.associations):
        target, target_errors = _require_memory(
            uow,
            memory_id=association.to_memory_id,
            field=f"memory.links.associations.{index}.to_memory_id",
        )
        errors.extend(target_errors)
        if target and not target.is_visible_in(request.repo_id):
            errors.append(
                ErrorDetail(
                    code=ErrorCode.INTEGRITY_ERROR,
                    message="Association target shellbrain is not visible for this repo_id",
                    field=f"memory.links.associations.{index}.to_memory_id",
                )
            )
        if target and target.is_visible_in(request.repo_id):
            errors.extend(
                validate_matures_into_relation(
                    source_kind=MemoryKind(request.memory.kind),
                    target_kind=target.kind,
                    relation_type=association.relation_type,
                    field=f"memory.links.associations.{index}.relation_type",
                )
            )
    return errors


def validate_update_integrity(
    request: MemoryUpdateRequest | MemoryBatchUpdateRequest, uow: IUnitOfWork
) -> list[ErrorDetail]:
    """Validate database integrity constraints for update operations."""

    if isinstance(request, MemoryBatchUpdateRequest):
        errors: list[ErrorDetail] = []
        for index, item in enumerate(request.updates):
            single_errors = validate_update_integrity(
                MemoryUpdateRequest(
                    repo_id=request.repo_id,
                    memory_id=item.memory_id,
                    update=item.update,
                ),
                uow,
            )
            for error in single_errors:
                field = error.field
                if field is not None:
                    field = f"updates.{index}.{field}"
                errors.append(
                    ErrorDetail(code=error.code, message=error.message, field=field)
                )
        return errors

    errors: list[ErrorDetail] = []
    target_memory, target_errors = _require_memory(
        uow, memory_id=request.memory_id, field="memory_id"
    )
    errors.extend(target_errors)
    if target_memory and not target_memory.is_visible_in(request.repo_id):
        errors.append(
            ErrorDetail(
                code=ErrorCode.INTEGRITY_ERROR,
                message="Target memory is not visible for this repo_id",
                field="memory_id",
            )
        )

    update = request.update
    if isinstance(update, UtilityVoteUpdate):
        errors.extend(
            _validate_evidence_refs(
                uow,
                repo_id=request.repo_id,
                refs=list(update.evidence_refs),
                field_prefix="update.evidence_refs",
            )
        )
        problem_memory, problem_errors = _require_memory(
            uow, memory_id=update.problem_id, field="update.problem_id"
        )
        errors.extend(problem_errors)
        if problem_memory and not problem_memory.is_visible_in(request.repo_id):
            errors.append(
                ErrorDetail(
                    code=ErrorCode.INTEGRITY_ERROR,
                    message="utility_vote.problem_id is not visible for this repo_id",
                    field="update.problem_id",
                )
            )
        if problem_memory and problem_memory.kind != MemoryKind.PROBLEM:
            errors.append(
                ErrorDetail(
                    code=ErrorCode.INTEGRITY_ERROR,
                    message="utility_vote.problem_id must reference a problem memory",
                    field="update.problem_id",
                )
            )

    if isinstance(update, FactUpdateLinkUpdate):
        errors.extend(
            _validate_evidence_refs(
                uow,
                repo_id=request.repo_id,
                refs=list(update.evidence_refs),
                field_prefix="update.evidence_refs",
            )
        )
        old_fact, old_errors = _require_memory(
            uow, memory_id=update.old_fact_id, field="update.old_fact_id"
        )
        new_fact, new_errors = _require_memory(
            uow, memory_id=update.new_fact_id, field="update.new_fact_id"
        )
        errors.extend(old_errors)
        errors.extend(new_errors)
        if old_fact and not old_fact.is_visible_in(request.repo_id):
            errors.append(
                ErrorDetail(
                    code=ErrorCode.INTEGRITY_ERROR,
                    message="old_fact_id is not visible for this repo_id",
                    field="update.old_fact_id",
                )
            )
        if old_fact and old_fact.kind != MemoryKind.FACT:
            errors.append(
                ErrorDetail(
                    code=ErrorCode.INTEGRITY_ERROR,
                    message="old_fact_id must reference a fact memory",
                    field="update.old_fact_id",
                )
            )
        if new_fact and not new_fact.is_visible_in(request.repo_id):
            errors.append(
                ErrorDetail(
                    code=ErrorCode.INTEGRITY_ERROR,
                    message="new_fact_id is not visible for this repo_id",
                    field="update.new_fact_id",
                )
            )
        if new_fact and new_fact.kind != MemoryKind.FACT:
            errors.append(
                ErrorDetail(
                    code=ErrorCode.INTEGRITY_ERROR,
                    message="new_fact_id must reference a fact memory",
                    field="update.new_fact_id",
                )
            )
        if target_memory and target_memory.kind != MemoryKind.CHANGE:
            errors.append(
                ErrorDetail(
                    code=ErrorCode.INTEGRITY_ERROR,
                    message="memory_id must reference a change memory for fact_update_link",
                    field="memory_id",
                )
            )

    if isinstance(update, AssociationLinkUpdate):
        errors.extend(
            _validate_evidence_refs(
                uow,
                repo_id=request.repo_id,
                refs=list(update.evidence_refs),
                field_prefix="update.evidence_refs",
            )
        )
        target, target_errors = _require_memory(
            uow, memory_id=update.to_memory_id, field="update.to_memory_id"
        )
        errors.extend(target_errors)
        if target and not target.is_visible_in(request.repo_id):
            errors.append(
                ErrorDetail(
                    code=ErrorCode.INTEGRITY_ERROR,
                    message="association_link.to_memory_id is not visible for this repo_id",
                    field="update.to_memory_id",
                )
            )
        if target_memory and target and target.is_visible_in(request.repo_id):
            errors.extend(
                validate_matures_into_relation(
                    source_kind=target_memory.kind,
                    target_kind=target.kind,
                    relation_type=update.relation_type,
                    field="update.relation_type",
                )
            )
    return errors
