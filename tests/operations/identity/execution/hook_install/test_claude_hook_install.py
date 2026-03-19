"""Claude hook installation contracts."""

import json
from pathlib import Path

from shellbrain.periphery.identity.claude_hook_install import install_claude_hook


def test_claude_hook_install_should_write_one_repo_local_settings_file_with_shellbrain_identity_exports(tmp_path: Path) -> None:
    """claude hook install should always write one repo-local settings file with Shellbrain identity exports."""

    repo_root = tmp_path / "claude-hook-repo"
    repo_root.mkdir()

    settings_path = install_claude_hook(repo_root=repo_root)

    assert settings_path == repo_root / ".claude" / "settings.local.json"
    content = settings_path.read_text(encoding="utf-8")
    assert "SessionStart" in content
    assert "CLAUDE_ENV_FILE" in content
    assert "SHELLBRAIN_HOST_APP=claude_code" in content


def test_claude_hook_install_should_merge_shellbrain_entry_without_overwriting_unrelated_hooks(tmp_path: Path) -> None:
    """claude hook install should merge the managed SessionStart entry non-destructively."""

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
