"""Interactive and flag-driven storage selection for Shellbrain init."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import TextIO

from app.core.entities.admin_errors import InitConflictError, InitDependencyError
from app.infrastructure.local_state.machine_config_store import (
    MachineConfig,
    RUNTIME_MODE_EXTERNAL_POSTGRES,
    RUNTIME_MODE_MANAGED_LOCAL,
)


STORAGE_FLAG_MANAGED = "managed"
STORAGE_FLAG_EXTERNAL = "external"

_MANAGED_PROMPT_TEXT = (
    "Set up a local PostgreSQL + pgvector database for me (recommended)"
)
_EXTERNAL_PROMPT_TEXT = "Use an existing PostgreSQL + pgvector database"
_NON_INTERACTIVE_MESSAGE = (
    "Shellbrain init needs a storage choice on first bootstrap. "
    "Rerun interactively or pass --storage managed or --storage external --admin-dsn <dsn>."
)


@dataclass(frozen=True)
class StorageSelection:
    """Normalized storage-selection input for one init run."""

    runtime_mode: str
    admin_dsn: str | None = None


def resolve_storage_selection(
    *,
    existing_config: MachineConfig | None,
    storage_flag: str | None,
    admin_dsn_flag: str | None,
) -> StorageSelection:
    """Resolve one storage selection from flags, config, or an interactive prompt."""

    normalized_flag = _normalize_storage_flag(storage_flag)
    normalized_admin_dsn = _normalize_admin_dsn(admin_dsn_flag)

    if existing_config is not None:
        if (
            normalized_flag is not None
            and normalized_flag != existing_config.runtime_mode
        ):
            raise InitConflictError(
                "Shellbrain init cannot switch storage modes while a machine config already exists. "
                "Repair or remove the current machine config first."
            )
        if normalized_admin_dsn is not None:
            raise InitConflictError(
                "Shellbrain init cannot replace the configured external database while a machine config already exists."
            )
        return StorageSelection(
            runtime_mode=existing_config.runtime_mode,
            admin_dsn=existing_config.database.admin_dsn,
        )

    runtime_mode = normalized_flag
    admin_dsn = normalized_admin_dsn
    if runtime_mode is None:
        runtime_mode = _prompt_for_storage_mode()

    if runtime_mode == RUNTIME_MODE_EXTERNAL_POSTGRES and admin_dsn is None:
        admin_dsn = _prompt_for_admin_dsn()
    if runtime_mode == RUNTIME_MODE_EXTERNAL_POSTGRES and admin_dsn is None:
        raise InitDependencyError(_NON_INTERACTIVE_MESSAGE)
    return StorageSelection(runtime_mode=runtime_mode, admin_dsn=admin_dsn)


def _normalize_storage_flag(storage_flag: str | None) -> str | None:
    """Map one CLI storage flag to the persisted runtime mode."""

    if storage_flag is None:
        return None
    normalized = storage_flag.strip().lower()
    if normalized == STORAGE_FLAG_MANAGED:
        return RUNTIME_MODE_MANAGED_LOCAL
    if normalized == STORAGE_FLAG_EXTERNAL:
        return RUNTIME_MODE_EXTERNAL_POSTGRES
    raise InitDependencyError(f"Unsupported storage mode: {storage_flag!r}")


def _normalize_admin_dsn(admin_dsn: str | None) -> str | None:
    """Return a trimmed admin DSN when present."""

    if admin_dsn is None:
        return None
    normalized = admin_dsn.strip()
    return normalized or None


def _prompt_for_storage_mode() -> str:
    """Prompt the user for the first-bootstrap storage mode."""

    reader, writer, handle = _open_interactive_stream()
    try:
        writer.write("How should Shellbrain store its data?\n")
        writer.write(f"1. {_MANAGED_PROMPT_TEXT}\n")
        writer.write(f"2. {_EXTERNAL_PROMPT_TEXT}\n")
        while True:
            writer.write("Choose 1 or 2 [1]: ")
            writer.flush()
            answer = reader.readline()
            if answer == "":
                raise InitDependencyError(
                    "Shellbrain init was interrupted before a storage mode was selected."
                )
            normalized = answer.strip().lower()
            if normalized in {"", "1", "managed", "local"}:
                return RUNTIME_MODE_MANAGED_LOCAL
            if normalized in {"2", "external", "postgres", "postgresql"}:
                return RUNTIME_MODE_EXTERNAL_POSTGRES
            writer.write("Please enter 1 or 2.\n")
    finally:
        _close_interactive_stream(handle)


def _prompt_for_admin_dsn() -> str | None:
    """Prompt for the external PostgreSQL admin DSN when needed."""

    reader, writer, handle = _open_interactive_stream()
    try:
        writer.write(
            "Enter the PostgreSQL admin connection string for your existing database.\n"
        )
        writer.write("It must point at the target database and support pgvector.\n")
        while True:
            writer.write("Admin DSN: ")
            writer.flush()
            answer = reader.readline()
            if answer == "":
                raise InitDependencyError(
                    "Shellbrain init was interrupted before the external PostgreSQL DSN was provided."
                )
            normalized = answer.strip()
            if normalized:
                return normalized
            writer.write("Please enter a non-empty PostgreSQL admin DSN.\n")
    finally:
        _close_interactive_stream(handle)


def _open_interactive_stream() -> tuple[TextIO, TextIO, TextIO | None]:
    """Return one interactive IO pair, preferring the real terminal for pipe installs."""

    if sys.stdin.isatty() and sys.stdout.isatty():
        return sys.stdin, sys.stdout, None
    writer = _resolve_interactive_writer()
    if sys.stdin.isatty():
        return sys.stdin, writer, None
    try:
        handle = Path("/dev/tty").open("r", encoding="utf-8")
    except OSError as exc:
        raise InitDependencyError(_NON_INTERACTIVE_MESSAGE) from exc
    return handle, writer, handle


def _resolve_interactive_writer() -> TextIO:
    """Return one visible terminal writer for prompts when available."""

    if sys.stderr.isatty():
        return sys.stderr
    if sys.stdout.isatty():
        return sys.stdout
    raise InitDependencyError(_NON_INTERACTIVE_MESSAGE)


def _close_interactive_stream(handle: TextIO | None) -> None:
    """Close one temporary terminal handle when needed."""

    if handle is None:
        return
    handle.close()
