"""This module defines the Alembic environment for online and offline PostgreSQL migrations."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from shellbrain.periphery.db.models.registry import target_metadata


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

memory_dsn = os.getenv("SHELLBRAIN_DB_DSN")
if memory_dsn:
    config.set_main_option("sqlalchemy.url", memory_dsn)


def run_migrations_offline() -> None:
    """This function runs migrations in offline mode using URL-only context."""

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """This function runs migrations in online mode using an engine connection."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
