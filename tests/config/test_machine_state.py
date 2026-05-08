"""Machine-config schema compatibility contracts."""

from __future__ import annotations

import tomllib
from pathlib import Path

from app.periphery.local_state.machine_config_store import (
    BackupState,
    DatabaseState,
    EmbeddingRuntimeState,
    MachineConfig,
    load_machine_config,
    save_machine_config,
)


def test_load_machine_config_should_upgrade_old_managed_payload_without_top_level_instance_id(tmp_path: Path) -> None:
    """legacy managed configs should still load by deriving instance_id from the managed section."""

    config_path = tmp_path / "machine.toml"
    config_path.write_text(
        """
config_version = 1
bootstrap_version = 1
runtime_mode = "managed_local"
bootstrap_state = "ready"
current_step = "verification"
last_error = ""

[database]
app_dsn = "postgresql+psycopg://app@127.0.0.1:55432/shellbrain"
admin_dsn = "postgresql+psycopg://admin@127.0.0.1:55432/shellbrain"

[managed]
instance_id = "inst-legacy"
container_name = "shellbrain-postgres"
image = "pgvector/pgvector:pg16"
host = "127.0.0.1"
port = 55432
db_name = "shellbrain"
data_dir = "/tmp/shellbrain-data"
admin_user = "shellbrain_admin"
admin_password = "admin-secret"
app_user = "shellbrain_app"
app_password = "app-secret"

[backups]
root = "/tmp/shellbrain-backups"
mirror_root = ""

[embeddings]
provider = "sentence_transformers"
model = "all-MiniLM-L6-v2"
model_revision = ""
backend_version = ""
cache_path = "/tmp/shellbrain-models"
readiness_state = "ready"
last_error = ""
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_machine_config(config_path)

    assert config is not None
    assert config.instance_id == "inst-legacy"
    assert config.machine_instance_id == "inst-legacy"
    assert config.managed is not None
    assert config.managed.container_name == "shellbrain-postgres"


def test_external_machine_config_should_round_trip_without_managed_metadata(tmp_path: Path) -> None:
    """external configs should save and load without fabricating managed metadata."""

    config_path = tmp_path / "machine.toml"
    config = MachineConfig(
        config_version=2,
        bootstrap_version=1,
        instance_id="ext-1",
        runtime_mode="external_postgres",
        bootstrap_state="ready",
        current_step="verification",
        last_error=None,
        database=DatabaseState(
            app_dsn="postgresql+psycopg://shellbrain_app:app_secret@db.example.com:5432/shellbrain",
            admin_dsn="postgresql+psycopg://admin:admin_secret@db.example.com:5432/shellbrain",
        ),
        managed=None,
        backups=BackupState(root="/tmp/shellbrain-backups", mirror_root=None),
        embeddings=EmbeddingRuntimeState(
            provider="sentence_transformers",
            model="all-MiniLM-L6-v2",
            model_revision=None,
            backend_version="1.0.0",
            cache_path="/tmp/shellbrain-models",
            readiness_state="ready",
            last_error=None,
        ),
    )

    save_machine_config(config, config_path)
    reloaded = load_machine_config(config_path)
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))

    assert reloaded == config
    assert "managed" not in payload
    assert payload["instance_id"] == "ext-1"
