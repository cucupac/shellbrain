"""External PostgreSQL runtime helpers for Shellbrain init."""

from __future__ import annotations

import importlib.metadata
import secrets

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.infrastructure.local_state.paths import (
    get_machine_backups_dir,
    get_machine_models_dir,
)
from app.core.entities.admin_errors import InitConflictError
from app.infrastructure.db.admin.instance_guard import (
    dsn_fingerprint,
    ensure_instance_metadata,
)
from app.core.entities.machine_config import (
    BOOTSTRAP_STATE_PROVISIONING,
    BOOTSTRAP_VERSION,
    CONFIG_VERSION,
    BackupState,
    DatabaseState,
    EmbeddingRuntimeState,
    MachineConfig,
    RUNTIME_MODE_EXTERNAL_POSTGRES,
)
from app.infrastructure.db.admin.privileges import reconcile_app_role_privileges


DEFAULT_EXTERNAL_APP_USER = "shellbrain_app"


def build_fresh_machine_config(
    *, admin_dsn: str, embeddings: dict[str, object]
) -> MachineConfig:
    """Construct one fresh machine config for external PostgreSQL mode."""

    if not isinstance(embeddings, dict):
        raise RuntimeError("runtime.embeddings must be configured")
    app_dsn = _provision_external_app_role(admin_dsn=admin_dsn)
    instance_id = dsn_fingerprint(admin_dsn)
    backend_version = _sentence_transformers_version()
    return MachineConfig(
        config_version=CONFIG_VERSION,
        bootstrap_version=BOOTSTRAP_VERSION,
        instance_id=instance_id,
        runtime_mode=RUNTIME_MODE_EXTERNAL_POSTGRES,
        bootstrap_state=BOOTSTRAP_STATE_PROVISIONING,
        current_step="bootstrap",
        last_error=None,
        database=DatabaseState(app_dsn=app_dsn, admin_dsn=admin_dsn),
        managed=None,
        backups=BackupState(root=str(get_machine_backups_dir()), mirror_root=None),
        embeddings=EmbeddingRuntimeState(
            provider=str(embeddings.get("provider") or "sentence_transformers"),
            model=str(embeddings.get("model") or "all-MiniLM-L6-v2"),
            model_revision=None,
            backend_version=backend_version,
            cache_path=str(get_machine_models_dir()),
            readiness_state="pending",
            last_error=None,
        ),
    )


def reconcile_database(config: MachineConfig) -> tuple[bool, MachineConfig]:
    """Validate one external PostgreSQL database and reconcile the Shellbrain app role."""

    if config.runtime_mode != RUNTIME_MODE_EXTERNAL_POSTGRES:
        raise InitConflictError(
            "External runtime reconciliation requires external_postgres mode."
        )
    _validate_external_admin_dsn(config.database.admin_dsn)
    app_dsn = _provision_external_app_role(
        admin_dsn=config.database.admin_dsn,
        existing_app_dsn=config.database.app_dsn,
    )
    ensure_instance_metadata(
        config.database.admin_dsn,
        instance_mode="live",
        created_by="app.init",
        notes="External PostgreSQL Shellbrain instance",
    )
    if app_dsn == config.database.app_dsn:
        return False, config
    updated = MachineConfig(
        config_version=config.config_version,
        bootstrap_version=config.bootstrap_version,
        instance_id=config.instance_id,
        runtime_mode=config.runtime_mode,
        bootstrap_state=config.bootstrap_state,
        current_step=config.current_step,
        last_error=config.last_error,
        database=DatabaseState(app_dsn=app_dsn, admin_dsn=config.database.admin_dsn),
        managed=config.managed,
        backups=config.backups,
        embeddings=config.embeddings,
    )
    return True, updated


def inspect_runtime(*, admin_dsn: str) -> list[str]:
    """Return best-effort warnings for one external PostgreSQL runtime."""

    warnings: list[str] = []
    try:
        _validate_external_admin_dsn(admin_dsn)
    except InitConflictError as exc:
        warnings.append(str(exc))
    return warnings


def _validate_external_admin_dsn(admin_dsn: str) -> None:
    """Verify the external admin DSN reaches PostgreSQL with pgvector available."""

    raw_admin_dsn = admin_dsn.replace("+psycopg", "")
    try:
        with psycopg.connect(raw_admin_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                version_row = cur.fetchone()
                if version_row is None or "PostgreSQL" not in str(version_row[0]):
                    raise InitConflictError("External database must be PostgreSQL.")
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                except psycopg.Error as exc:
                    raise InitConflictError(
                        "External PostgreSQL database must have pgvector available to install or already installed."
                    ) from exc
                cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
                if cur.fetchone() is None:
                    raise InitConflictError(
                        "External PostgreSQL database must have the pgvector extension installed."
                    )
    except InitConflictError:
        raise
    except psycopg.Error as exc:
        raise InitConflictError(
            f"Could not connect to the external PostgreSQL admin DSN: {exc}"
        ) from exc


def _provision_external_app_role(
    *, admin_dsn: str, existing_app_dsn: str | None = None
) -> str:
    """Create or repair the dedicated Shellbrain app role for one external database."""

    app_user = DEFAULT_EXTERNAL_APP_USER
    app_password = None
    if existing_app_dsn:
        app_url = make_url(existing_app_dsn)
        app_user = app_url.username or DEFAULT_EXTERNAL_APP_USER
        app_password = app_url.password
    if not app_password:
        app_password = secrets.token_hex(16)
    app_dsn = _app_dsn_from_admin_dsn(
        admin_dsn=admin_dsn, app_user=app_user, app_password=app_password
    )
    raw_admin_dsn = admin_dsn.replace("+psycopg", "")
    database_name = make_url(admin_dsn).database
    if not database_name:
        raise InitConflictError(
            "External PostgreSQL admin DSN must include a database name."
        )
    try:
        with psycopg.connect(raw_admin_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (app_user,))
                if cur.fetchone() is None:
                    cur.execute(
                        sql.SQL(
                            "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}"
                        ).format(
                            sql.Identifier(app_user),
                            sql.Literal(app_password),
                        ),
                    )
                else:
                    cur.execute(
                        sql.SQL("ALTER ROLE {} WITH PASSWORD {}").format(
                            sql.Identifier(app_user),
                            sql.Literal(app_password),
                        ),
                    )
                cur.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(database_name),
                        sql.Identifier(app_user),
                    )
                )
    except psycopg.Error as exc:
        raise InitConflictError(
            f"Could not provision the external Shellbrain app role: {exc}"
        ) from exc
    reconcile_app_role_privileges(admin_dsn=admin_dsn, app_dsn=app_dsn)
    return app_dsn


def _app_dsn_from_admin_dsn(*, admin_dsn: str, app_user: str, app_password: str) -> str:
    """Build one Shellbrain app DSN from the external admin DSN shape."""

    url = make_url(admin_dsn)
    return str(url.set(username=app_user, password=app_password))


def _sentence_transformers_version() -> str | None:
    """Return the installed sentence-transformers version when present."""

    try:
        return importlib.metadata.version("sentence-transformers")
    except importlib.metadata.PackageNotFoundError:
        return None
