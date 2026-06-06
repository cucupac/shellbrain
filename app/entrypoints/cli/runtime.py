"""Entrypoint-facing CLI runtime protocol."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class CliRuntime(Protocol):
    """Startup-composed behavior consumed by the CLI runner."""

    resolve_repo_context: Callable[..., Any]
    build_operation_dependencies: Callable[[], Any]
    get_create_hydration_defaults: Callable[[], dict[str, Any]]
    get_read_hydration_defaults: Callable[[], dict[str, Any]]
    get_uow_factory: Callable[[], Any]
    get_embedding_provider_factory: Callable[[], Any]
    get_embedding_model: Callable[[], str]
    get_operation_telemetry_context: Callable[[], Any]
    new_invocation_id: Callable[[], str]
    resolve_caller_identity: Callable[[], Any]
    set_operation_context: Callable[[Any], Any]
    reset_operation_context: Callable[[Any], None]
    ensure_repo_registration: Callable[..., None]
    ensure_shadow_baseline: Callable[..., None]
    maybe_start_sync: Callable[[Any], bool]
    update_operation_polling_status: Callable[..., None]
    should_register_repo_during_init: Callable[..., bool]
    run_init: Callable[..., Any]
    init_success_presenter_context: Callable[[], dict[str, Any]]
    run_upgrade_command: Callable[[], int]
    warn_or_fail_on_unsafe_app_role: Callable[[], None]
    run_metrics_dashboard: Callable[..., object]
    run_wiki: Callable[..., int]
    admin_dependencies: Any
