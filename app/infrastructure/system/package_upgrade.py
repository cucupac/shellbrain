"""Hosted package upgrade entrypoint for Shellbrain."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys


UPGRADE_URL = "shellbrain.ai/upgrade"


def run_upgrade() -> int:
    """Delegate Shellbrain self-upgrade to the hosted upgrade script."""

    curl_bin = shutil.which("curl")
    bash_bin = shutil.which("bash")
    if curl_bin is None or bash_bin is None:
        missing = ", ".join(
            name
            for name, path in (("curl", curl_bin), ("bash", bash_bin))
            if path is None
        )
        print(f"shellbrain upgrade requires {missing}.", file=sys.stderr)
        print(
            "Install the missing tools, then retry shellbrain upgrade.", file=sys.stderr
        )
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
