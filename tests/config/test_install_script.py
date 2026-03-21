"""Regression coverage for the public website installer script."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def test_install_script_should_ignore_incompatible_zsh_profiles_and_reach_init(tmp_path: Path) -> None:
    """The installer should not die silently when a zsh profile is invalid under bash."""

    repo_root = Path(__file__).resolve().parents[2]
    install_script = repo_root / "docs" / "install"

    home_dir = tmp_path / "home"
    home_dir.mkdir()
    (home_dir / ".zprofile").write_text("setopt PROMPT_SUBST\n", encoding="utf-8")

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    user_bin = home_dir / "Library" / "Python" / "3.13" / "bin"
    marker_path = tmp_path / "shellbrain-init-called"

    fake_python = fake_bin / "python3.13"
    fake_python.write_text(
        f"""#!{sys.executable}
from pathlib import Path
import sys

user_bin = Path({str(user_bin)!r})
marker_path = Path({str(marker_path)!r})

if len(sys.argv) >= 3 and sys.argv[1] == "-c":
    code = sys.argv[2]
    if code == "import sys; print(sys.version_info.minor)":
        print("13")
        raise SystemExit(0)
    if code == "import sys; print(f'{{sys.version_info.major}}.{{sys.version_info.minor}}')":
        print("3.13")
        raise SystemExit(0)
    if code == "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))":
        print(user_bin)
        raise SystemExit(0)
    raise SystemExit(f"unexpected python -c payload: {{code!r}}")

if len(sys.argv) >= 3 and sys.argv[1:3] == ["-m", "pip"]:
    user_bin.mkdir(parents=True, exist_ok=True)
    shellbrain = user_bin / "shellbrain"
    shellbrain.write_text(
        "#!/usr/bin/env bash\\n"
        "if [ \\"$1\\" = \\"init\\" ]; then\\n"
        f"  touch {str(marker_path)!r}\\n"
        "  echo STUB_INIT\\n"
        "  exit 0\\n"
        "fi\\n"
        "exit 1\\n",
        encoding="utf-8",
    )
    shellbrain.chmod(0o755)
    print("stub pip install")
    raise SystemExit(0)

raise SystemExit(f"unexpected python invocation: {{sys.argv!r}}")
""",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    completed = subprocess.run(
        ["bash", str(install_script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={
            **dict(PATH=f"{fake_bin}:{Path('/usr/bin')}:{Path('/bin')}"),
            **dict(HOME=str(home_dir), SHELL="/bin/zsh"),
        },
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "installing shellbrain..." in completed.stdout
    assert "using python3.13 (3.13)" in completed.stdout
    assert "initializing..." in completed.stdout
    assert "STUB_INIT" in completed.stdout
    assert "shellbrain. knowledge compounds." in completed.stdout
    assert marker_path.exists()


def test_install_script_should_prefer_the_fresh_user_bin_over_a_stale_path_binary(tmp_path: Path) -> None:
    """The installer should run the binary it just installed, not an older PATH entry."""

    repo_root = Path(__file__).resolve().parents[2]
    install_script = repo_root / "docs" / "install"

    home_dir = tmp_path / "home"
    home_dir.mkdir()

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    user_bin = home_dir / "Library" / "Python" / "3.13" / "bin"
    marker_path = tmp_path / "shellbrain-init-called"

    stale_shellbrain = fake_bin / "shellbrain"
    stale_shellbrain.write_text(
        "#!/usr/bin/env bash\n"
        "echo STALE_PATH_BINARY\n"
        "exit 17\n",
        encoding="utf-8",
    )
    stale_shellbrain.chmod(0o755)

    fake_python = fake_bin / "python3.13"
    fake_python.write_text(
        f"""#!{sys.executable}
from pathlib import Path
import sys

user_bin = Path({str(user_bin)!r})
marker_path = Path({str(marker_path)!r})

if len(sys.argv) >= 3 and sys.argv[1] == "-c":
    code = sys.argv[2]
    if code == "import sys; print(sys.version_info.minor)":
        print("13")
        raise SystemExit(0)
    if code == "import sys; print(f'{{sys.version_info.major}}.{{sys.version_info.minor}}')":
        print("3.13")
        raise SystemExit(0)
    if code == "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))":
        print(user_bin)
        raise SystemExit(0)
    raise SystemExit(f"unexpected python -c payload: {{code!r}}")

if len(sys.argv) >= 3 and sys.argv[1:3] == ["-m", "pip"]:
    user_bin.mkdir(parents=True, exist_ok=True)
    shellbrain = user_bin / "shellbrain"
    shellbrain.write_text(
        "#!/usr/bin/env bash\\n"
        "if [ \\"$1\\" = \\"init\\" ]; then\\n"
        f"  touch {str(marker_path)!r}\\n"
        "  echo STUB_INIT\\n"
        "  exit 0\\n"
        "fi\\n"
        "exit 1\\n",
        encoding="utf-8",
    )
    shellbrain.chmod(0o755)
    print("stub pip install")
    raise SystemExit(0)

raise SystemExit(f"unexpected python invocation: {{sys.argv!r}}")
""",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    completed = subprocess.run(
        ["bash", str(install_script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={
            **dict(PATH=f"{fake_bin}:{Path('/usr/bin')}:{Path('/bin')}"),
            **dict(HOME=str(home_dir), SHELL="/bin/zsh"),
        },
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "STALE_PATH_BINARY" not in completed.stdout
    assert "STUB_INIT" in completed.stdout
    assert marker_path.exists()
