"""Contracts for the local audit-attestation commit gate."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_FAILURE_MESSAGE = """Audit attestation required.

Agent path:
  Use Codex skills $clean-architecture and $clean-code on `git diff --cached`.
  Run relevant tests/checks.
  Then: scripts/audit-attestation attest --tests "<commands run>"

Human waiver:
  scripts/audit-attestation waive
  Agents may waive only when the human explicitly asks.

Changing staged files expires the attestation/waiver.
"""


def test_missing_attestation_blocks_commit_and_prints_exact_message(
    tmp_path: Path,
) -> None:
    repo = _new_repo_with_gate(tmp_path)
    _stage_file(repo, "work.txt", "blocked\n")

    result = _run(repo, "git", "commit", "-m", "blocked", check=False)

    assert result.returncode == 1
    assert result.stderr == EXPECTED_FAILURE_MESSAGE


def test_attestation_allows_same_staged_tree_to_commit(tmp_path: Path) -> None:
    repo = _new_repo_with_gate(tmp_path)
    _stage_file(repo, "work.txt", "attested\n")

    _run(
        repo,
        "scripts/audit-attestation",
        "attest",
        "--tests",
        "pytest -q tests/config/test_audit_attestation.py",
    )
    _run(repo, "scripts/audit-attestation", "check")
    commit = _run(repo, "git", "commit", "-m", "attested")

    assert "attested" in commit.stdout
    assert _receipt_count(repo, "attestations") == 1


def test_changing_staged_files_after_attesting_blocks_again(
    tmp_path: Path,
) -> None:
    repo = _new_repo_with_gate(tmp_path)
    _stage_file(repo, "work.txt", "attested\n")
    _run(repo, "scripts/audit-attestation", "attest", "--tests", "unit tests")

    _stage_file(repo, "work.txt", "changed\n")
    result = _run(repo, "scripts/audit-attestation", "check", check=False)

    assert result.returncode == 1
    assert result.stderr == EXPECTED_FAILURE_MESSAGE


def test_human_waiver_allows_same_staged_tree_to_commit(tmp_path: Path) -> None:
    repo = _new_repo_with_gate(tmp_path)
    _stage_file(repo, "work.txt", "waived\n")

    _run(repo, "scripts/audit-attestation", "waive")
    _run(repo, "scripts/audit-attestation", "check")
    commit = _run(repo, "git", "commit", "-m", "waived")

    assert "waived" in commit.stdout
    assert _receipt_count(repo, "waivers") == 1


def test_receipts_persist_across_later_processes(tmp_path: Path) -> None:
    repo = _new_repo_with_gate(tmp_path)
    _stage_file(repo, "work.txt", "session-stable\n")

    _run(repo, "scripts/audit-attestation", "attest", "--tests", "unit tests")
    first_check = _run(repo, "scripts/audit-attestation", "check")
    later_check = subprocess.run(
        ["scripts/audit-attestation", "check"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    assert first_check.returncode == 0
    assert later_check.returncode == 0


def test_changing_head_invalidates_old_receipt(tmp_path: Path) -> None:
    repo = _new_repo_with_gate(tmp_path)
    disabled_hooks = repo / ".git" / "disabled-hooks"
    disabled_hooks.mkdir()
    _stage_file(repo, "work.txt", "same-tree\n")
    _run(repo, "scripts/audit-attestation", "attest", "--tests", "unit tests")
    _run(repo, "scripts/audit-attestation", "check")

    _run(repo, "git", "reset", "--hard", "HEAD")
    _run(
        repo,
        "git",
        "-c",
        f"core.hooksPath={disabled_hooks}",
        "commit",
        "--allow-empty",
        "-m",
        "advance head",
    )
    _stage_file(repo, "work.txt", "same-tree\n")
    result = _run(repo, "scripts/audit-attestation", "check", check=False)

    assert result.returncode == 1
    assert result.stderr == EXPECTED_FAILURE_MESSAGE


def test_old_receipts_do_not_affect_unrelated_future_staged_trees(
    tmp_path: Path,
) -> None:
    repo = _new_repo_with_gate(tmp_path)
    _stage_file(repo, "work.txt", "first\n")
    _run(repo, "scripts/audit-attestation", "attest", "--tests", "unit tests")

    _stage_file(repo, "other.txt", "unrelated\n")
    result = _run(repo, "scripts/audit-attestation", "check", check=False)

    assert result.returncode == 1
    assert result.stderr == EXPECTED_FAILURE_MESSAGE


def test_install_sets_core_hooks_path_to_tracked_hook_directory(
    tmp_path: Path,
) -> None:
    repo = _new_repo_with_gate(tmp_path, install=False)

    _run(repo, "scripts/audit-attestation", "install")
    hooks_path = _run(repo, "git", "config", "--get", "core.hooksPath")

    assert hooks_path.stdout.strip() == ".githooks"


def _new_repo_with_gate(tmp_path: Path, *, install: bool = True) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "scripts").mkdir()
    (repo / ".githooks").mkdir()
    shutil.copy2(REPO_ROOT / "scripts" / "audit-attestation", repo / "scripts")
    shutil.copy2(REPO_ROOT / ".githooks" / "pre-commit", repo / ".githooks")
    (repo / "scripts" / "audit-attestation").chmod(0o755)
    (repo / ".githooks" / "pre-commit").chmod(0o755)

    _run(repo, "git", "init")
    _run(repo, "git", "config", "user.email", "test@example.com")
    _run(repo, "git", "config", "user.name", "Test User")
    _stage_file(repo, "README.md", "initial\n")
    _run(repo, "git", "commit", "-m", "initial")
    if install:
        _run(repo, "scripts/audit-attestation", "install")
    return repo


def _stage_file(repo: Path, relative_path: str, content: str) -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _run(repo, "git", "add", relative_path)


def _receipt_count(repo: Path, receipt_kind: str) -> int:
    receipt_dir = repo / ".git" / "solveos" / "audit-attestation" / receipt_kind
    return len(list(receipt_dir.glob("*.json")))


def _run(
    cwd: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"{' '.join(args)} failed with {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result
