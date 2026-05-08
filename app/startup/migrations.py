"""Packaged Alembic bootstrap helpers for installed-shellbrain database migrations."""

from __future__ import annotations

from importlib.resources import as_file, files
import importlib.metadata

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.script.revision import ResolutionError

from app.startup.admin_db import get_admin_db_dsn, get_backup_dir, get_backup_mirror_dir, get_instance_mode_default
from app.startup.db import get_optional_db_dsn
from app.infrastructure.postgres_admin.connection import database_has_shellbrain_objects, fetch_schema_revision
from app.infrastructure.postgres_admin.destructive_guard import backup_and_verify_before_destructive_action
from app.infrastructure.postgres_admin.instance_guard import ensure_instance_metadata, fetch_instance_metadata
from app.infrastructure.postgres_admin.privileges import reconcile_app_role_privileges


class DatabaseRevisionAheadOfInstalledPackageError(RuntimeError):
    """Raised when the target database revision is newer than the installed package knows about."""


def upgrade_database(revision: str = "head") -> None:
    """Apply packaged Alembic migrations to the configured database."""

    config = Config()
    admin_dsn = get_admin_db_dsn()
    with as_file(files("migrations")) as migrations_path:
        config.set_main_option("script_location", str(migrations_path))
        script = ScriptDirectory.from_config(config)
        if database_has_shellbrain_objects(admin_dsn):
            _assert_database_revision_is_known(admin_dsn=admin_dsn, script=script)
            backup_and_verify_before_destructive_action(
                admin_dsn=admin_dsn,
                backup_root=get_backup_dir(),
                mirror_root=get_backup_mirror_dir(),
            )
        config.set_main_option("sqlalchemy.url", admin_dsn)
        command.upgrade(config, revision)
    if fetch_instance_metadata(admin_dsn) is None:
        ensure_instance_metadata(
            admin_dsn,
            instance_mode=get_instance_mode_default(),
            created_by="app.admin.migrate",
            notes="Stamped by packaged migration runner.",
        )
    app_dsn = get_optional_db_dsn()
    if app_dsn:
        reconcile_app_role_privileges(admin_dsn=admin_dsn, app_dsn=app_dsn)


def _assert_database_revision_is_known(*, admin_dsn: str, script: ScriptDirectory) -> None:
    """Fail early with a user-facing error when the database revision is newer than this package."""

    current_revision = fetch_schema_revision(admin_dsn)
    if current_revision is None:
        return
    try:
        script.get_revision(current_revision)
    except ResolutionError as exc:
        installed_version = _installed_shellbrain_version()
        raise DatabaseRevisionAheadOfInstalledPackageError(
            "Installed Shellbrain package "
            f"({installed_version}) cannot manage database revision {current_revision}. "
            "This database was likely migrated by a newer Shellbrain release than the one currently installed. "
            "Upgrade Shellbrain to a build that includes this revision, then rerun `shellbrain init` or "
            "`shellbrain admin migrate`."
        ) from exc


def _installed_shellbrain_version() -> str:
    """Return the installed Shellbrain package version when available."""

    try:
        return importlib.metadata.version("shellbrain")
    except importlib.metadata.PackageNotFoundError:
        return "dev"
