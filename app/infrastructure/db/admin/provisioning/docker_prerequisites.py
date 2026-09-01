"""Docker prerequisite checks for managed local runtime operations."""

from __future__ import annotations

import shutil
import subprocess

from app.core.entities.admin_errors import InitDependencyError
from app.infrastructure.db.admin.provisioning import managed_local as managed_runtime


def ensure_docker_runtime_available() -> None:
    """Verify Docker CLI and daemon availability."""

    if shutil.which("docker") is None:
        raise InitDependencyError("Shellbrain init requires Docker to be installed.")
    completed = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        if not detail:
            detail = f"docker info exited with status {completed.returncode}"
        raise InitDependencyError(
            "Shellbrain requires a reachable Docker daemon for managed-local runtime operations. "
            f"docker info failed: {detail}"
        )


def recover_managed_machine_config_from_docker(*, embeddings: dict[str, object]):
    """Attempt to recover one unique managed instance from Docker metadata."""

    if shutil.which("docker") is None:
        return None
    try:
        return managed_runtime.recover_machine_config_from_docker(embeddings=embeddings)
    except FileNotFoundError:
        return None
