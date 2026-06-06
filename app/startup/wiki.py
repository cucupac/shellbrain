"""Composition wrapper for Shellbrain Wiki."""

from __future__ import annotations

import sys
from collections.abc import Callable

from app.infrastructure.db.runtime.uow import PostgresUnitOfWork
from app.infrastructure.reporting.wiki import browser, server
from app.infrastructure.reporting.wiki.summary_worker import WikiSummaryRefreshWorker
from app.infrastructure.system.clock import SystemClock
from app.startup import db as startup_db
from app.startup.internal_agents import (
    get_wiki_summary_inner_agent_runner,
    get_wiki_summary_settings,
)
from app.startup.read_policy import get_read_policy_settings


def run_wiki(
    *,
    repo_id: str,
    warn_or_fail_on_unsafe_app_role: Callable[[], None],
    output=None,
) -> int:
    """Wire concrete wiki dependencies and run the local server."""

    warn_or_fail_on_unsafe_app_role()
    if startup_db.get_optional_db_dsn() is None:
        raise RuntimeError(
            "Shellbrain database is not configured. Run `shellbrain init` first."
        )
    output_stream = output or sys.stdout
    include_global = get_read_policy_settings().include_global
    clock = SystemClock()
    summary_worker = WikiSummaryRefreshWorker(
        uow_factory=_wiki_uow_factory,
        clock=clock,
        settings=get_wiki_summary_settings(),
        agent_runner=get_wiki_summary_inner_agent_runner(),
        error_sink=lambda message: output_stream.write(message + "\n"),
    )
    wiki_app = server.WikiApplication(
        repo_id=repo_id,
        include_global=include_global,
        uow_factory=_wiki_uow_factory,
        clock=clock,
        summary_refresh_sink=summary_worker.enqueue,
    )
    return server.run_wiki_server(
        app=wiki_app,
        open_browser=browser.open_wiki,
        output=output_stream,
        background_worker=summary_worker,
    )


def _wiki_uow_factory() -> PostgresUnitOfWork:
    return PostgresUnitOfWork(startup_db.get_session_factory_instance())
