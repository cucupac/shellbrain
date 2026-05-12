"""Composition wrapper for Shellbrain doctor diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any

from app.core.use_cases.admin.diagnose_runtime import (
    DiagnoseRuntimePorts,
    build_diagnose_runtime_report,
)
from app.core.entities.machine_config import (
    RUNTIME_MODE_EXTERNAL_POSTGRES,
    RUNTIME_MODE_MANAGED_LOCAL,
)
from app.infrastructure.host_apps.assets import inspect_host_assets
from app.infrastructure.local_state.machine_config_store import try_load_machine_config
from app.infrastructure.local_state.paths import get_shellbrain_home
from app.infrastructure.local_state.repo_registration_store import (
    IDENTITY_STRENGTH_WEAK_LOCAL,
    load_repo_registration_for_target,
    resolve_git_root,
)
from app.infrastructure.db.admin.connection import fetch_schema_revision
from app.infrastructure.db.admin.instance_guard import (
    fetch_instance_metadata,
    fingerprint_summary,
    inspect_role_safety,
)
from app.infrastructure.db.admin.backups.logical_backup import list_backups
from app.infrastructure.db.admin.provisioning import (
    external_postgres as external_runtime,
)


def build_doctor_report(
    *,
    app_dsn: str | None,
    admin_dsn: str | None,
    backup_root: Path,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Wire concrete diagnostic probes and return one doctor report."""

    return build_diagnose_runtime_report(
        app_dsn=app_dsn,
        admin_dsn=admin_dsn,
        backup_root=backup_root,
        repo_root=repo_root,
        ports=DiagnoseRuntimePorts(
            load_machine_config=try_load_machine_config,
            fetch_instance_metadata=fetch_instance_metadata,
            list_backups=list_backups,
            inspect_role_safety=inspect_role_safety,
            fetch_schema_revision=fetch_schema_revision,
            get_shellbrain_home=get_shellbrain_home,
            disk_usage=shutil.disk_usage,
            now=lambda: datetime.now(timezone.utc),
            path_exists=Path.exists,
            serialize_backup_manifest=lambda backup: dict(backup.__dict__),
            inspect_host_assets=inspect_host_assets,
            resolve_git_root=resolve_git_root,
            load_repo_registration_for_target=load_repo_registration_for_target,
            inspect_external_runtime=external_runtime.inspect_runtime,
            fingerprint_summary=fingerprint_summary,
            identity_strength_weak_local=IDENTITY_STRENGTH_WEAK_LOCAL,
            runtime_mode_external_postgres=RUNTIME_MODE_EXTERNAL_POSTGRES,
            runtime_mode_managed_local=RUNTIME_MODE_MANAGED_LOCAL,
        ),
    )
