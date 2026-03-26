"""Host asset installation contracts."""

from __future__ import annotations

from pathlib import Path
import sys

from app.periphery.onboarding.host_assets import inspect_host_assets, install_host_assets


def test_install_host_assets_auto_should_install_the_default_codex_claude_and_cursor_set(monkeypatch, tmp_path: Path) -> None:
    """auto mode should install Codex skill, Claude skill, Cursor skill, and the Claude global hook by default."""

    home_root = tmp_path / "home"
    codex_home = home_root / ".codex"
    cursor_home = home_root / ".cursor"
    monkeypatch.setenv("HOME", str(home_root))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CURSOR_HOME", str(cursor_home))

    result = install_host_assets(host_mode="auto", force=False)
    inspection = inspect_host_assets()

    codex_skill_root = codex_home / "skills" / "shellbrain-session-start"
    codex_review_root = codex_home / "skills" / "shellbrain-usage-review"
    claude_skill_root = home_root / ".claude" / "skills" / "shellbrain-session-start"
    claude_review_root = home_root / ".claude" / "skills" / "shellbrain-usage-review"
    cursor_skill_root = cursor_home / "skills" / "shellbrain-session-start"
    cursor_review_root = cursor_home / "skills" / "shellbrain-usage-review"
    claude_settings_path = home_root / ".claude" / "settings.json"

    assert (codex_skill_root / "SKILL.md").exists()
    assert (codex_review_root / "SKILL.md").exists()
    assert (codex_skill_root / "agents" / "openai.yaml").exists()
    assert (claude_skill_root / "SKILL.md").exists()
    assert (claude_review_root / "SKILL.md").exists()
    assert (cursor_skill_root / "SKILL.md").exists()
    assert (cursor_review_root / "SKILL.md").exists()
    assert claude_settings_path.exists()
    assert inspection.codex_skill["managed"] is True
    assert inspection.claude_skill["managed"] is True
    assert inspection.cursor_skill["managed"] is True
    assert inspection.claude_global_hook["managed"] is True
    assert inspection.claude_global_hook["command_executable"] == str(Path(sys.executable).resolve())
    assert inspection.claude_global_hook["executable_exists"] is True
    assert any(line.startswith("Codex skill (shellbrain-session-start): installed at ") for line in result.lines)
    assert any(line.startswith("Codex skill (shellbrain-usage-review): installed at ") for line in result.lines)
    assert any(line.startswith("Claude skill (shellbrain-session-start): installed at ") for line in result.lines)
    assert any(line.startswith("Claude skill (shellbrain-usage-review): installed at ") for line in result.lines)
    assert any(line.startswith("Cursor skill (shellbrain-session-start): installed at ") for line in result.lines)
    assert any(line.startswith("Cursor skill (shellbrain-usage-review): installed at ") for line in result.lines)
    assert any(line.startswith("Claude global hook: installed at ") for line in result.lines)


