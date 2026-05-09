"""Infrastructure effects used by runtime init and repair wiring."""

from __future__ import annotations

from app.infrastructure.db.admin.provisioning.docker_prerequisites import (
    ensure_docker_runtime_available,
    recover_managed_machine_config_from_docker,
)


def ensure_managed_runtime_available() -> None:
    """Verify managed-local runtime prerequisites before mutation."""

    ensure_docker_runtime_available()


def recover_managed_machine_config(*, embeddings: dict[str, object]):
    """Recover one unique managed runtime config for the current machine state."""

    return recover_managed_machine_config_from_docker(embeddings=embeddings)
