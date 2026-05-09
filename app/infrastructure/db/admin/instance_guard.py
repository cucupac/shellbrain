"""Guards that classify DB instances and refuse destructive actions on live targets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Final
from urllib.parse import urlparse

import psycopg


LIVE: Final[str] = "live"
TEST: Final[str] = "test"
SCRATCH: Final[str] = "scratch"
ALLOWED_INSTANCE_MODES: Final[set[str]] = {LIVE, TEST, SCRATCH}
PROTECTED_DB_NAMES: Final[set[str]] = {"shellbrain", "memory"}


@dataclass(frozen=True)
class InstanceMetadataRecord:
    """Minimal typed view of one instance_metadata row."""

    instance_id: str
    instance_mode: str
    created_at: str
    created_by: str
    notes: str | None = None


def normalize_dsn(dsn: str) -> str:
    """Normalize a DSN into a stable fingerprint source string."""

    parsed = urlparse(dsn.replace("+psycopg", ""))
    hostname = (parsed.hostname or "").lower()
    port = parsed.port or 5432
    db_name = parsed.path.lstrip("/")
    return f"{hostname}:{port}/{db_name}"


def dsn_fingerprint(dsn: str) -> str:
    """Hash a normalized DSN to compare protected targets without exposing passwords."""

    return hashlib.sha256(normalize_dsn(dsn).encode("utf-8")).hexdigest()


def host_port_from_dsn(dsn: str) -> tuple[str, int]:
    """Extract the normalized host/port pair from one DSN."""

    parsed = urlparse(dsn.replace("+psycopg", ""))
    return ((parsed.hostname or "").lower(), parsed.port or 5432)


def database_name_from_dsn(dsn: str) -> str:
    """Extract the target database name from one DSN."""

    return urlparse(dsn.replace("+psycopg", "")).path.lstrip("/")


def assert_disposable_test_dsn(
    *,
    test_dsn: str,
    protected_dsn: str | None = None,
    protected_host_ports: set[tuple[str, int]] | None = None,
) -> None:
    """Refuse to treat a protected or production-shaped database as disposable."""

    if protected_dsn and dsn_fingerprint(test_dsn) == dsn_fingerprint(protected_dsn):
        raise RuntimeError(
            "Refusing destructive test setup against the protected live database DSN."
        )
    protected_pairs = set(protected_host_ports or set())
    if protected_dsn:
        protected_pairs.add(host_port_from_dsn(protected_dsn))
    if host_port_from_dsn(test_dsn) in protected_pairs:
        raise RuntimeError(
            "Refusing destructive test setup against the protected live database host/port."
        )
    db_name = database_name_from_dsn(test_dsn).lower()
    if db_name in PROTECTED_DB_NAMES:
        raise RuntimeError(
            f"Refusing destructive test setup against protected database '{db_name}'. "
            "Use an explicitly disposable scratch/test database name."
        )


def ensure_instance_metadata(
    dsn: str,
    *,
    instance_mode: str,
    created_by: str,
    notes: str | None = None,
) -> InstanceMetadataRecord:
    """Create or preserve one instance_metadata row for the target database."""

    if instance_mode not in ALLOWED_INSTANCE_MODES:
        raise ValueError(f"Unsupported instance mode: {instance_mode}")
    raw_dsn = dsn.replace("+psycopg", "")
    instance_id = dsn_fingerprint(dsn)
    created_at = datetime.now(timezone.utc).isoformat()
    with psycopg.connect(raw_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS instance_metadata (
                  instance_id TEXT PRIMARY KEY,
                  instance_mode TEXT NOT NULL,
                  created_at TIMESTAMPTZ NOT NULL,
                  created_by TEXT NOT NULL,
                  notes TEXT NULL
                )
                """
            )
            cur.execute(
                """
                INSERT INTO instance_metadata (instance_id, instance_mode, created_at, created_by, notes)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (instance_id) DO NOTHING
                """,
                (instance_id, instance_mode, created_at, created_by, notes),
            )
        conn.commit()
    record = fetch_instance_metadata(dsn, include_legacy_lookup=False)
    if record is None:
        raise RuntimeError("Failed to persist instance metadata.")
    return record


def fetch_instance_metadata(
    dsn: str, *, include_legacy_lookup: bool = True
) -> InstanceMetadataRecord | None:
    """Read one instance_metadata row when the safety table exists."""

    raw_dsn = dsn.replace("+psycopg", "")
    instance_ids = [dsn_fingerprint(dsn)]
    if include_legacy_lookup:
        instance_ids.append(_legacy_dsn_fingerprint(dsn))
    try:
        with psycopg.connect(raw_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.instance_metadata');")
                if cur.fetchone()[0] is None:
                    return None
                row = None
                for instance_id in instance_ids:
                    cur.execute(
                        """
                        SELECT instance_id, instance_mode, created_at::text, created_by, notes
                        FROM instance_metadata
                        WHERE instance_id = %s
                        """,
                        (instance_id,),
                    )
                    row = cur.fetchone()
                    if row is not None:
                        break
    except psycopg.Error:
        return None
    if row is None:
        return None
    return InstanceMetadataRecord(*row)


def assert_destructive_allowed(
    dsn: str, *, allowed_modes: tuple[str, ...] = (TEST, SCRATCH)
) -> None:
    """Fail closed unless the target database is explicitly classified as disposable."""

    record = fetch_instance_metadata(dsn)
    if record is None:
        raise RuntimeError(
            "Refusing destructive action because instance metadata is missing. "
            "Stamp the database as test or scratch first."
        )
    if record.instance_mode not in allowed_modes:
        raise RuntimeError(
            f"Refusing destructive action against instance_mode={record.instance_mode!r}. "
            f"Allowed modes: {', '.join(allowed_modes)}."
        )


def inspect_role_safety(dsn: str) -> list[str]:
    """Return warnings when the provided DSN points at a dangerously privileged role."""

    warnings: list[str] = []
    raw_dsn = dsn.replace("+psycopg", "")
    try:
        with psycopg.connect(raw_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT r.rolsuper,
                           pg_has_role(current_user, 'pg_database_owner', 'member'),
                           has_schema_privilege(current_user, 'public', 'CREATE')
                    FROM pg_roles r
                    WHERE r.rolname = current_user
                    """
                )
                row = cur.fetchone()
    except psycopg.Error as exc:
        return [f"Could not audit DB role safety: {exc}"]
    if row is None:
        return warnings
    is_superuser, is_db_owner, can_create_in_public = row
    if is_superuser:
        warnings.append("Current DSN role is superuser-capable.")
    if is_db_owner:
        warnings.append("Current DSN role is a database owner.")
    if can_create_in_public:
        warnings.append("Current DSN role can CREATE in schema public.")
    return warnings


def fingerprint_summary(dsn: str) -> dict[str, str]:
    """Return one printable DB identity summary for diagnostics and manifests."""

    parsed = urlparse(dsn.replace("+psycopg", ""))
    return {
        "fingerprint": dsn_fingerprint(dsn),
        "host": parsed.hostname or "",
        "port": str(parsed.port or 5432),
        "database": parsed.path.lstrip("/"),
        "user": parsed.username or "",
    }


def _legacy_dsn_fingerprint(dsn: str) -> str:
    """Compute the legacy fingerprint that also included the username."""

    parsed = urlparse(dsn.replace("+psycopg", ""))
    hostname = (parsed.hostname or "").lower()
    port = parsed.port or 5432
    db_name = parsed.path.lstrip("/")
    user = parsed.username or ""
    return hashlib.sha256(
        f"{hostname}:{port}/{db_name}?user={user}".encode("utf-8")
    ).hexdigest()
