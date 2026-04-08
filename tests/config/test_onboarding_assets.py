"""Contracts that keep human onboarding, agent docs, and packaged assets aligned."""

from __future__ import annotations

from pathlib import Path

from app.periphery.cli import main as cli_main


def _read_text(path: Path) -> str:
    """Read one UTF-8 text file from the repository."""

    return path.read_text(encoding="utf-8")


def test_readme_should_teach_the_installer_first_happy_path() -> None:
    """README should center the website installer and not reteach the full agent protocol."""

    repo_root = Path(__file__).resolve().parents[2]
    readme = _read_text(repo_root / "README.md")

    assert "curl -L shellbrain.ai/install | bash" in readme
    assert "shellbrain upgrade" in readme
    assert "curl -L shellbrain.ai/upgrade | bash" in readme
    assert "runs `shellbrain init` for you" in readme
    assert "pipx upgrade shellbrain && shellbrain init" in readme
    assert "Use $shellbrain-session-start" in readme
    assert "Use Shellbrain Session Start" in readme
    assert "utility_vote" not in readme
    assert "what should I know about this repo?" not in readme
    assert "Repos register themselves on first use." in readme


def test_agent_docs_should_share_the_shellbrain_protocol() -> None:
    """The longer agent-facing surfaces should teach the same Shellbrain mental model."""

    repo_root = Path(__file__).resolve().parents[2]
    texts = [
        _read_text(repo_root / "docs" / "external-quickstart.md"),
        _read_text(repo_root / "app" / "onboarding_assets" / "codex" / "shellbrain-session-start" / "SKILL.md"),
        _read_text(repo_root / "app" / "onboarding_assets" / "claude" / "skills" / "shellbrain-session-start" / "SKILL.md"),
        _read_text(repo_root / "app" / "onboarding_assets" / "cursor" / "skills" / "shellbrain-session-start" / "SKILL.md"),
    ]

    required_phrases = [
        "shellbrain init",
        "shellbrain admin doctor",
        "durable memories",
        "episodic evidence",
        "--repo-root",
        "goal | surface | obstacle | hypothesis",
        "SB: read |",
        "utility_vote",
        "what should I know about this repo?",
        "sysconfig.get_path('scripts', 'posix_user')",
        "~/.bash_profile",
    ]

    for phrase in required_phrases:
        assert all(phrase in text for text in texts)


def test_cli_help_should_share_the_short_protocol() -> None:
    """Top-level CLI help should still match the condensed taught workflow."""

    help_text = cli_main._TOP_LEVEL_HELP

    required_phrases = [
        "case-based memory system",
        "curl -L shellbrain.ai/install | bash",
        "curl -L shellbrain.ai/upgrade | bash",
        "Avoid generic prompts like",
        "evidence_refs",
        "utility_vote",
        "shellbrain upgrade",
        "pipx upgrade shellbrain && shellbrain init",
        "shellbrain admin migrate",
        "shellbrain init",
        "--repo-root",
        "At session end",
    ]

    for phrase in required_phrases:
        assert phrase in help_text

    assert "--no-sync" not in help_text


def test_packaged_codex_skill_should_ship_codex_agent_metadata() -> None:
    """The packaged Codex skill should include Codex UI metadata."""

    repo_root = Path(__file__).resolve().parents[2]
    openai_yaml = _read_text(repo_root / "app" / "onboarding_assets" / "codex" / "shellbrain-session-start" / "agents" / "openai.yaml")

    assert 'display_name: "Shellbrain Session Start"' in openai_yaml
    assert 'icon_large: "./assets/shellbrain_logo.png"' in openai_yaml
    assert 'default_prompt: "Use $shellbrain-session-start' in openai_yaml


