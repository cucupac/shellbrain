"""Claude hook installation contracts."""

import json
from pathlib import Path
import sys

from app.infrastructure.host_identity.claude_hook_install import install_claude_hook, inspect_claude_hook


def test_claude_hook_install_should_write_one_repo_local_settings_file_with_shellbrain_identity_exports(tmp_path: Path) -> None:
    """repo-local install should still write one settings.local.json file with Shellbrain identity exports."""

    repo_root = tmp_path / "claude-hook-repo"
    repo_root.mkdir()

    settings_path = install_claude_hook(repo_root=repo_root)

    assert settings_path == repo_root / ".claude" / "settings.local.json"
    content = settings_path.read_text(encoding="utf-8")
    assert "SessionStart" in content
    assert "CLAUDE_ENV_FILE" in content
    assert "SHELLBRAIN_HOST_APP=claude_code" in content
    assert str(Path(sys.executable).resolve()) in content


def test_claude_hook_install_should_merge_shellbrain_entry_without_overwriting_unrelated_hooks(tmp_path: Path) -> None:
    """hook install should merge the managed SessionStart entry non-destructively."""

    repo_root = tmp_path / "claude-hook-merge-repo"
    settings_path = repo_root / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": "echo custom"}]},
                        {
                            "matcher": "startup|resume|clear|compact",
                            "hooks": [{"type": "command", "command": "echo stale # shellbrain-managed:session-start"}],
                        },
                    ],
                    "Stop": [{"hooks": [{"type": "command", "command": "echo stop"}]}],
                },
                "other": {"preserve": True},
            }
        ),
        encoding="utf-8",
    )

    install_claude_hook(repo_root=repo_root)

    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    session_start = payload["hooks"]["SessionStart"]
    assert len(session_start) == 2
    assert session_start[0]["hooks"][0]["command"] == "echo custom"
    assert "shellbrain-managed:session-start" in session_start[1]["hooks"][0]["command"]
    assert payload["hooks"]["Stop"][0]["hooks"][0]["command"] == "echo stop"
    assert payload["other"] == {"preserve": True}


def test_claude_hook_install_should_create_global_settings_file_when_absent(tmp_path: Path) -> None:
    """global install should create ~/.claude/settings.json when it does not exist yet."""

    settings_path = tmp_path / ".claude" / "settings.json"

    installed_path = install_claude_hook(settings_path=settings_path)
    status = inspect_claude_hook(settings_path=settings_path)

    assert installed_path == settings_path.resolve()
    assert settings_path.exists()
    assert status.exists is True
    assert status.malformed is False
    assert status.managed is True
    assert status.command_executable == str(Path(sys.executable).resolve())
    assert status.executable_exists is True


def test_claude_hook_install_should_backup_malformed_global_settings_before_recreating(tmp_path: Path) -> None:
    """malformed global settings should be backed up before Shellbrain recreates a valid file."""

    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text("{not-json", encoding="utf-8")

    install_claude_hook(settings_path=settings_path)

    backups = sorted(settings_path.parent.glob("settings.json.shellbrain-backup-*"))
    status = inspect_claude_hook(settings_path=settings_path)

    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{not-json"
    assert status.managed is True
    assert status.malformed is False
    assert status.command_executable == str(Path(sys.executable).resolve())
    assert status.executable_exists is True


def test_claude_hook_inspection_should_report_missing_managed_interpreter(tmp_path: Path) -> None:
    """managed hook inspection should expose a broken interpreter path clearly."""

    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "matcher": "startup|resume|clear|compact",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "/tmp/missing-shellbrain-python -m app.infrastructure.host_identity.claude_runtime session-start # shellbrain-managed:session-start",
                                }
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    status = inspect_claude_hook(settings_path=settings_path)

    assert status.managed is True
    assert status.command_executable == "/tmp/missing-shellbrain-python"
    assert status.executable_exists is False
