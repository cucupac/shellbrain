"""Infrastructure coverage for Shellbrain Wiki rendering and local routes."""

from __future__ import annotations

from datetime import datetime

from app.core.entities.wiki_summaries import (
    WikiSummaryFreshness,
    WikiSummaryGenerationStatus,
    WikiSummaryLinkTarget,
    WikiSummaryLinkTargetType,
    WikiSummaryTarget,
    WikiSummaryTargetType,
    WikiSummaryView,
)
from app.core.use_cases.wiki.result import (
    WikiClaimItem,
    WikiConceptGroup,
    WikiConceptListItem,
    WikiConceptPageResult,
    WikiHomeResult,
    WikiIndexResult,
    WikiRepositoryItem,
    WikiStatus,
)
from app.infrastructure.reporting.wiki import browser, render_html
from app.infrastructure.reporting.wiki.server import WikiApplication
from tests.operations.wiki.test_wiki_core import NOW, _FakeUow


def test_render_page_escapes_content_and_uses_wikipedia_landmarks() -> None:
    result = WikiConceptPageResult(
        id="concept-danger",
        repo_id="repo",
        slug="danger",
        name='Danger "Concept"',
        kind="process",
        status="active",
        definition="<script>alert(1)</script>",
        status_rollup={"active": 1},
        evidence_total=1,
        key_claims=(
            WikiClaimItem(
                id="claim-1",
                claim_type="definition",
                text="<b>unsafe</b>",
                status=WikiStatus(status="active", currentness="current"),
            ),
        ),
    )

    html = render_html.render_page(result)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "class=\"sidebar\"" in html
    assert "class=\"toc\"" in html
    assert "class=\"infobox\"" in html
    assert "font-family: Georgia" in html


def test_render_home_page_links_to_concepts() -> None:
    result = WikiHomeResult(
        repo_id="repo",
        groups=(
            WikiConceptGroup(
                kind="process",
                concepts=(
                    WikiConceptListItem(
                        id="concept-recall",
                        slug="recall",
                        name="Recall",
                        kind="process",
                        status="active",
                        scope_note=None,
                        definition="Recall returns a compact read-only brief.",
                        claim_count=1,
                        memory_count=1,
                        evidence_count=1,
                        popularity_score=3,
                    ),
                ),
            ),
        ),
    )

    html = render_html.render_page(result)

    assert "<!doctype html>" in html
    assert "/repo/repo/concept/recall" in html
    assert "Knowledge for repo" in html
    assert "Workflows and recurring moves" in html
    assert "Ranked by supporting-record volume." in html
    assert "Recall returns a compact read-only brief." in html


def test_render_page_escapes_cached_summary_and_shows_freshness() -> None:
    result = WikiHomeResult(
        repo_id="repo",
        groups=(),
        summary=WikiSummaryView(
            target=WikiSummaryTarget(
                repo_id="repo",
                target_type=WikiSummaryTargetType.REPO,
                target_id="repo",
            ),
            freshness=WikiSummaryFreshness.FRESH,
            body="Recall <b>generated</b> repo summary",
            generated_at=None,
            stale_reason=None,
            generation_status=WikiSummaryGenerationStatus.OK,
            link_targets=(
                WikiSummaryLinkTarget(
                    target_type=WikiSummaryLinkTargetType.CONCEPT,
                    target_id="concept-recall",
                    label="Recall",
                    slug="recall",
                ),
            ),
        ),
    )

    html = render_html.render_page(result)

    assert "<b>generated</b>" not in html
    assert "<a href=\"/repo/repo/concept/recall\">Recall</a> &lt;b&gt;generated&lt;/b&gt; repo summary" in html
    assert "Freshness: fresh" in html
    assert "Related: <a href=\"/repo/repo/concept/recall\">Recall</a>" in html


def test_render_index_page_lists_repositories_first() -> None:
    result = WikiIndexResult(
        current_repo_id="repo",
        repositories=(
            WikiRepositoryItem(
                repo_id="repo",
                repo_root="/repo",
                concept_count=1,
                memory_count=2,
                evidence_count=3,
                last_seen_at=None,
                is_current=True,
                popularity_score=6,
            ),
        ),
    )

    html = render_html.render_page(result)

    assert "<h2>Repositories</h2>" in html
    assert "/repo/repo" in html
    assert "current" in html
    assert "popularity 6" in html


def test_wiki_application_routes_full_pages_and_fragments() -> None:
    app = WikiApplication(
        repo_id="repo",
        include_global=True,
        uow_factory=_uow_factory,
        clock=_FakeClock(),
    )

    index = app.handle("/")
    home = app.handle("/repo/repo")
    fragment = app.handle("/fragment/repo/repo/concept/recall/claims")
    legacy_fragment = app.handle("/fragment/concept/recall/claims")
    missing = app.handle("/repo/repo/concept/missing")

    assert index.status == 200
    assert "Repositories" in index.body
    assert home.status == 200
    assert "Knowledge for repo" in home.body
    assert fragment.status == 200
    assert "<!doctype html>" not in fragment.body
    assert "Recall returns a compact read-only brief." in fragment.body
    assert legacy_fragment.status == 200
    assert missing.status == 404
    assert "Traceback" not in missing.body


def test_open_wiki_should_delegate_to_webbrowser(monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        "app.infrastructure.reporting.wiki.browser.webbrowser.open",
        lambda url: opened.append(url) or True,
    )

    assert browser.open_wiki("http://127.0.0.1:1234/")
    assert opened == ["http://127.0.0.1:1234/"]


class _ContextUow(_FakeUow):
    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None


def _uow_factory() -> _ContextUow:
    return _ContextUow()


class _FakeClock:
    def now(self) -> datetime:
        return NOW