def test_packaged_codex_asset_should_include_required_files() -> None:
    """The packaged Codex asset should include the files needed by the host."""

    repo_root = Path(__file__).resolve().parents[2]
    packaged_skill_root = repo_root / "app" / "onboarding_assets" / "codex" / "shellbrain-session-start"

    relative_paths = [
        Path("SKILL.md"),
        Path("agents") / "openai.yaml",
        Path("assets") / "shellbrain-small.svg",
        Path("assets") / "shellbrain-large.svg",
        Path("assets") / "shellbrain_logo.png",
        Path("references") / "request-shapes.md",
        Path("references") / "session-workflow.md",
    ]

    for relative_path in relative_paths:
        assert (packaged_skill_root / relative_path).is_file()


def test_packaged_startup_guidance_assets_should_exist_for_codex_and_claude() -> None:
    """The packaged startup guidance blocks should ship for the managed startup-layer install."""

    repo_root = Path(__file__).resolve().parents[2]

    assert (repo_root / "app" / "onboarding_assets" / "codex" / "AGENTS.md").is_file()
    assert (repo_root / "app" / "onboarding_assets" / "claude" / "CLAUDE.md").is_file()


def test_packaged_codex_usage_review_asset_should_include_ui_metadata_and_icons() -> None:
    """The secondary packaged Codex skill should also ship icon metadata and assets."""

    repo_root = Path(__file__).resolve().parents[2]
    packaged_skill_root = repo_root / "app" / "onboarding_assets" / "codex" / "shellbrain-usage-review"
    openai_yaml = _read_text(packaged_skill_root / "agents" / "openai.yaml")

    assert 'display_name: "Shellbrain Usage Review"' in openai_yaml
    assert 'icon_small: "./assets/shellbrain-small.svg"' in openai_yaml
    assert 'icon_large: "./assets/shellbrain_logo.png"' in openai_yaml
    assert (packaged_skill_root / "assets" / "shellbrain-small.svg").is_file()
    assert (packaged_skill_root / "assets" / "shellbrain_logo.png").is_file()


def test_packaged_cursor_skill_should_include_the_required_skill_file() -> None:
    """The packaged Cursor skill should ship the SKILL.md file consumed by Cursor."""

    repo_root = Path(__file__).resolve().parents[2]
    packaged_skill_root = repo_root / "app" / "onboarding_assets" / "cursor" / "skills" / "shellbrain-session-start"

    assert (packaged_skill_root / "SKILL.md").is_file()


def test_install_script_should_locate_binary_delegate_to_init_and_configure_shell_snippets() -> None:
    """The website installer should wire PATH through managed snippets and let init choose storage mode."""

    repo_root = Path(__file__).resolve().parents[2]
    install_script = _read_text(repo_root / "docs" / "install")

    assert "sysconfig.get_path('scripts', 'posix_user')" in install_script
    assert "--upgrade" in install_script
    assert "$SHELLBRAIN init" in install_script
    assert "ensure_user_bin_on_shell_path" in install_script
    assert 'shellbrain/path.sh' in install_script
    assert 'shellbrain.fish' in install_script
    assert 'cli path: ensured via $PATH_SNIPPET' in install_script
    assert "shellbrain init will ask how it should store data." in install_script
    assert "existing PostgreSQL + pgvector database" in install_script
    assert "git rev-parse --is-inside-work-tree" not in install_script
    assert "shellbrain was installed but is not on PATH." not in install_script


def test_upgrade_script_should_locate_binary_delegate_to_init_and_configure_shell_snippets() -> None:
    """The website upgrader should wire PATH through managed snippets and let init choose storage mode."""

    repo_root = Path(__file__).resolve().parents[2]
    upgrade_script = _read_text(repo_root / "docs" / "upgrade")

    assert "sysconfig.get_path('scripts', 'posix_user')" in upgrade_script
    assert "--upgrade" in upgrade_script
    assert "$SHELLBRAIN init" in upgrade_script
    assert "ensure_user_bin_on_shell_path" in upgrade_script
    assert 'shellbrain/path.sh' in upgrade_script
    assert 'shellbrain.fish' in upgrade_script
    assert 'cli path: ensured via $PATH_SNIPPET' in upgrade_script
    assert "shellbrain init will ask how it should store data." in upgrade_script
    assert "existing PostgreSQL + pgvector database" in upgrade_script
    assert "shellbrain was upgraded but could not be found." in upgrade_script
