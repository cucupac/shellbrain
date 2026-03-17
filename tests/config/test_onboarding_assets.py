"""Contracts that keep CLI help, docs, and the session-start skill aligned."""

from __future__ import annotations

from pathlib import Path

from shellbrain.periphery.cli import main as cli_main


def _read_text(path: Path) -> str:
    """Read one UTF-8 text file from the repository."""

    return path.read_text(encoding="utf-8")


def test_docs_and_skill_should_share_the_shellbrain_protocol() -> None:
    """The longer onboarding surfaces should teach the same Shellbrain mental model."""

    repo_root = Path(__file__).resolve().parents[2]
    texts = [
        _read_text(repo_root / "README.md"),
        _read_text(repo_root / "docs" / "external-quickstart.md"),
        _read_text(repo_root / "skills" / "shellbrain-session-start" / "SKILL.md"),
    ]

    required_phrases = [
        "one-time global install",
        "durable memories",
        "episodic evidence",
        "Never invent `evidence_refs`",
        "--repo-root",
        "session end",
        "utility_vote",
        "what should I know about this repo?",
    ]

    for phrase in required_phrases:
        assert all(phrase in text for text in texts)


def test_cli_help_should_share_the_short_protocol() -> None:
    """Top-level CLI help should match the condensed taught workflow."""

    help_text = cli_main._TOP_LEVEL_HELP

    required_phrases = [
        "case-based memory system",
        "Avoid generic prompts like",
        "evidence_refs",
        "utility_vote",
        "shellbrain admin migrate",
        "--repo-root",
        "At session end",
    ]

    for phrase in required_phrases:
        assert phrase in help_text

    assert "--no-sync" not in help_text


def test_shellbrain_skill_should_ship_codex_agent_metadata() -> None:
    """The reusable shellbrain skill should include Codex UI metadata."""

    repo_root = Path(__file__).resolve().parents[2]
    openai_yaml = _read_text(repo_root / "skills" / "shellbrain-session-start" / "agents" / "openai.yaml")

    assert 'display_name: "Shellbrain Session Start"' in openai_yaml
    assert 'default_prompt: "Use $shellbrain-session-start' in openai_yaml
