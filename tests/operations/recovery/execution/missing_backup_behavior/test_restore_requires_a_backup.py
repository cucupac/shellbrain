"""Recovery contracts for missing backup scenarios."""

from __future__ import annotations

from pathlib import Path

import pytest

from shellbrain.periphery.admin.backup import restore_backup, verify_backup


def test_backup_verify_should_fail_when_no_backups_exist(tmp_path: Path) -> None:
    """backup verify should fail clearly when no backup manifests exist."""

    with pytest.raises(RuntimeError, match="No Shellbrain backups are available"):
        verify_backup(backup_root=tmp_path)


def test_restore_should_fail_when_no_backups_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """backup restore should fail clearly when no backup manifests exist."""

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/psql" if name == "psql" else None)

    with pytest.raises(RuntimeError, match="No Shellbrain backups are available"):
        restore_backup(
            admin_dsn="postgresql+psycopg://shellbrain_admin:shellbrain_admin@localhost:5432/shellbrain_live",
            backup_root=tmp_path,
            target_db="shellbrain_restore_001",
        )
