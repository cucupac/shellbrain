"""Local HTTP server for Shellbrain Wiki."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import parse_qs, unquote, urlparse

from app.core.errors import DomainValidationError
from app.core.entities.wiki_summaries import WikiSummaryTarget
from app.core.ports.system.clock import IClock
from app.core.policies.wiki_summary_freshness import needs_wiki_summary_refresh
from app.core.use_cases.wiki import (
    wiki_anchor_page,
    wiki_concept_facet,
    wiki_concept_page,
    wiki_evidence_page,
    wiki_home,
    wiki_index,
    wiki_memory_neighbors,
    wiki_memory_page,
    wiki_memory_sources,
    wiki_search,
)
from app.core.use_cases.wiki.request import (
    WikiAnchorRequest,
    WikiConceptFacetRequest,
    WikiConceptRequest,
    WikiEvidenceRequest,
    WikiIndexRequest,
    WikiMemoryRequest,
    WikiRepoRequest,
    WikiSearchRequest,
)
from app.infrastructure.reporting.wiki import render_html


@dataclass(frozen=True)
class WikiHttpResponse:
    """HTTP response produced by the wiki route adapter."""

    status: int
    body: str
    content_type: str = "text/html; charset=utf-8"


class WikiApplication:
    """Route local wiki requests into core read-only use cases."""

    def __init__(
        self,
        *,
        repo_id: str,
        include_global: bool,
        uow_factory,
        clock: IClock,
        summary_refresh_sink: Callable[[WikiSummaryTarget], None] | None = None,
    ) -> None:
        self._repo_id = repo_id
        self._include_global = include_global
        self._uow_factory = uow_factory
        self._clock = clock
        self._summary_refresh_sink = summary_refresh_sink

    def handle(self, raw_url: str) -> WikiHttpResponse:
        """Return an HTML response for one local wiki URL."""

        parsed = urlparse(raw_url)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        try:
            return self._route(path=path, query=query)
        except DomainValidationError as exc:
            return WikiHttpResponse(
                status=404,
                body=render_html.render_error_page(
                    title="Not found",
                    message="; ".join(error.message for error in exc.errors),
                ),
            )
        except ValueError as exc:
            return WikiHttpResponse(
                status=400,
                body=render_html.render_error_page(title="Bad request", message=str(exc)),
            )
        except Exception as exc:  # pragma: no cover - defensive local server envelope
            return WikiHttpResponse(
                status=500,
                body=render_html.render_error_page(title="Server error", message=str(exc)),
            )

    def _route(self, *, path: str, query: dict[str, list[str]]) -> WikiHttpResponse:
        if path == "/":
            with self._uow_factory() as uow:
                result = wiki_index(WikiIndexRequest(current_repo_id=self._repo_id), uow)
            return WikiHttpResponse(status=200, body=render_html.render_page(result))

        parts = _path_parts(path)
        if len(parts) >= 2 and parts[0] == "repo":
            return self._route_repo(repo_id=parts[1], parts=parts[2:], query=query)
        if len(parts) >= 3 and parts[0] == "fragment" and parts[1] == "repo":
            return self._route_repo(
                repo_id=parts[2],
                parts=("fragment", *parts[3:]),
                query=query,
            )
        return self._route_repo(repo_id=self._repo_id, parts=parts, query=query)

    def _route_repo(
        self,
        *,
        repo_id: str,
        parts: list[str] | tuple[str, ...],
        query: dict[str, list[str]],
    ) -> WikiHttpResponse:
        if not parts:
            with self._uow_factory() as uow:
                result = wiki_home(WikiRepoRequest(repo_id=repo_id, now=self._now()), uow)
            self._queue_summary_refresh(result)
            return WikiHttpResponse(status=200, body=render_html.render_page(result))

        if len(parts) == 1 and parts[0] == "search":
            search_query = _first(query, "q")
            with self._uow_factory() as uow:
                result = wiki_search(
                    WikiSearchRequest(
                        repo_id=repo_id,
                        now=self._now(),
                        query=search_query,
                        include_global=self._include_global,
                    ),
                    uow,
                )
            return WikiHttpResponse(status=200, body=render_html.render_page(result))

        if len(parts) == 2 and parts[0] == "concept":
            with self._uow_factory() as uow:
                result = wiki_concept_page(
                    WikiConceptRequest(
                        repo_id=repo_id, now=self._now(), concept_ref=parts[1]
                    ),
                    uow,
                )
            self._queue_summary_refresh(result)
            return WikiHttpResponse(status=200, body=render_html.render_page(result))

        if len(parts) == 2 and parts[0] == "memory":
            with self._uow_factory() as uow:
                result = wiki_memory_page(
                    WikiMemoryRequest(
                        repo_id=repo_id,
                        now=self._now(),
                        memory_id=parts[1],
                        include_global=self._include_global,
                    ),
                    uow,
                )
            return WikiHttpResponse(status=200, body=render_html.render_page(result))

        if len(parts) == 2 and parts[0] == "anchor":
            with self._uow_factory() as uow:
                result = wiki_anchor_page(
                    WikiAnchorRequest(
                        repo_id=repo_id, now=self._now(), anchor_id=parts[1]
                    ),
                    uow,
                )
            return WikiHttpResponse(status=200, body=render_html.render_page(result))

        if len(parts) == 2 and parts[0] == "evidence":
            with self._uow_factory() as uow:
                result = wiki_evidence_page(
                    WikiEvidenceRequest(
                        repo_id=repo_id, now=self._now(), evidence_id=parts[1]
                    ),
                    uow,
                )
            return WikiHttpResponse(status=200, body=render_html.render_page(result))

        if len(parts) == 4 and parts[0] == "fragment" and parts[1] == "concept":
            with self._uow_factory() as uow:
                result = wiki_concept_facet(
                    WikiConceptFacetRequest(
                        repo_id=repo_id,
                        now=self._now(),
                        concept_ref=parts[2],
                        facet=parts[3],
                    ),
                    uow,
                )
            return WikiHttpResponse(
                status=200,
                body=render_html.render_fragment(result, facet=parts[3]),
            )

        if len(parts) == 4 and parts[0] == "fragment" and parts[1] == "memory":
            request = WikiMemoryRequest(
                repo_id=repo_id,
                now=self._now(),
                memory_id=parts[2],
                include_global=self._include_global,
            )
            with self._uow_factory() as uow:
                if parts[3] == "neighbors":
                    result = wiki_memory_neighbors(request, uow)
                elif parts[3] == "evidence":
                    result = wiki_memory_sources(request, uow)
                else:
                    raise ValueError(f"Unsupported memory fragment: {parts[3]}")
            return WikiHttpResponse(
                status=200,
                body=render_html.render_fragment(result, facet=parts[3]),
            )

        return WikiHttpResponse(
            status=404,
            body=render_html.render_error_page(
                title="Not found",
                message=f"Wiki route not found for repo {repo_id}: {'/'.join(parts)}",
            ),
        )

    def _queue_summary_refresh(self, result) -> None:
        if self._summary_refresh_sink is None:
            return
        summary = getattr(result, "summary", None)
        if summary is None:
            return
        if needs_wiki_summary_refresh(summary.freshness):
            self._summary_refresh_sink(summary.target)

    def _now(self) -> datetime:
        return self._clock.now()


def run_wiki_server(
    *,
    app: WikiApplication,
    open_browser: Callable[[str], bool],
    output,
    background_worker=None,
) -> int:
    """Serve the local wiki in the foreground until interrupted."""

    handler = _handler_for(app)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    if background_worker is not None:
        background_worker.start()
    url = f"http://127.0.0.1:{server.server_port}/"
    output.write(f"Shellbrain Wiki: {url}\n")
    if open_browser(url):
        output.write("Browser: opened Shellbrain Wiki.\n")
    else:
        output.write(f"Browser: open {url}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        output.write("Shellbrain Wiki stopped.\n")
    finally:
        if background_worker is not None:
            background_worker.stop()
        server.server_close()
    return 0


def _handler_for(app: WikiApplication):
    class _WikiRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            response = app.handle(self.path)
            body = response.body.encode("utf-8")
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args) -> None:
            return None

    return _WikiRequestHandler


def _path_parts(path: str) -> list[str]:
    return [unquote(part) for part in path.strip("/").split("/") if part]


def _first(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key)
    if not values:
        return ""
    return values[0]
