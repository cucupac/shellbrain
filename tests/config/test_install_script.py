"""Regression coverage for the public website installer and upgrader scripts."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


SHELLBRAIN_SECTION_BORDER = "# ============================================================================ #"
SHELLBRAIN_SECTION_HEADER = "# SHELLBRAIN"
SHELLBRAIN_SOURCE_LINE = (
    '[ -f "${XDG_CONFIG_HOME:-$HOME/.config}/shellbrain/path.sh" ]'
    ' && . "${XDG_CONFIG_HOME:-$HOME/.config}/shellbrain/path.sh"'
)


def _repo_root() -> Path:
    """Return the repository root for hosted script lookups."""

    return Path(__file__).resolve().parents[2]


def _write_fake_python(
    *,
    fake_bin: Path,
    user_bin: Path,
    marker_path: Path,
    pip_log_path: Path,
    init_stdout: str,
) -> None:
    """Write one fake Python executable that installs a stub Shellbrain CLI."""

    fake_python = fake_bin / "python3.13"
    shellbrain_stub = (
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "init" ]; then\n'
        f"  touch {str(marker_path)!r}\n"
        f"  printf '%s\\n' {init_stdout!r}\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n"
    )
    fake_python.write_text(
        f"""#!{sys.executable}
from pathlib import Path
import sys

user_bin = Path({str(user_bin)!r})
marker_path = Path({str(marker_path)!r})
pip_log_path = Path({str(pip_log_path)!r})

if len(sys.argv) >= 3 and sys.argv[1] == "-c":
    code = sys.argv[2]
    mapping = {{
        "import sys; print(sys.version_info.minor)": "13",
        "import sys; print(f'{{sys.version_info.major}}.{{sys.version_info.minor}}')": "3.13",
        "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))": str(user_bin),
    }}
    if code in mapping:
        print(mapping[code])
        raise SystemExit(0)
    raise SystemExit(f"unexpected python -c payload: {{code!r}}")

if len(sys.argv) >= 3 and sys.argv[1:3] == ["-m", "pip"]:
    pip_log_path.write_text(" ".join(sys.argv), encoding="utf-8")
    user_bin.mkdir(parents=True, exist_ok=True)
    shellbrain = user_bin / "shellbrain"
    shellbrain.write_text({shellbrain_stub!r}, encoding="utf-8")
    shellbrain.chmod(0o755)
    print("stub pip install")
    raise SystemExit(0)

