"""App-role safety checks for CLI command execution."""

from __future__ import annotations

from typing import TextIO

from app.infrastructure.db.admin import instance_guard


def warn_or_fail_on_unsafe_app_role(
    *,
    get_db_dsn,
    should_fail_on_unsafe_app_role,
    stderr: TextIO,
) -> None:
    """Emit one warning, or fail in strict mode, when the app DSN is overprivileged."""

    dsn = get_db_dsn()
    warnings = instance_guard.inspect_role_safety(dsn)
    if not warnings:
        return
    message = "Unsafe Shellbrain app-role configuration:\n- " + "\n- ".join(warnings)
    metadata = instance_guard.fetch_instance_metadata(dsn)
    if metadata is not None and metadata.instance_mode in {
        instance_guard.TEST,
        instance_guard.SCRATCH,
    }:
        print(message, file=stderr)
        return
    if should_fail_on_unsafe_app_role():
        raise ValueError(message)
    print(message, file=stderr)
