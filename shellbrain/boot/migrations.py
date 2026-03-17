"""Packaged Alembic bootstrap helpers for installed-shellbrain database migrations."""

from __future__ import annotations

from importlib.resources import as_file, files

from alembic import command
from alembic.config import Config

from shellbrain.boot.db import get_db_dsn


def upgrade_database(revision: str = "head") -> None:
    """Apply packaged Alembic migrations to the configured database."""

    config = Config()
    config.set_main_option("sqlalchemy.url", get_db_dsn())
    with as_file(files("shellbrain").joinpath("migrations")) as migrations_path:
        config.set_main_option("script_location", str(migrations_path))
        command.upgrade(config, revision)
