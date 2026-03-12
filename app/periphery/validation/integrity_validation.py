"""Database-integrity compatibility checks for validated edge requests."""

from app.core.contracts.errors import ErrorCode, ErrorDetail
from app.core.contracts.requests import (
    AssociationLinkUpdate,
    FactUpdateLinkUpdate,
    MemoryCreateRequest,
    MemoryUpdateRequest,
    UtilityVoteUpdate,
)
from app.core.entities.memory import Memory, MemoryKind, MemoryScope
from app.core.interfaces.unit_of_work import IUnitOfWork


def _is_visible(memory: Memory, repo_id: str) -> bool:
    """Determine whether a memory is visible inside a repo operation context."""

    return memory.repo_id == repo_id or memory.scope == MemoryScope.GLOBAL


def _require_memory(uow: IUnitOfWork, *, memory_id: str, field: str) -> tuple[Memory | None, list[ErrorDetail]]:
    """Fetch a memory row and return a not-found contract error when missing."""

    memory = uow.memories.get(memory_id)
    if memory is None:
        return None, [ErrorDetail(code=ErrorCode.NOT_FOUND, message=f"Memory not found: {memory_id}", field=field)]
    return memory, []


def validate_create_integrity(request: MemoryCreateRequest, uow: IUnitOfWork) -> list[ErrorDetail]:
    """Validate database integrity constraints for create operations."""

    errors: list[ErrorDetail] = []
    links = request.memory.links
    if links.problem_id:
        problem_memory, problem_errors = _require_memory(uow, memory_id=links.problem_id, field="memory.links.problem_id")
        errors.extend(problem_errors)
        if problem_memory and not _is_visible(problem_memory, request.repo_id):
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
        if target and not _is_visible(target, request.repo_id):
            errors.append(
                ErrorDetail(
                    code=ErrorCode.INTEGRITY_ERROR,
                    message="Association target memory is not visible for this repo_id",
                    field=f"memory.links.associations.{index}.to_memory_id",
                )
            )
    return errors


def validate_update_integrity(request: MemoryUpdateRequest, uow: IUnitOfWork) -> list[ErrorDetail]:
    """Validate database integrity constraints for update operations."""

    errors: list[ErrorDetail] = []
    target_memory, target_errors = _require_memory(uow, memory_id=request.memory_id, field="memory_id")
    errors.extend(target_errors)
    if target_memory and not _is_visible(target_memory, request.repo_id):
        errors.append(
            ErrorDetail(
                code=ErrorCode.INTEGRITY_ERROR,
                message="Target memory is not visible for this repo_id",
                field="memory_id",
            )
        )

    update = request.update
    if isinstance(update, UtilityVoteUpdate):
        problem_memory, problem_errors = _require_memory(uow, memory_id=update.problem_id, field="update.problem_id")
        errors.extend(problem_errors)
        if problem_memory and not _is_visible(problem_memory, request.repo_id):
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
        old_fact, old_errors = _require_memory(uow, memory_id=update.old_fact_id, field="update.old_fact_id")
        new_fact, new_errors = _require_memory(uow, memory_id=update.new_fact_id, field="update.new_fact_id")
        errors.extend(old_errors)
        errors.extend(new_errors)
        if old_fact and not _is_visible(old_fact, request.repo_id):
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
        if new_fact and not _is_visible(new_fact, request.repo_id):
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
        target, target_errors = _require_memory(uow, memory_id=update.to_memory_id, field="update.to_memory_id")
        errors.extend(target_errors)
        if target and not _is_visible(target, request.repo_id):
            errors.append(
                ErrorDetail(
                    code=ErrorCode.INTEGRITY_ERROR,
                    message="association_link.to_memory_id is not visible for this repo_id",
                    field="update.to_memory_id",
                )
            )
    return errors
