"""Claude hook installation contracts."""

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
