"""Docker prerequisite checks for managed local runtime operations."""

from __future__ import annotations

import shutil
import subprocess

from app.core.entities.admin_errors import InitDependencyError
from app.infrastructure.runtime import managed_runtime


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
        raise InitDependencyError("Shellbrain init requires the Docker daemon to be running and reachable.")


def recover_managed_machine_config_from_docker(*, embeddings: dict[str, object]):
    """Attempt to recover one unique managed instance from Docker metadata."""

    if shutil.which("docker") is None:
        return None
    try:
        return managed_runtime.recover_machine_config_from_docker(embeddings=embeddings)
    except FileNotFoundError:
        return None
