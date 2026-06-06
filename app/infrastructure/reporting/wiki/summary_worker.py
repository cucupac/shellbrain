"""Background refresh worker for generated Shellbrain Wiki summaries."""

from __future__ import annotations

from collections.abc import Callable
from queue import Empty, Queue
from threading import Event, Lock, Thread
from time import monotonic

from app.core.entities.inner_agents import WikiSummarySettings
from app.core.entities.wiki_summaries import WikiSummaryTarget
from app.core.ports.host_apps.inner_agents import IWikiSummaryAgentRunner
from app.core.ports.system.clock import IClock
from app.core.use_cases.wiki.summaries import (
    UowFactory,
    plan_wiki_summary_refresh_batch,
    refresh_wiki_summary,
)


class WikiSummaryRefreshWorker:
    """Bounded background queue for generated wiki summary refreshes."""

    def __init__(
        self,
        *,
        uow_factory: UowFactory,
        clock: IClock,
        settings: WikiSummarySettings,
        agent_runner: IWikiSummaryAgentRunner | None,
        error_sink: Callable[[str], None] | None = None,
    ) -> None:
        """Store dependencies for background summary refreshes."""

        self._uow_factory = uow_factory
        self._clock = clock
        self._settings = settings
        self._agent_runner = agent_runner
        self._error_sink = error_sink
        self._queue: Queue[WikiSummaryTarget] = Queue()
        self._queued: set[WikiSummaryTarget] = set()
        self._queued_lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        """Start the worker thread once."""

        if self._thread is not None:
            return
        self._thread = Thread(
            target=self._run,
            name="shellbrain-wiki-summary-refresh",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Request worker shutdown and wait briefly for it to exit."""

        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def enqueue(self, target: WikiSummaryTarget) -> None:
        """Queue one summary target for refresh if it is not already queued."""

        with self._queued_lock:
            if target in self._queued:
                return
            self._queued.add(target)
            self._queue.put(target)

    def _run(self) -> None:
        self._enqueue_planned(self._settings.startup_batch_limit)
        next_periodic = monotonic() + self._settings.periodic_seconds
        while not self._stop.is_set():
            now = monotonic()
            if now >= next_periodic:
                self._enqueue_planned(self._settings.periodic_batch_limit)
                next_periodic = now + self._settings.periodic_seconds
            try:
                target = self._queue.get(timeout=1)
            except Empty:
                continue
            try:
                refresh_wiki_summary(
                    target=target,
                    uow_factory=self._uow_factory,
                    clock=self._clock,
                    settings=self._settings,
                    agent_runner=self._agent_runner,
                )
            except Exception as exc:
                self._report_error(
                    "Wiki summary refresh failed for "
                    f"{target.target_type.value}:{target.target_id}: {exc}"
                )
            finally:
                with self._queued_lock:
                    self._queued.discard(target)
                self._queue.task_done()

    def _enqueue_planned(self, limit: int) -> None:
        if limit <= 0:
            return
        try:
            with self._uow_factory() as uow:
                snapshots = plan_wiki_summary_refresh_batch(
                    uow=uow,
                    now=self._clock.now(),
                    limit=limit,
                )
        except Exception as exc:
            self._report_error(f"Wiki summary refresh planning failed: {exc}")
            return
        for snapshot in snapshots:
            self.enqueue(snapshot.target)

    def _report_error(self, message: str) -> None:
        if self._error_sink is None:
            return
        self._error_sink(message)
