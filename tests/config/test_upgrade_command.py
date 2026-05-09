"""Behavioral coverage for the hosted Shellbrain upgrader wrapper."""

from __future__ import annotations

from types import SimpleNamespace

from app.infrastructure.system import package_upgrade as upgrade_module


def test_run_upgrade_should_fail_cleanly_when_required_tools_are_missing(
    monkeypatch, capsys
) -> None:
    """Missing curl/bash should produce one clear manual fallback and non-zero exit."""

    monkeypatch.setattr(upgrade_module.shutil, "which", lambda name: None)

    exit_code = upgrade_module.run_upgrade()

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "shellbrain upgrade requires curl, bash." in err
    assert (
        "python3 -m pip install --user --upgrade shellbrain && shellbrain init" in err
    )
    assert "pipx upgrade shellbrain && shellbrain init" in err


def test_run_upgrade_should_shell_out_to_the_hosted_upgrade_script(monkeypatch) -> None:
    """The Python wrapper should keep the hosted script as the single source of truth."""

    captured: dict[str, object] = {}

    def _which(name: str) -> str | None:
        return {
            "curl": "/usr/bin/curl",
            "bash": "/bin/bash",
        }.get(name)

    def _run(command, check=False):
        captured["command"] = command
        captured["check"] = check
        return SimpleNamespace(returncode=17)

    monkeypatch.setattr(upgrade_module.shutil, "which", _which)
    monkeypatch.setattr(upgrade_module.subprocess, "run", _run)

    exit_code = upgrade_module.run_upgrade()

    assert exit_code == 17
    assert captured["check"] is False
    command = captured["command"]
    assert command[0] == "/bin/bash"
    assert command[1] == "-lc"
    assert "set -o pipefail;" in command[2]
    assert "shellbrain.ai/upgrade" in command[2]
    assert "/usr/bin/curl" in command[2]
    assert "/bin/bash" in command[2]
