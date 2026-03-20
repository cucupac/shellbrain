"""Logical backup helpers for Shellbrain databases."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from uuid import uuid4

import psycopg

from app.periphery.admin.instance_guard import PROTECTED_DB_NAMES, fetch_instance_metadata, fingerprint_summary


_UNSUPPORTED_RESTORE_PARAMETERS = ("transaction_timeout",)
_UNSUPPORTED_SET_LINE_RE = re.compile(r"^SET\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=")
_UNSUPPORTED_SET_CONFIG_RE = re.compile(r"^SELECT\s+pg_catalog\.set_config\('([a-zA-Z_][a-zA-Z0-9_]*)'")


@dataclass(frozen=True)
class BackupManifest:
    """Portable metadata stored next to one logical backup artifact."""

    backup_id: str
    instance_id: str
    instance_mode: str
    source: dict[str, str]
    schema_revision: str
    created_at: str
    artifact_filename: str
    artifact_sha256: str
    artifact_size_bytes: int
    compression: str


@dataclass(frozen=True)
class _ResolvedInstanceMetadata:
    """Minimal metadata used to bucket and label backup artifacts."""

    instance_id: str
    instance_mode: str


def create_backup(
    *,
    admin_dsn: str,
    backup_root: Path,
    mirror_root: Path | None = None,
    container_name: str | None = None,
    container_db_name: str | None = None,
    container_admin_user: str | None = None,
    container_admin_password: str | None = None,
) -> BackupManifest:
    """Create one compressed logical backup and return its manifest."""

    if container_name is None and shutil.which("pg_dump") is None:
        raise RuntimeError("pg_dump is required to create Shellbrain backups.")
    metadata = _resolve_instance_metadata(admin_dsn)
    schema_revision = _fetch_schema_revision(admin_dsn)
    created_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_id = uuid4().hex
    instance_dir = backup_root / metadata.instance_id
    instance_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = instance_dir / f"{created_at}-{backup_id}.sql.gz"
    manifest_path = instance_dir / f"{created_at}-{backup_id}.manifest.json"
    raw_dsn = admin_dsn.replace("+psycopg", "")

    command = _backup_command(
        admin_dsn=admin_dsn,
        container_name=container_name,
        container_db_name=container_db_name,
        container_admin_user=container_admin_user,
    )
    env = _backup_env(
        container_admin_password=container_admin_password,
    )
    popen_kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": False,
    }
    if env is not None:
        popen_kwargs["env"] = env
    with subprocess.Popen(command, **popen_kwargs) as process:
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {stderr.decode('utf-8', errors='replace').strip()}")
    with gzip.open(artifact_path, "wb") as handle:
        handle.write(stdout)

    manifest = BackupManifest(
        backup_id=backup_id,
        instance_id=metadata.instance_id,
        instance_mode=metadata.instance_mode,
        source=fingerprint_summary(admin_dsn),
        schema_revision=schema_revision,
        created_at=datetime.now(timezone.utc).isoformat(),
        artifact_filename=artifact_path.name,
        artifact_sha256=_sha256(artifact_path),
        artifact_size_bytes=artifact_path.stat().st_size,
        compression="gzip",
    )
    manifest_path.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True), encoding="utf-8")

    if mirror_root is not None:
        mirror_dir = mirror_root / metadata.instance_id
        mirror_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifact_path, mirror_dir / artifact_path.name)
        shutil.copy2(manifest_path, mirror_dir / manifest_path.name)
    return manifest


def list_backups(*, backup_root: Path) -> list[BackupManifest]:
    """Return every parseable backup manifest under the configured backup root."""

    if not backup_root.exists():
        return []
    manifests: list[BackupManifest] = []
    for path in sorted(backup_root.rglob("*.manifest.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        manifests.append(BackupManifest(**payload))
    return sorted(manifests, key=lambda item: item.created_at, reverse=True)


def verify_backup(*, backup_root: Path, backup_id: str | None = None) -> BackupManifest:
    """Verify one backup manifest and artifact hash, defaulting to the newest artifact."""

    manifest = resolve_backup(backup_root=backup_root, backup_id=backup_id)
    artifact_path = backup_root / manifest.instance_id / manifest.artifact_filename
    if not artifact_path.exists():
        raise RuntimeError(f"Backup artifact is missing: {artifact_path}")
    actual_sha256 = _sha256(artifact_path)
    if actual_sha256 != manifest.artifact_sha256:
        raise RuntimeError("Backup artifact hash mismatch.")
    return manifest


def resolve_backup(*, backup_root: Path, backup_id: str | None = None) -> BackupManifest:
    """Resolve one manifest by id, defaulting to the newest available backup."""

    manifests = list_backups(backup_root=backup_root)
    if not manifests:
        raise RuntimeError("No Shellbrain backups are available.")
    if backup_id is None:
        return manifests[0]
    for manifest in manifests:
        if manifest.backup_id == backup_id:
            return manifest
    raise RuntimeError(f"Backup id not found: {backup_id}")


def restore_backup(
    *,
    admin_dsn: str,
    backup_root: Path,
    target_db: str,
    app_dsn: str | None = None,
    backup_id: str | None = None,
    container_name: str | None = None,
    container_admin_user: str | None = None,
    container_admin_password: str | None = None,
) -> BackupManifest:
    """Restore one verified backup into a new scratch database."""

    if container_name is None and shutil.which("psql") is None:
        raise RuntimeError("psql is required to restore Shellbrain backups.")
    if target_db.lower() in PROTECTED_DB_NAMES:
        raise RuntimeError(
            f"Refusing to restore into protected database name '{target_db}'. Use a fresh scratch database name."
        )
    manifest = verify_backup(backup_root=backup_root, backup_id=backup_id)
    artifact_path = backup_root / manifest.instance_id / manifest.artifact_filename
    raw_admin_dsn = admin_dsn.replace("+psycopg", "")
    _create_empty_database(admin_dsn=admin_dsn, target_db=target_db)
    target_dsn = _replace_database(raw_admin_dsn, target_db)
    with gzip.open(artifact_path, "rb") as handle:
        restored_sql = _sanitize_restore_sql(handle.read())
    run_kwargs = {
        "input": restored_sql,
        "capture_output": True,
        "check": False,
    }
    env = _backup_env(container_admin_password=container_admin_password)
    if env is not None:
        run_kwargs["env"] = env
    process = subprocess.run(
        _restore_command(
            target_dsn=target_dsn,
            target_db=target_db,
            container_name=container_name,
            container_admin_user=container_admin_user,
        ),
        **run_kwargs,
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace").strip() or "psql restore failed")
    from app.periphery.admin.instance_guard import ensure_instance_metadata

    target_admin_dsn = _replace_database(admin_dsn, target_db)
    ensure_instance_metadata(
        target_admin_dsn,
        instance_mode="scratch",
        created_by="app.admin.restore",
        notes=f"Restored from backup {manifest.backup_id}",
    )
    if app_dsn:
        from app.periphery.admin.privileges import reconcile_app_role_privileges

        target_app_dsn = _replace_database(app_dsn, target_db)
        reconcile_app_role_privileges(admin_dsn=target_admin_dsn, app_dsn=target_app_dsn)
    return manifest


def _resolve_instance_metadata(admin_dsn: str) -> _ResolvedInstanceMetadata:
    """Resolve stored instance metadata, or synthesize a stable fallback label."""

    metadata = fetch_instance_metadata(admin_dsn)
    if metadata is not None:
        return _ResolvedInstanceMetadata(
            instance_id=metadata.instance_id,
            instance_mode=metadata.instance_mode,
        )
    source = fingerprint_summary(admin_dsn)
    return _ResolvedInstanceMetadata(
        instance_id=source["fingerprint"],
        instance_mode="unknown",
    )


def _backup_command(
    *,
    admin_dsn: str,
    container_name: str | None,
    container_db_name: str | None,
    container_admin_user: str | None,
) -> list[str]:
    """Return the pg_dump command for host or managed-container execution."""

    if container_name is None:
        raw_dsn = admin_dsn.replace("+psycopg", "")
        return ["pg_dump", "--no-owner", "--no-privileges", f"--dbname={raw_dsn}"]
    if not container_db_name or not container_admin_user:
        raise RuntimeError("Managed container backups require container DB name and admin user.")
    return [
        "docker",
        "exec",
        "-e",
        "PGPASSWORD",
        container_name,
        "pg_dump",
        "--no-owner",
        "--no-privileges",
        "--username",
        container_admin_user,
        "--dbname",
        container_db_name,
    ]


def _restore_command(
    *,
    target_dsn: str,
    target_db: str,
    container_name: str | None,
    container_admin_user: str | None,
) -> list[str]:
    """Return the psql command for host or managed-container restore execution."""

    if container_name is None:
        return ["psql", "--set", "ON_ERROR_STOP=1", f"--dbname={target_dsn}"]
    if not container_admin_user:
        raise RuntimeError("Managed container restore requires the container admin user.")
    return [
        "docker",
        "exec",
        "-i",
        "-e",
        "PGPASSWORD",
        container_name,
        "psql",
        "--set",
        "ON_ERROR_STOP=1",
        "--username",
        container_admin_user,
        "--dbname",
        target_db,
    ]


def _backup_env(*, container_admin_password: str | None) -> dict[str, str] | None:
    """Return subprocess environment overrides for managed-container operations."""

    if container_admin_password is None:
        return None
    env = os.environ.copy()
    env["PGPASSWORD"] = container_admin_password
    return env


def _create_empty_database(*, admin_dsn: str, target_db: str) -> None:
    """Create one empty restore target database, failing if it already exists."""

    raw_admin_dsn = admin_dsn.replace("+psycopg", "")
    postgres_dsn = _replace_database(raw_admin_dsn, "postgres")
    with psycopg.connect(postgres_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
            if cur.fetchone() is not None:
                raise RuntimeError(f"Target database already exists: {target_db}")
            cur.execute(f'CREATE DATABASE "{target_db}"')


def _fetch_schema_revision(admin_dsn: str) -> str:
    """Read the current alembic revision for manifest metadata."""

    raw_dsn = admin_dsn.replace("+psycopg", "")
    with psycopg.connect(raw_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version_num FROM alembic_version")
            return str(cur.fetchone()[0])


def _replace_database(dsn: str, db_name: str) -> str:
    """Replace the database path portion of one DSN string."""

    prefix, _, _ = dsn.rpartition("/")
    return f"{prefix}/{db_name}"


def _sha256(path: Path) -> str:
    """Compute one stable SHA-256 hash for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sanitize_restore_sql(dump_bytes: bytes) -> bytes:
    """Strip session settings that newer pg_dump versions emit but older servers reject."""

    filtered: list[bytes] = []
    for line in dump_bytes.splitlines(keepends=True):
        decoded = line.decode("utf-8", errors="replace").strip()
        set_match = _UNSUPPORTED_SET_LINE_RE.match(decoded)
        if set_match and set_match.group(1) in _UNSUPPORTED_RESTORE_PARAMETERS:
            continue
        set_config_match = _UNSUPPORTED_SET_CONFIG_RE.match(decoded)
        if set_config_match and set_config_match.group(1) in _UNSUPPORTED_RESTORE_PARAMETERS:
            continue
        filtered.append(line)
    return b"".join(filtered)