def test_install_host_assets_should_preserve_legacy_claude_command(monkeypatch, tmp_path: Path) -> None:
    """Claude installs should leave the legacy Claude command untouched."""

    home_root = tmp_path / "home"
    legacy_command = home_root / ".claude" / "commands" / "shellbrain-session-start.md"
    legacy_command.parent.mkdir(parents=True)
    legacy_command.write_text("# legacy\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home_root))

    result = install_host_assets(host_mode="claude", force=False)

    skill_root = home_root / ".claude" / "skills" / "shellbrain-session-start"
    review_root = home_root / ".claude" / "skills" / "shellbrain-usage-review"
    assert (skill_root / "SKILL.md").exists()
    assert (review_root / "SKILL.md").exists()
    assert legacy_command.read_text(encoding="utf-8") == "# legacy\n"
    assert any(line == f"Claude legacy command: preserved at {legacy_command}" for line in result.lines)


def test_install_host_assets_should_not_overwrite_unmanaged_codex_skill_without_force(monkeypatch, tmp_path: Path) -> None:
    """explicit Codex installs should skip unmanaged conflicts unless force is requested."""

    home_root = tmp_path / "home"
    codex_home = home_root / ".codex"
    unmanaged_root = codex_home / "skills" / "shellbrain-session-start"
    unmanaged_root.mkdir(parents=True)
    sentinel = unmanaged_root / "SKILL.md"
    sentinel.write_text("custom skill\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home_root))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    result = install_host_assets(host_mode="codex", force=False)

    assert sentinel.read_text(encoding="utf-8") == "custom skill\n"
    assert result.lines[0] == (
        f"Codex skill (shellbrain-session-start): skipped (unmanaged install exists at {unmanaged_root}; rerun with --force to replace)"
    )
    assert any(line.startswith("Codex skill (shellbrain-usage-review): installed at ") for line in result.lines)


def test_install_host_assets_should_adopt_legacy_markerless_codex_shellbrain_skill(monkeypatch, tmp_path: Path) -> None:
    """Legacy Shellbrain Codex skill installs without a marker should update in place."""

    home_root = tmp_path / "home"
    codex_home = home_root / ".codex"
    skill_root = codex_home / "skills" / "shellbrain-session-start"
    source_root = (
        Path(__file__).resolve().parents[5]
        / "app"
        / "onboarding_assets"
        / "codex"
        / "shellbrain-session-start"
    )
    skill_root.mkdir(parents=True)
    for relative_path in (
        Path("SKILL.md"),
        Path("agents") / "openai.yaml",
        Path("references") / "request-shapes.md",
        Path("references") / "session-workflow.md",
    ):
        destination = skill_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        text = (source_root / relative_path).read_text(encoding="utf-8")
        destination.write_text(text.replace("~/.bash_profile", "~/.bashrc"), encoding="utf-8")
    monkeypatch.setenv("HOME", str(home_root))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    result = install_host_assets(host_mode="codex", force=False)

    assert any(line == f"Codex skill (shellbrain-session-start): updated at {skill_root}" for line in result.lines)
    assert (skill_root / ".shellbrain-managed.json").exists()
    assert "~/.bash_profile" in (skill_root / "SKILL.md").read_text(encoding="utf-8")


def test_install_host_assets_should_not_overwrite_unmanaged_cursor_skill_without_force(monkeypatch, tmp_path: Path) -> None:
    """explicit Cursor installs should skip unmanaged conflicts unless force is requested."""

    home_root = tmp_path / "home"
    cursor_home = home_root / ".cursor"
    unmanaged_root = cursor_home / "skills" / "shellbrain-session-start"
    unmanaged_root.mkdir(parents=True)
    sentinel = unmanaged_root / "SKILL.md"
    sentinel.write_text("custom cursor skill\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home_root))
    monkeypatch.setenv("CURSOR_HOME", str(cursor_home))

    result = install_host_assets(host_mode="cursor", force=False)

    assert sentinel.read_text(encoding="utf-8") == "custom cursor skill\n"
    assert result.lines[0] == (
        f"Cursor skill (shellbrain-session-start): skipped (unmanaged install exists at {unmanaged_root}; rerun with --force to replace)"
    )
    assert any(line.startswith("Cursor skill (shellbrain-usage-review): installed at ") for line in result.lines)


def test_install_host_assets_should_update_managed_codex_skill_idempotently(monkeypatch, tmp_path: Path) -> None:
    """explicit Codex installs should refresh an existing Shellbrain-managed install in place."""

    home_root = tmp_path / "home"
    codex_home = home_root / ".codex"
    monkeypatch.setenv("HOME", str(home_root))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    first = install_host_assets(host_mode="codex", force=False)
    skill_root = codex_home / "skills" / "shellbrain-session-start"
    review_root = codex_home / "skills" / "shellbrain-usage-review"
    (skill_root / "SKILL.md").write_text("stale\n", encoding="utf-8")

    second = install_host_assets(host_mode="codex", force=False)

    assert any(line.startswith("Codex skill (shellbrain-session-start): installed at ") for line in first.lines)
    assert any(line.startswith("Codex skill (shellbrain-usage-review): installed at ") for line in first.lines)
    assert any(line == f"Codex skill (shellbrain-session-start): updated at {skill_root}" for line in second.lines)
    assert any(line == f"Codex skill (shellbrain-usage-review): updated at {review_root}" for line in second.lines)
    assert "Use Shellbrain as a case-based reasoning system" in (skill_root / "SKILL.md").read_text(encoding="utf-8")
