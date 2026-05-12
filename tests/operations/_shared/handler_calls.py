"""Test adapters for operation handlers after request-parsing/handler separation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from app.core.use_cases.episodes.events.request import EpisodeEventsRequest
from app.core.use_cases.memories.add.request import MemoryAddRequest
from app.core.use_cases.memories.update.request import (
    MemoryBatchUpdateRequest,
    MemoryUpdateRequest,
)
from app.core.use_cases.retrieval.read.request import MemoryReadRequest
from app.core.use_cases.retrieval.recall.request import MemoryRecallRequest
from app.core.ports.system.idgen import IIdGenerator
from app.entrypoints.cli.request_parsing.episodes import prepare_events_request
from app.entrypoints.cli.request_parsing.memories import (
    prepare_memory_add_request,
    prepare_update_request,
)
from app.entrypoints.cli.request_parsing.prepared import PreparedOperationRequest
from app.entrypoints.cli.request_parsing.retrieval import (
    prepare_read_request,
    prepare_recall_request,
)
from app.entrypoints.cli.handlers.internal_agent.episodes.events import run_read_events_operation
from app.entrypoints.cli.handlers.internal_agent.memories.add import run_create_memory_operation
from app.entrypoints.cli.handlers.internal_agent.memories.update import run_update_memory_operation
from app.entrypoints.cli.handlers.internal_agent.retrieval.read import run_read_memory_operation
from app.entrypoints.cli.handlers.working_agent.recall import run_recall_memory_operation
from app.entrypoints.cli.handlers.internal_agent.concepts.add import run_concept_add_operation
from app.entrypoints.cli.handlers.internal_agent.concepts.update import run_concept_update_operation
from app.startup import operation_dependencies as startup_handlers
from app.startup.create_policy import get_create_hydration_defaults
from app.startup.read_policy import get_read_hydration_defaults


def handle_memory_add(
    request: MemoryAddRequest | dict[str, Any] | None,
    *,
    uow_factory,
    embedding_provider_factory,
    embedding_model: str,
    inferred_repo_id: str,
    defaults: dict[str, Any] | None = None,
    id_generator: IIdGenerator | None = None,
    repo_root: Path | None = None,
    **_: Any,
) -> dict[str, Any]:
    prepared = _prepare_create(request, inferred_repo_id=inferred_repo_id, defaults=defaults)
    dependencies = startup_handlers.build_operation_dependencies()
    if id_generator is not None:
        dependencies = replace(dependencies, id_generator=id_generator)
    return run_create_memory_operation(
        prepared.request,
        dependencies=dependencies,
        uow_factory=uow_factory,
        embedding_provider_factory=embedding_provider_factory,
        embedding_model=embedding_model,
        inferred_repo_id=inferred_repo_id,
        validation_errors=prepared.errors,
        validation_error_stage=prepared.error_stage,
        repo_root=repo_root,
    )


def handle_update(
    request: MemoryUpdateRequest | MemoryBatchUpdateRequest | dict[str, Any] | None,
    *,
    uow_factory,
    inferred_repo_id: str,
    id_generator: IIdGenerator | None = None,
    repo_root: Path | None = None,
    **_: Any,
) -> dict[str, Any]:
    prepared = _prepare_update(request, inferred_repo_id=inferred_repo_id)
    dependencies = startup_handlers.build_operation_dependencies()
    if id_generator is not None:
        dependencies = replace(dependencies, id_generator=id_generator)
    return run_update_memory_operation(
        prepared.request,
        dependencies=dependencies,
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        validation_errors=prepared.errors,
        validation_error_stage=prepared.error_stage,
        repo_root=repo_root,
    )


def handle_read(
    request: MemoryReadRequest | dict[str, Any] | None,
    *,
    uow_factory,
    inferred_repo_id: str,
    defaults: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    **_: Any,
) -> dict[str, Any]:
    prepared = _prepare_read(request, inferred_repo_id=inferred_repo_id, defaults=defaults)
    return run_read_memory_operation(
        prepared.request,
        dependencies=startup_handlers.build_operation_dependencies(),
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        validation_errors=prepared.errors,
        validation_error_stage=prepared.error_stage,
        requested_limit=prepared.requested_limit,
        repo_root=repo_root,
    )


def handle_recall(
    request: MemoryRecallRequest | dict[str, Any] | None,
    *,
    uow_factory,
    inferred_repo_id: str,
    repo_root: Path | None = None,
    **_: Any,
) -> dict[str, Any]:
    prepared = _prepare_recall(request, inferred_repo_id=inferred_repo_id)
    return run_recall_memory_operation(
        prepared.request,
        dependencies=startup_handlers.build_operation_dependencies(),
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        validation_errors=prepared.errors,
        validation_error_stage=prepared.error_stage,
        repo_root=repo_root,
    )


def handle_events(
    request: EpisodeEventsRequest | dict[str, Any] | None,
    *,
    uow_factory,
    inferred_repo_id: str,
    repo_root: Path | None = None,
    search_roots_by_host: dict[str, list[Path]] | None = None,
    id_generator: IIdGenerator | None = None,
    **_: Any,
) -> dict[str, Any]:
    prepared = _prepare_events(request, inferred_repo_id=inferred_repo_id)
    dependencies = startup_handlers.build_operation_dependencies()
    if id_generator is not None:
        dependencies = replace(dependencies, id_generator=id_generator)
    return run_read_events_operation(
        prepared.request,
        dependencies=dependencies,
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        validation_errors=prepared.errors,
        validation_error_stage=prepared.error_stage,
        repo_root=repo_root,
        search_roots_by_host=search_roots_by_host,
    )


def handle_concept_add(*args: Any, **kwargs: Any) -> dict[str, Any]:
    dependencies = startup_handlers.build_operation_dependencies()
    return run_concept_add_operation(*args, dependencies=dependencies, **kwargs)


def handle_concept_update(*args: Any, **kwargs: Any) -> dict[str, Any]:
    dependencies = startup_handlers.build_operation_dependencies()
    return run_concept_update_operation(*args, dependencies=dependencies, **kwargs)


def _prepare_create(
    request: MemoryAddRequest | dict[str, Any] | None,
    *,
    inferred_repo_id: str,
    defaults: dict[str, Any] | None,
) -> PreparedOperationRequest[MemoryAddRequest]:
    if isinstance(request, MemoryAddRequest) or request is None:
        return PreparedOperationRequest(request=request, errors=())
    return prepare_memory_add_request(
        request,
        inferred_repo_id=inferred_repo_id,
        defaults=defaults or get_create_hydration_defaults(),
    )


def _prepare_update(
    request: MemoryUpdateRequest | MemoryBatchUpdateRequest | dict[str, Any] | None,
    *,
    inferred_repo_id: str,
) -> PreparedOperationRequest[MemoryUpdateRequest | MemoryBatchUpdateRequest]:
    if (
        isinstance(request, MemoryUpdateRequest | MemoryBatchUpdateRequest)
        or request is None
    ):
        return PreparedOperationRequest(request=request, errors=())
    return prepare_update_request(request, inferred_repo_id=inferred_repo_id)


def _prepare_read(
    request: MemoryReadRequest | dict[str, Any] | None,
    *,
    inferred_repo_id: str,
    defaults: dict[str, Any] | None,
) -> PreparedOperationRequest[MemoryReadRequest]:
    if isinstance(request, MemoryReadRequest) or request is None:
        requested_limit = request.limit if request is not None else None
        return PreparedOperationRequest(
            request=request, errors=(), requested_limit=requested_limit
        )
    return prepare_read_request(
        request,
        inferred_repo_id=inferred_repo_id,
        defaults=defaults or get_read_hydration_defaults(),
    )


def _prepare_recall(
    request: MemoryRecallRequest | dict[str, Any] | None,
    *,
    inferred_repo_id: str,
) -> PreparedOperationRequest[MemoryRecallRequest]:
    if isinstance(request, MemoryRecallRequest) or request is None:
        return PreparedOperationRequest(request=request, errors=())
    return prepare_recall_request(request, inferred_repo_id=inferred_repo_id)


def _prepare_events(
    request: EpisodeEventsRequest | dict[str, Any] | None,
    *,
    inferred_repo_id: str,
) -> PreparedOperationRequest[EpisodeEventsRequest]:
    if isinstance(request, EpisodeEventsRequest) or request is None:
        return PreparedOperationRequest(request=request, errors=())
    return prepare_events_request(request, inferred_repo_id=inferred_repo_id)
