"""Postgres connection probes used by admin/runtime workflows."""

from __future__ import annotations

import time

import psycopg

from app.core.entities.admin_errors import InitConflictError


def wait_for_postgres(admin_dsn: str, *, timeout_seconds: int = 45) -> None:
    """Wait for the configured PostgreSQL runtime to accept connections."""

    deadline = time.time() + timeout_seconds
    raw_dsn = admin_dsn.replace("+psycopg", "")
    while True:
        try:
            with psycopg.connect(raw_dsn, connect_timeout=2):
                return
        except psycopg.Error:
            if time.time() >= deadline:
                raise InitConflictError(
                    "Shellbrain PostgreSQL runtime did not become ready in time."
                )
            time.sleep(1)


def fetch_schema_revision(dsn: str) -> str | None:
    """Best-effort read of the current alembic revision."""

    try:
        with psycopg.connect(dsn.replace("+psycopg", "")) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version_num FROM alembic_version")
                row = cur.fetchone()
    except psycopg.Error:
        return None
    if row is None or row[0] is None:
        return None
    return str(row[0])


def database_has_shellbrain_objects(admin_dsn: str) -> bool:
    """Return whether the target database already contains Shellbrain-managed tables."""

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
