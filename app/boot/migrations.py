"""Packaged Alembic bootstrap helpers for installed-shellbrain database migrations."""

from __future__ import annotations

from importlib.resources import as_file, files

from alembic import command
from alembic.config import Config

from app.boot.admin_db import get_admin_db_dsn, get_backup_dir, get_backup_mirror_dir, get_instance_mode_default
from app.boot.db import get_optional_db_dsn
from app.periphery.admin.destructive_guard import backup_and_verify_before_destructive_action
from app.periphery.admin.instance_guard import ensure_instance_metadata, fetch_instance_metadata
from app.periphery.admin.privileges import reconcile_app_role_privileges


def upgrade_database(revision: str = "head") -> None:
    """Apply packaged Alembic migrations to the configured database."""

    config = Config()
    admin_dsn = get_admin_db_dsn()
    if _database_has_shellbrain_objects(admin_dsn):
        backup_and_verify_before_destructive_action(
            admin_dsn=admin_dsn,
            backup_root=get_backup_dir(),
            mirror_root=get_backup_mirror_dir(),
        )
    config.set_main_option("sqlalchemy.url", admin_dsn)
    with as_file(files("app").joinpath("migrations")) as migrations_path:
        config.set_main_option("script_location", str(migrations_path))
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


def _database_has_shellbrain_objects(admin_dsn: str) -> bool:
    """Return whether the target database already contains Shellbrain-managed tables."""

    import psycopg

    with psycopg.connect(admin_dsn.replace("+psycopg", "")) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                  SELECT 1
                  FROM information_schema.tables
                  WHERE table_schema = 'public'
                    AND table_name IN ('memories', 'episodes', 'episode_events', 'operation_invocations')
                )
                """
            )
            return bool(cur.fetchone()[0])
