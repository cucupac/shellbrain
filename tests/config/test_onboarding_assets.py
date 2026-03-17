"""Contracts that keep CLI help, docs, and the session-start skill aligned."""

from __future__ import annotations

from pathlib import Path

from shellbrain.periphery.cli import main as cli_main


def _read_text(path: Path) -> str:
    """Read one UTF-8 text file from the repository."""

    return path.read_text(encoding="utf-8")


def test_onboarding_assets_should_share_the_explicit_evidence_workflow() -> None:
    """README quickstart skill and CLI help should all teach the same evidence path."""

    repo_root = Path(__file__).resolve().parents[2]
    texts = [
        _read_text(repo_root / "README.md"),
        _read_text(repo_root / "docs" / "external-quickstart.md"),
        _read_text(repo_root / "skills" / "shellbrain-session-start" / "SKILL.md"),
        cli_main._TOP_LEVEL_HELP,
    ]

    required_phrases = [
        "shellbrain admin migrate",
        "shellbrain events",
        "evidence_refs",
        "Never invent `evidence_refs`",
        "--repo-root",
        "--no-sync",
    ]

    for phrase in required_phrases:
        assert all(phrase in text for text in texts)


def test_shellbrain_skill_should_ship_codex_agent_metadata() -> None:
    """The reusable shellbrain skill should include Codex UI metadata."""

    repo_root = Path(__file__).resolve().parents[2]
    openai_yaml = _read_text(repo_root / "skills" / "shellbrain-session-start" / "agents" / "openai.yaml")

    assert 'display_name: "Shellbrain Session Start"' in openai_yaml
    assert 'default_prompt: "Use $shellbrain-session-start' in openai_yaml
