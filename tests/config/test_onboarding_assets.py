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
    assert "The installer already runs `shellbrain init` for you." in readme
    assert "pipx install shellbrain" in readme
    assert "shellbrain read --json" in readme
    assert "utility_vote" not in readme
    assert "what should I know about this repo?" not in readme
    assert "auto-registers repos later on first use inside a repo" in readme


def test_agent_docs_should_share_the_shellbrain_protocol() -> None:
    """The longer agent-facing surfaces should teach the same Shellbrain mental model."""

    repo_root = Path(__file__).resolve().parents[2]
    texts = [
        _read_text(repo_root / "docs" / "external-quickstart.md"),
        _read_text(repo_root / "skills" / "shellbrain-session-start" / "SKILL.md"),
        _read_text(repo_root / "app" / "onboarding_assets" / "claude" / "skills" / "shellbrain-session-start" / "SKILL.md"),
    ]

    required_phrases = [
        "shellbrain init",
        "shellbrain admin doctor",
        "durable memories",
        "episodic evidence",
        "--repo-root",
        "utility_vote",
        "what should I know about this repo?",
    ]

    for phrase in required_phrases:
        assert all(phrase in text for text in texts)


def test_cli_help_should_share_the_short_protocol() -> None:
    """Top-level CLI help should still match the condensed taught workflow."""

    help_text = cli_main._TOP_LEVEL_HELP

    required_phrases = [
        "case-based memory system",
        "curl -L shellbrain.ai/install | bash",
        "Avoid generic prompts like",
        "evidence_refs",
        "utility_vote",
        "shellbrain admin migrate",
        "shellbrain init",
        "--repo-root",
        "At session end",
    ]

    for phrase in required_phrases:
        assert phrase in help_text

    assert "--no-sync" not in help_text


def test_repo_codex_skill_should_ship_codex_agent_metadata() -> None:
    """The repo-facing Codex skill should include Codex UI metadata."""

    repo_root = Path(__file__).resolve().parents[2]
    openai_yaml = _read_text(repo_root / "skills" / "shellbrain-session-start" / "agents" / "openai.yaml")

    assert 'display_name: "Shellbrain Session Start"' in openai_yaml
    assert 'default_prompt: "Use $shellbrain-session-start' in openai_yaml


def test_packaged_codex_asset_should_match_repo_codex_skill() -> None:
    """The packaged Codex asset should stay aligned with the repo-facing Codex skill."""

    repo_root = Path(__file__).resolve().parents[2]
    repo_skill_root = repo_root / "skills" / "shellbrain-session-start"
    packaged_skill_root = repo_root / "app" / "onboarding_assets" / "codex" / "shellbrain-session-start"

    relative_paths = [
        Path("SKILL.md"),
        Path("agents") / "openai.yaml",
        Path("assets") / "shellbrain-small.svg",
        Path("assets") / "shellbrain-large.svg",
        Path("references") / "request-shapes.md",
        Path("references") / "session-workflow.md",
    ]

    for relative_path in relative_paths:
        assert _read_text(repo_skill_root / relative_path) == _read_text(packaged_skill_root / relative_path)


def test_install_script_should_locate_binary_and_always_run_init() -> None:
    """The website installer should always run shellbrain init after installation."""

    repo_root = Path(__file__).resolve().parents[2]
    install_script = _read_text(repo_root / "docs" / "install")

    assert "sysconfig.get_path('scripts', 'posix_user')" in install_script
    assert "$SHELLBRAIN init" in install_script
    assert "git rev-parse --is-inside-work-tree" not in install_script
    assert "shellbrain was installed but is not on PATH." not in install_script
