"""Admin helpers that reconcile safe runtime privileges for the app role."""

from __future__ import annotations

from urllib.parse import urlparse

import psycopg


def reconcile_app_role_privileges(*, admin_dsn: str, app_dsn: str) -> None:
    """Grant only the DML/runtime privileges the app role needs after admin migrations."""

    app_user = _username_from_dsn(app_dsn)
    if not app_user:
        raise RuntimeError(
            "Could not determine the app-role username from SHELLBRAIN_DB_DSN."
        )

    raw_admin_dsn = admin_dsn.replace("+psycopg", "")
    with psycopg.connect(raw_admin_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            cur.execute(f'REVOKE CREATE ON SCHEMA public FROM "{app_user}"')
            cur.execute(f'GRANT USAGE ON SCHEMA public TO "{app_user}"')
            cur.execute(
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{app_user}"'
            )
            cur.execute(
                f'GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO "{app_user}"'
            )
            cur.execute(
                f"ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA public "
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{app_user}"'
            )
            cur.execute(
                f"ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA public "
                f'GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO "{app_user}"'
            )


def _username_from_dsn(dsn: str) -> str:
    """Extract the username from one DSN."""

    return urlparse(dsn.replace("+psycopg", "")).username or ""
