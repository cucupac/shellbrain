"""Hosted package upgrade entrypoint for Shellbrain."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys


UPGRADE_URL = "shellbrain.ai/upgrade"
_MANUAL_PIP_UPGRADE = "python3 -m pip install --user --upgrade shellbrain && shellbrain init"
_MANUAL_PIPX_UPGRADE = "pipx upgrade shellbrain && shellbrain init"


def run_upgrade() -> int:
    """Delegate Shellbrain self-upgrade to the hosted upgrade script."""

    curl_bin = shutil.which("curl")
    bash_bin = shutil.which("bash")
    if curl_bin is None or bash_bin is None:
        missing = ", ".join(name for name, path in (("curl", curl_bin), ("bash", bash_bin)) if path is None)
        print(f"shellbrain upgrade requires {missing}.", file=sys.stderr)
        print("manual fallback:", file=sys.stderr)
        print(f"  {_MANUAL_PIP_UPGRADE}", file=sys.stderr)
        print(f"  {_MANUAL_PIPX_UPGRADE}", file=sys.stderr)
        return 1

    command = (
        "set -o pipefail; "
        f"{shlex.quote(curl_bin)} -L {shlex.quote(UPGRADE_URL)} | {shlex.quote(bash_bin)}"
    )
    completed = subprocess.run(
        [bash_bin, "-lc", command],
        check=False,
    )
    return completed.returncode