raise SystemExit(f"unexpected python invocation: {{sys.argv!r}}")
""",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)


def _write_fake_docker(*, fake_bin: Path, daemon_running: bool) -> None:
    """Write one fake Docker executable for installer preflight coverage."""

    fake_docker = fake_bin / "docker"
    docker_info_result = "0" if daemon_running else "1"
    fake_docker.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"$1\" = \"info\" ]; then\n"
        f"  exit {docker_info_result}\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)


def _write_system_tool_shims(*, system_bin: Path) -> None:
    """Expose only the host commands the hosted scripts need during test runs."""

    system_bin.mkdir(exist_ok=True)
    for command in ("bash", "grep", "awk", "mv", "dirname", "mkdir", "touch", "cat"):
        target = shutil.which(command)
        if target is None:
            raise RuntimeError(f"expected host command {command!r} to be available for installer tests")
        shim = system_bin / command
        if not shim.exists():
            shim.symlink_to(target)


def _run_hosted_script(
    *,
    tmp_path: Path,
    script_name: str,
    shell_path: str,
    user_bin: Path,
    docker_mode: str,
    init_stdout: str = "STUB_INIT",
) -> tuple[subprocess.CompletedProcess[str], Path, Path, Path]:
    """Run one hosted install or upgrade script under a fake Python/Docker environment."""

    home_dir = tmp_path / "home"
    home_dir.mkdir(exist_ok=True)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(exist_ok=True)
    system_bin = tmp_path / "system-bin"
    _write_system_tool_shims(system_bin=system_bin)
    marker_path = tmp_path / "shellbrain-init-called"
    pip_log_path = tmp_path / "pip-args.txt"

    _write_fake_python(
        fake_bin=fake_bin,
        user_bin=user_bin,
        marker_path=marker_path,
        pip_log_path=pip_log_path,
        init_stdout=init_stdout,
    )
    if docker_mode != "missing":
        _write_fake_docker(fake_bin=fake_bin, daemon_running=docker_mode == "ok")

    completed = subprocess.run(
        ["bash", str(_repo_root() / "docs" / script_name)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={
            **dict(PATH=f"{fake_bin}:{system_bin}"),
            **dict(HOME=str(home_dir), SHELL=shell_path),
        },
        check=False,
    )
    return completed, home_dir, marker_path, pip_log_path


def test_install_script_should_wire_zsh_login_and_interactive_shells(tmp_path: Path) -> None:
    """The installer should wire zsh PATH setup through a managed snippet and both zsh startup files."""

    user_bin = tmp_path / "home" / "Library" / "Python" / "3.13" / "bin"
    completed, home_dir, marker_path, pip_log_path = _run_hosted_script(
        tmp_path=tmp_path,
        script_name="install",
        shell_path="/bin/zsh",
        user_bin=user_bin,
        docker_mode="ok",
    )

    path_snippet = home_dir / ".config" / "shellbrain" / "path.sh"
    zprofile = home_dir / ".zprofile"
    zshrc = home_dir / ".zshrc"

    assert completed.returncode == 0, completed.stderr
    assert marker_path.exists()
    assert "--upgrade" in pip_log_path.read_text(encoding="utf-8")
    assert "initializing..." in completed.stdout
    assert "STUB_INIT" in completed.stdout
    assert f"cli path: ensured via {path_snippet}" in completed.stdout
    assert str(zprofile) in completed.stdout
    assert str(zshrc) in completed.stdout
    assert f'export PATH="{user_bin}:$PATH" ;;' in path_snippet.read_text(encoding="utf-8")
    zprofile_text = zprofile.read_text(encoding="utf-8")
    zshrc_text = zshrc.read_text(encoding="utf-8")
    assert f"{SHELLBRAIN_SECTION_BORDER}\n{SHELLBRAIN_SECTION_HEADER}\n{SHELLBRAIN_SECTION_BORDER}" in zprofile_text
    assert SHELLBRAIN_SOURCE_LINE in zprofile_text
    assert f"{SHELLBRAIN_SECTION_BORDER}\n{SHELLBRAIN_SECTION_HEADER}\n{SHELLBRAIN_SECTION_BORDER}" in zshrc_text
    assert SHELLBRAIN_SOURCE_LINE in zshrc_text
    assert not (home_dir / ".bash_profile").exists()


def test_upgrade_script_should_wire_bash_login_and_interactive_shells(tmp_path: Path) -> None:
    """The upgrader should wire bash PATH setup through a managed snippet and both bash startup files."""

    user_bin = tmp_path / "home" / ".local" / "bin"
    completed, home_dir, marker_path, pip_log_path = _run_hosted_script(
        tmp_path=tmp_path,
        script_name="upgrade",
        shell_path="/bin/bash",
        user_bin=user_bin,
        docker_mode="ok",
    )

    path_snippet = home_dir / ".config" / "shellbrain" / "path.sh"
    bash_profile = home_dir / ".bash_profile"
    bashrc = home_dir / ".bashrc"

    assert completed.returncode == 0, completed.stderr
    assert marker_path.exists()
    assert "--upgrade" in pip_log_path.read_text(encoding="utf-8")
    assert "re-initializing..." in completed.stdout
    assert "STUB_INIT" in completed.stdout
    assert f"cli path: ensured via {path_snippet}" in completed.stdout
    assert str(bash_profile) in completed.stdout
    assert str(bashrc) in completed.stdout
    assert SHELLBRAIN_SOURCE_LINE in bash_profile.read_text(encoding="utf-8")
    assert SHELLBRAIN_SOURCE_LINE in bashrc.read_text(encoding="utf-8")
    assert not (home_dir / ".zprofile").exists()


def test_install_script_should_write_fish_path_config_without_touching_posix_profiles(tmp_path: Path) -> None:
    """Fish users should get fish PATH wiring without unnecessary POSIX profile edits."""

    user_bin = tmp_path / "home" / ".local" / "bin"
    completed, home_dir, marker_path, _ = _run_hosted_script(
        tmp_path=tmp_path,
        script_name="install",
        shell_path="/usr/local/bin/fish",
        user_bin=user_bin,
        docker_mode="ok",
    )

    path_snippet = home_dir / ".config" / "shellbrain" / "path.sh"
    fish_conf = home_dir / ".config" / "fish" / "conf.d" / "shellbrain.fish"

    assert completed.returncode == 0, completed.stderr
    assert marker_path.exists()
    assert path_snippet.exists()
    assert fish_conf.exists()
    assert f'set -gx PATH "{user_bin}" $PATH' in fish_conf.read_text(encoding="utf-8")
    assert not (home_dir / ".profile").exists()
    assert not (home_dir / ".zprofile").exists()
    assert not (home_dir / ".bash_profile").exists()


def test_install_script_should_rewrite_the_managed_path_snippet_when_user_bin_changes(tmp_path: Path) -> None:
    """Re-running the installer should update the managed snippet instead of leaving a stale Python path behind."""

    first_user_bin = tmp_path / "home" / "Library" / "Python" / "3.13" / "bin"
    first_completed, home_dir, marker_path, _ = _run_hosted_script(
        tmp_path=tmp_path,
        script_name="install",
        shell_path="/bin/zsh",
        user_bin=first_user_bin,
        docker_mode="ok",
    )
    assert first_completed.returncode == 0, first_completed.stderr
    assert marker_path.exists()

    second_user_bin = tmp_path / "home" / ".local" / "bin"
    second_completed, _, _, _ = _run_hosted_script(
        tmp_path=tmp_path,
        script_name="install",
        shell_path="/bin/zsh",
        user_bin=second_user_bin,
        docker_mode="ok",
    )

    path_snippet = home_dir / ".config" / "shellbrain" / "path.sh"
    zprofile = home_dir / ".zprofile"
    zshrc = home_dir / ".zshrc"
    snippet_text = path_snippet.read_text(encoding="utf-8")

    assert second_completed.returncode == 0, second_completed.stderr
    assert str(second_user_bin) in snippet_text
    assert str(first_user_bin) not in snippet_text
    assert zprofile.read_text(encoding="utf-8").count(SHELLBRAIN_SECTION_HEADER) == 1
    assert zshrc.read_text(encoding="utf-8").count(SHELLBRAIN_SECTION_HEADER) == 1


def test_install_script_should_migrate_legacy_inline_path_blocks_to_the_new_source_model(tmp_path: Path) -> None:
    """Legacy inline PATH blocks should be removed and replaced with managed snippet sourcing."""

    home_dir = tmp_path / "home"
    home_dir.mkdir()
    legacy_zprofile = home_dir / ".zprofile"
    legacy_zprofile.write_text(
        "\n".join(
            [
                "setopt PROMPT_SUBST",
                "# >>> shellbrain path >>>",
                'export PATH="/tmp/old-shellbrain:$PATH"',
                "# <<< shellbrain path <<<",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    user_bin = home_dir / ".local" / "bin"
    completed, _, marker_path, _ = _run_hosted_script(
        tmp_path=tmp_path,
        script_name="install",
        shell_path="/bin/zsh",
        user_bin=user_bin,
        docker_mode="ok",
    )

    migrated_text = legacy_zprofile.read_text(encoding="utf-8")

    assert completed.returncode == 0, completed.stderr
    assert marker_path.exists()
    assert "# >>> shellbrain path >>>" not in migrated_text
    assert f"{SHELLBRAIN_SECTION_BORDER}\n{SHELLBRAIN_SECTION_HEADER}\n{SHELLBRAIN_SECTION_BORDER}" in migrated_text
    assert SHELLBRAIN_SOURCE_LINE in migrated_text
    assert migrated_text.count(SHELLBRAIN_SECTION_HEADER) == 1


def test_install_script_should_fail_fast_when_docker_is_missing(tmp_path: Path) -> None:
    """The installer should stop before init when Docker is not installed."""

    user_bin = tmp_path / "home" / ".local" / "bin"
    completed, home_dir, marker_path, _ = _run_hosted_script(
        tmp_path=tmp_path,
        script_name="install",
        shell_path="/bin/zsh",
        user_bin=user_bin,
        docker_mode="missing",
    )

    assert completed.returncode == 1
    assert not marker_path.exists()
    assert "managed-local bootstrap incomplete." in completed.stdout
    assert "reason: Docker is not installed." in completed.stdout
    assert "shellbrain CLI is installed, but managed-local bootstrap was not run." in completed.stdout
    assert "fix Docker, then rerun: shellbrain init" in completed.stdout
    assert "docs: shellbrain.ai/external-quickstart" in completed.stdout
    assert (home_dir / ".config" / "shellbrain" / "path.sh").exists()


def test_install_script_should_fail_fast_when_the_docker_daemon_is_unreachable(tmp_path: Path) -> None:
    """The installer should stop before init when Docker exists but the daemon is unavailable."""

    user_bin = tmp_path / "home" / ".local" / "bin"
    completed, home_dir, marker_path, _ = _run_hosted_script(
        tmp_path=tmp_path,
        script_name="install",
        shell_path="/bin/zsh",
        user_bin=user_bin,
        docker_mode="daemon-down",
    )

    assert completed.returncode == 1
    assert not marker_path.exists()
    assert "managed-local bootstrap incomplete." in completed.stdout
    assert "reason: Docker is installed, but the daemon is not running or reachable." in completed.stdout
    assert "shellbrain CLI is installed, but managed-local bootstrap was not run." in completed.stdout
    assert "fix Docker, then rerun: shellbrain init" in completed.stdout
    assert "docs: shellbrain.ai/external-quickstart" in completed.stdout
    assert (home_dir / ".config" / "shellbrain" / "path.sh").exists()
