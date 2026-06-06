"""Render Wikipedia-style HTML for Shellbrain Wiki."""

from __future__ import annotations

from html import escape
import re
from urllib.parse import quote

from app.core.entities.wiki_summaries import (
    WikiSummaryLinkTarget,
    WikiSummaryLinkTargetType,
)
from app.core.use_cases.wiki.result import (
    WikiAnchorPageResult,
    WikiClaimItem,
    WikiConceptFacetResult,
    WikiConceptPageResult,
    WikiEvidenceItem,
    WikiEvidencePageResult,
    WikiGroundingItem,
    WikiHomeResult,
    WikiIndexResult,
    WikiMemoryLinkItem,
    WikiMemoryNeighbor,
    WikiMemoryPageResult,
    WikiRepositoryItem,
    WikiRelationItem,
    WikiSearchResult,
    WikiStatus,
)


_CATEGORY_COPY = {
    "capability": (
        "What this repo can do",
        "Capabilities Shellbrain has seen this repository provide or support.",
    ),
    "component": (
        "Code and system parts",
        "Named implementation pieces, data shapes, modules, or services.",
    ),
    "domain": (
        "Problem areas and external systems",
        "Business domains, vendors, protocols, or outside systems this repo touches.",
    ),
    "entity": (
        "Named things Shellbrain recognizes",
        "People, tools, objects, or other nouns that appear as stable references.",
    ),
    "process": (
        "Workflows and recurring moves",
        "Procedures, debugging paths, build flows, or repeated engineering steps.",
    ),
    "rule": (
        "Rules and constraints",
        "Constraints, invariants, conventions, and decisions Shellbrain should remember.",
    ),
}


def render_page(result) -> str:
    """Render one full wiki page."""

    if isinstance(result, WikiIndexResult):
        return _page("Shellbrain Wiki", _index_body(result))
    if isinstance(result, WikiHomeResult):
        return _page(
            f"Repository {result.repo_id}",
            _home_body(result),
            search_action=_repo_search_url(result.repo_id),
        )
    if isinstance(result, WikiConceptPageResult):
        return _page(
            result.name,
            _concept_body(result),
            search_action=_repo_search_url(result.repo_id),
        )
    if isinstance(result, WikiMemoryPageResult):
        return _page(
            f"Memory {result.id}",
            _memory_body(result),
            search_action=_repo_search_url(result.repo_id),
        )
    if isinstance(result, WikiAnchorPageResult):
        return _page(
            f"Anchor {result.id}",
            _anchor_body(result),
            search_action=_repo_search_url(result.repo_id),
        )
    if isinstance(result, WikiEvidencePageResult):
        return _page(
            f"Evidence {result.id}",
            _evidence_body(result),
            search_action=_repo_search_url(result.repo_id),
        )
    if isinstance(result, WikiSearchResult):
        return _page(
            "Search",
            _search_body(result),
            search_action=_repo_search_url(result.repo_id),
        )
    raise TypeError(f"unsupported wiki page result: {type(result).__name__}")


def render_fragment(result, *, facet: str | None = None) -> str:
    """Render one progressively loaded wiki fragment."""

    if isinstance(result, WikiConceptFacetResult):
        return _concept_facet(result)
    if isinstance(result, WikiMemoryPageResult):
        if facet == "neighbors":
            return _memory_neighbors(result.repo_id, result.neighbors)
        if facet == "evidence":
            return _evidence_list(result.repo_id, result.evidence)
        return _evidence_list(result.repo_id, result.evidence)
    raise TypeError(f"unsupported wiki fragment result: {type(result).__name__}")


def render_error_page(*, title: str, message: str) -> str:
    """Render an error page without tracebacks."""

    body = f"""
    <h1>{_text(title)}</h1>
    <p>{_text(message)}</p>
    <p><a href="/">Return to Shellbrain Wiki</a></p>
    """
    return _page(title, body)


def _page(title: str, body: str, *, search_action: str = "/search") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_text(title)} - Shellbrain Wiki</title>
  <style>{_css()}</style>
</head>
<body>
  <div class="shell">
    <nav class="sidebar" aria-label="Wiki navigation">
      <a class="brand" href="/">Shellbrain Wiki</a>
      <form class="search" action="{_attr(search_action)}" method="get">
        <input name="q" type="search" placeholder="Search Shellbrain" aria-label="Search Shellbrain">
      </form>
      <a href="/">Home</a>
    </nav>
    <main class="article">
      {body}
    </main>
  </div>
  <script>{_script()}</script>
</body>
</html>"""


def _index_body(result: WikiIndexResult) -> str:
    repositories = "".join(_repository_item(item) for item in result.repositories)
    content = repositories or "<li>No repositories are available.</li>"
    return f"""
    <h1>Shellbrain Wiki</h1>
    <p class="lead">Choose a repository first. Repositories are ranked by supporting-record volume.</p>
    <aside class="infobox">
      <div><b>Current repo</b></div>
      <div>{_text(result.current_repo_id)}</div>
      <div><b>Scope</b></div>
      <div>All known repositories</div>
      <div><b>Ranking</b></div>
      <div>concepts + memories + evidence</div>
    </aside>
    <div class="toc">
      <b>Contents</b>
      <ol><li>Repositories</li></ol>
    </div>
    <section>
      <h2>Repositories</h2>
      <ul>{content}</ul>
    </section>
    """


def _repository_item(item: WikiRepositoryItem) -> str:
    marker = " <span class=\"status\">current</span>" if item.is_current else ""
    counts = (
        f"{item.concept_count} concepts; "
        f"{item.memory_count} memories; "
        f"{item.evidence_count} evidence"
    )
    root = f"<br><span class=\"meta\">{_text(item.repo_root)}</span>" if item.repo_root else ""
    return (
        f"<li><a href=\"{_repo_url(item.repo_id)}\">{_text(item.repo_id)}</a>{marker}"
        f" <span class=\"meta\">popularity {item.popularity_score}; {_text(counts)}</span>{root}</li>"
    )


def _home_body(result: WikiHomeResult) -> str:
    groups = []
    for group in result.groups:
        label, description = _category_copy(group.kind)
        rows = "".join(_concept_index_row(result.repo_id, item) for item in group.concepts)
        groups.append(
            f"""
            <section>
              <h2>{_text(label)}</h2>
              <p class="section-lede">{_text(description)} Ranked by supporting-record volume.</p>
              <table class="concept-index">
                <thead>
                  <tr><th>Concept</th><th>What Shellbrain currently thinks</th><th>Supporting records</th></tr>
                </thead>
                <tbody>{rows}</tbody>
              </table>
            </section>
            """
        )
    content = "".join(groups) or "<p>No active concepts are available.</p>"
    return f"""
    <h1>Knowledge for {_text(result.repo_id)}</h1>
    <p class="lead">These are named ideas Shellbrain has learned for this repository. Open one to see its claims, linked memories, source anchors, and evidence.</p>
    <aside class="infobox">
      <div><b>Repo</b></div>
      <div>{_text(result.repo_id)}</div>
      <div><b>Scope</b></div>
      <div>Single repository</div>
    </aside>
    <div class="toc">
      <b>Contents</b>
      <ol><li>Generated summary</li>{''.join(f'<li>{_text(_category_copy(group.kind)[0])}</li>' for group in result.groups)}</ol>
    </div>
    {_summary_section(result.summary, repo_id=result.repo_id)}
    {content}
    """


def _concept_index_row(repo_id: str, item) -> str:
    summary = item.definition or "No summary yet. Open this concept to inspect its claims and linked memories."
    links = (
        f"{item.claim_count} claims; "
        f"{item.memory_count} memories; "
        f"{item.evidence_count} evidence"
    )
    return f"""
    <tr>
      <td><a href="{_repo_concept_url(repo_id, item.slug)}">{_text(item.name)}</a></td>
      <td>{_text(summary)}</td>
      <td><span class="meta">{_text(links)}</span></td>
    </tr>
    """


def _category_copy(kind: str) -> tuple[str, str]:
    return _CATEGORY_COPY.get(
        kind,
        (
            kind.replace("_", " ").title(),
            "Other named ideas Shellbrain has extracted for this repository.",
        ),
    )


def _concept_body(result: WikiConceptPageResult) -> str:
    definition = result.definition or "No active definition claim yet."
    return f"""
    <h1>{_text(result.name)}</h1>
    <aside class="infobox">
      <div><b>Kind</b></div><div>{_text(result.kind)}</div>
      <div><b>Status</b></div><div>{_text(result.status)}</div>
      <div><b>Evidence</b></div><div>{result.evidence_total}</div>
    </aside>
    <p class="lead">{_text(definition)}</p>
    <div class="toc">
      <b>Contents</b>
      <ol>
        <li>Generated summary</li>
        <li>Key claims</li>
        <li>Claims</li>
        <li>Relations</li>
        <li>Linked memories</li>
        <li>Groundings</li>
        <li>Evidence</li>
      </ol>
    </div>
    {_summary_section(result.summary, repo_id=result.repo_id)}
    <h2>Key claims</h2>
    {_claim_list(result.key_claims)}
    {_lazy_section('Claims', _repo_concept_fragment_url(result.repo_id, result.slug, 'claims'))}
    {_lazy_section('Relations', _repo_concept_fragment_url(result.repo_id, result.slug, 'relations'))}
    {_lazy_section('Linked memories', _repo_concept_fragment_url(result.repo_id, result.slug, 'memory-links'))}
    {_lazy_section('Groundings', _repo_concept_fragment_url(result.repo_id, result.slug, 'groundings'))}
    {_lazy_section('Evidence', _repo_concept_fragment_url(result.repo_id, result.slug, 'evidence'))}
    """


def _summary_section(summary, *, repo_id: str) -> str:
    if summary is None:
        return ""
    body = summary.body or "No generated summary yet."
    related = _summary_related_links(summary.link_targets, repo_id=repo_id)
    related_html = (
        f"<p class=\"meta\">Related: {related}</p>" if related else ""
    )
    generated = (
        summary.generated_at.isoformat()
        if summary.generated_at is not None
        else "not generated"
    )
    reason = f" · {_text(summary.stale_reason)}" if summary.stale_reason else ""
    return f"""
    <section class="generated-summary">
      <h2>Generated summary</h2>
      <p>{_linkified_summary_text(body, summary.link_targets, repo_id=repo_id)}</p>
      {related_html}
      <p class="meta">Freshness: {_text(summary.freshness.value)} · Generated: {_text(generated)}{reason}</p>
    </section>
    """


def _memory_body(result: WikiMemoryPageResult) -> str:
    concepts = "".join(
        f"<li><a href=\"{_repo_concept_url(result.repo_id, link.concept.slug)}\">{_text(link.concept.name)}</a>"
        f" <span class=\"meta\">{_text(link.role)}</span> {_status_badge(link.status)}</li>"
        for link in result.concept_links
    )
    return f"""
    <h1>Memory { _text(result.id) }</h1>
    <aside class="infobox">
      <div><b>Kind</b></div><div>{_text(result.kind)}</div>
      <div><b>Status</b></div><div>{_text(result.status.status)}</div>
      <div><b>Currentness</b></div><div>{_text(result.status.currentness or '')}</div>
    </aside>
    <p class="memory-text">{_text(result.text)}</p>
    <h2>Linked concepts</h2>
    <ul>{concepts or '<li>No linked concepts.</li>'}</ul>
    {_lazy_section('Neighbors', _repo_memory_fragment_url(result.repo_id, result.id, 'neighbors'))}
    {_lazy_section('Evidence', _repo_memory_fragment_url(result.repo_id, result.id, 'evidence'))}
    """


def _anchor_body(result: WikiAnchorPageResult) -> str:
    links = "".join(
        f"<li><a href=\"{_repo_concept_url(result.repo_id, link.concept.slug)}\">{_text(link.concept.name)}</a>"
        f" <span class=\"meta\">{_text(link.role)}</span> {_status_badge(link.status)}</li>"
        for link in result.concept_links
    )
    return f"""
    <h1>Anchor { _text(result.id) }</h1>
    <aside class="infobox">
      <div><b>Kind</b></div><div>{_text(result.kind)}</div>
      <div><b>Status</b></div><div>{_text(result.status)}</div>
    </aside>
    <p>{_text(result.locator)}</p>
    <h2>Grounded concepts</h2>
    <ul>{links or '<li>No grounded concepts.</li>'}</ul>
    """


def _evidence_body(result: WikiEvidencePageResult) -> str:
    targets = "".join(
        f"<li>{_target_link(result.repo_id, item.target_type, item.target_id)}"
        f" <span class=\"meta\">{_text(item.role)}</span></li>"
        for item in result.linked_targets
    )
    return f"""
    <h1>Evidence { _text(result.id) }</h1>
    <aside class="infobox">
      <div><b>Kind</b></div><div>{_text(result.source_kind)}</div>
      <div><b>Created</b></div><div>{_text(result.created_at or '')}</div>
    </aside>
    <p>{_text(result.source_ref)}</p>
    <h2>Linked targets</h2>
    <ul>{targets or '<li>No linked targets.</li>'}</ul>
    """


def _search_body(result: WikiSearchResult) -> str:
    hits = "".join(
        f"<li><a href=\"{_attr(hit.url)}\">{_text(hit.title)}</a>"
        f" <span class=\"meta\">{_text(hit.subtitle)}</span></li>"
        for hit in result.hits
    )
    if not result.query:
        hits = "<li>Enter a search term.</li>"
    elif not hits:
        hits = "<li>No matching wiki pages.</li>"
    return f"""
    <h1>Search</h1>
    <form class="search-page" action="{_repo_search_url(result.repo_id)}" method="get">
      <input name="q" type="search" value="{_attr(result.query)}" aria-label="Search Shellbrain">
      <button type="submit">Search</button>
    </form>
    <ul>{hits}</ul>
    """


def _concept_facet(result: WikiConceptFacetResult) -> str:
    if result.facet == "claims":
        return _claim_list(result.claims)
    if result.facet == "relations":
        return _relation_list(result.repo_id, result.relations)
    if result.facet == "memory-links":
        return _memory_link_list(result.repo_id, result.memory_links)
    if result.facet == "groundings":
        return _grounding_list(result.repo_id, result.groundings)
    return _evidence_list(result.repo_id, result.evidence)


def _claim_list(claims) -> str:
    items = "".join(
        f"<li><b>{_text(claim.claim_type)}</b>: {_text(claim.text)} {_status_badge(claim.status)}</li>"
        for claim in claims
    )
    return f"<ul>{items or '<li>No claims.</li>'}</ul>"


def _relation_list(repo_id: str, relations: tuple[WikiRelationItem, ...]) -> str:
    items = "".join(
        f"<li><a href=\"{_repo_concept_url(repo_id, item.subject.slug)}\">{_text(item.subject.name)}</a>"
        f" <b>{_text(item.predicate)}</b> "
        f"<a href=\"{_repo_concept_url(repo_id, item.object.slug)}\">{_text(item.object.name)}</a>"
        f" {_status_badge(item.status)}</li>"
        for item in relations
    )
    return f"<ul>{items or '<li>No relations.</li>'}</ul>"


def _memory_link_list(repo_id: str, memory_links: tuple[WikiMemoryLinkItem, ...]) -> str:
    items = "".join(
        f"<li><a href=\"{_repo_memory_url(repo_id, item.memory_id)}\">{_text(item.memory_kind)}</a>"
        f" <span class=\"meta\">{_text(item.role)}</span>: {_text(item.memory_text)}"
        f" {_status_badge(item.status)}</li>"
        for item in memory_links
    )
    return f"<ul>{items or '<li>No linked memories.</li>'}</ul>"


def _grounding_list(repo_id: str, groundings: tuple[WikiGroundingItem, ...]) -> str:
    items = "".join(
        f"<li><a href=\"{_repo_anchor_url(repo_id, item.anchor_id)}\">{_text(item.anchor_kind)}</a>"
        f" <span class=\"meta\">{_text(item.role)}</span>: {_text(item.locator)}"
        f" {_status_badge(item.status)}</li>"
        for item in groundings
    )
    return f"<ul>{items or '<li>No groundings.</li>'}</ul>"


def _memory_neighbors(repo_id: str, neighbors: tuple[WikiMemoryNeighbor, ...]) -> str:
    items = "".join(
        f"<li><a href=\"{_repo_memory_url(repo_id, item.memory_id)}\">{_text(item.kind)}</a>"
        f" <span class=\"meta\">{_text(item.relation_type)}</span>: {_text(item.text)}</li>"
        for item in neighbors
    )
    return f"<ul>{items or '<li>No neighbors.</li>'}</ul>"


def _evidence_list(repo_id: str, evidence_items: tuple[WikiEvidenceItem, ...]) -> str:
    items = "".join(
        f"<li><a href=\"{_repo_evidence_url(repo_id, item.evidence_id)}\">{_text(item.source_kind)}</a>"
        f" <span class=\"meta\">{_text(item.role)}</span>: {_text(item.source_ref)}</li>"
        for item in evidence_items
    )
    return f"<ul>{items or '<li>No evidence.</li>'}</ul>"


def _target_link(repo_id: str, target_type: str, target_id: str) -> str:
    if target_type == "memory":
        return f"<a href=\"{_repo_memory_url(repo_id, target_id)}\">memory:{_text(target_id)}</a>"
    return f"{_text(target_type)}:{_text(target_id)}"


def _lazy_section(title: str, fragment_url: str) -> str:
    return f"""
    <section class="lazy-section">
      <h2>{_text(title)}</h2>
      <button type="button" data-fragment="{_attr(fragment_url)}">Load { _text(title.lower()) }</button>
      <div class="fragment"></div>
    </section>
    """


def _status_badge(status: WikiStatus) -> str:
    detail = status.currentness or status.status
    evidence = f" · evidence {status.evidence_count}" if status.evidence_count else ""
    return f"<span class=\"status\">{_text(detail)}{_text(evidence)}</span>"


def _text(value: object) -> str:
    return escape(str(value), quote=False)


def _attr(value: object) -> str:
    return escape(str(value), quote=True)


def _linkified_summary_text(
    body: str, link_targets: tuple[WikiSummaryLinkTarget, ...], *, repo_id: str
) -> str:
    labels = _summary_link_labels(link_targets)
    if not labels:
        return _text(body)
    pattern = re.compile(
        r"(?<![A-Za-z0-9_/-])("
        + "|".join(re.escape(label) for label, _target in labels)
        + r")(?![A-Za-z0-9_/-])",
        re.IGNORECASE,
    )
    target_by_label = {label.casefold(): target for label, target in labels}
    rendered: list[str] = []
    cursor = 0
    for match in pattern.finditer(body):
        rendered.append(_text(body[cursor:match.start()]))
        label = match.group(0)
        target = target_by_label[label.casefold()]
        rendered.append(
            f"<a href=\"{_attr(_summary_target_url(repo_id, target))}\">{_text(label)}</a>"
        )
        cursor = match.end()
    rendered.append(_text(body[cursor:]))
    return "".join(rendered)


def _summary_related_links(
    link_targets: tuple[WikiSummaryLinkTarget, ...], *, repo_id: str
) -> str:
    links = []
    seen_urls: set[str] = set()
    for target in link_targets:
        if target.label == (target.slug or ""):
            continue
        url = _summary_target_url(repo_id, target)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        links.append(f"<a href=\"{_attr(url)}\">{_text(target.label)}</a>")
        if len(links) >= 8:
            break
    return "; ".join(links)


def _summary_link_labels(
    link_targets: tuple[WikiSummaryLinkTarget, ...]
) -> list[tuple[str, WikiSummaryLinkTarget]]:
    labels: list[tuple[str, WikiSummaryLinkTarget]] = []
    seen: set[str] = set()
    for target in link_targets:
        label = target.label.strip()
        if len(label) < 4:
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        labels.append((label, target))
    labels.sort(key=lambda item: len(item[0]), reverse=True)
    return labels


def _summary_target_url(repo_id: str, target: WikiSummaryLinkTarget) -> str:
    if target.target_type == WikiSummaryLinkTargetType.CONCEPT and target.slug:
        return _repo_concept_url(repo_id, target.slug)
    if target.target_type == WikiSummaryLinkTargetType.MEMORY:
        return _repo_memory_url(repo_id, target.target_id)
    if target.target_type == WikiSummaryLinkTargetType.ANCHOR:
        return _repo_anchor_url(repo_id, target.target_id)
    if target.target_type == WikiSummaryLinkTargetType.EVIDENCE:
        return _repo_evidence_url(repo_id, target.target_id)
    return _repo_url(repo_id)


def _segment(value: str) -> str:
    return quote(value, safe="")


def _repo_url(repo_id: str) -> str:
    return f"/repo/{_segment(repo_id)}"


def _repo_search_url(repo_id: str) -> str:
    return f"{_repo_url(repo_id)}/search"


def _repo_concept_url(repo_id: str, concept_slug: str) -> str:
    return f"{_repo_url(repo_id)}/concept/{_segment(concept_slug)}"


def _repo_memory_url(repo_id: str, memory_id: str) -> str:
    return f"{_repo_url(repo_id)}/memory/{_segment(memory_id)}"


def _repo_anchor_url(repo_id: str, anchor_id: str) -> str:
    return f"{_repo_url(repo_id)}/anchor/{_segment(anchor_id)}"


def _repo_evidence_url(repo_id: str, evidence_id: str) -> str:
    return f"{_repo_url(repo_id)}/evidence/{_segment(evidence_id)}"


def _repo_concept_fragment_url(repo_id: str, concept_slug: str, facet: str) -> str:
    return (
        f"/fragment/repo/{_segment(repo_id)}/concept/"
        f"{_segment(concept_slug)}/{_segment(facet)}"
    )


def _repo_memory_fragment_url(repo_id: str, memory_id: str, facet: str) -> str:
    return (
        f"/fragment/repo/{_segment(repo_id)}/memory/"
        f"{_segment(memory_id)}/{_segment(facet)}"
    )


def _css() -> str:
    return """
body { margin: 0; background: #fff; color: #202122; font-family: sans-serif; font-size: 15px; line-height: 1.55; }
a { color: #0645ad; text-decoration: none; }
a:hover { text-decoration: underline; }
.shell { display: grid; grid-template-columns: 176px minmax(0, 1fr); min-height: 100vh; }
.sidebar { border-right: 1px solid #a2a9b1; padding: 18px 14px; background: #f8f9fa; }
.sidebar a { display: block; margin: 8px 0; }
.brand { font-family: Georgia, serif; font-size: 20px; color: #202122; }
.search input, .search-page input { width: 100%; box-sizing: border-box; border: 1px solid #a2a9b1; padding: 6px; }
.article { max-width: 1040px; padding: 22px 34px 48px; }
h1 { font-family: Georgia, 'Times New Roman', serif; font-weight: 400; font-size: 32px; border-bottom: 1px solid #a2a9b1; margin: 0 0 14px; }
h2 { font-family: Georgia, 'Times New Roman', serif; font-weight: 400; font-size: 22px; border-bottom: 1px solid #eaecf0; margin-top: 28px; }
.lead { font-size: 16px; max-width: 760px; }
.infobox { float: right; clear: right; width: 260px; border: 1px solid #a2a9b1; background: #f8f9fa; margin: 0 0 16px 24px; padding: 10px; display: grid; grid-template-columns: 96px 1fr; gap: 6px 8px; font-size: 13px; }
.toc { display: inline-block; border: 1px solid #a2a9b1; background: #f8f9fa; padding: 10px 14px; margin: 12px 0; }
.toc ol { margin: 6px 0 0 20px; padding: 0; }
.meta, .status { color: #54595d; font-size: 13px; }
.generated-summary { max-width: 820px; border-left: 3px solid #a2a9b1; padding-left: 12px; margin: 18px 0; }
.section-lede { color: #54595d; margin: 6px 0 10px; }
.concept-index { width: 100%; border-collapse: collapse; margin-top: 8px; }
.concept-index th, .concept-index td { border: 1px solid #a2a9b1; padding: 7px 9px; vertical-align: top; }
.concept-index th { background: #eaecf0; text-align: left; font-weight: 600; }
.concept-index td:first-child { width: 240px; }
.concept-index td:last-child { width: 180px; }
.memory-text { white-space: pre-wrap; }
button { border: 1px solid #a2a9b1; background: #f8f9fa; padding: 5px 9px; cursor: pointer; }
button:hover { background: #fff; }
.fragment { margin-top: 8px; }
@media (max-width: 760px) {
  .shell { display: block; }
  .sidebar { border-right: 0; border-bottom: 1px solid #a2a9b1; }
  .article { padding: 18px; }
  .infobox { float: none; width: auto; margin: 0 0 16px; }
}
"""


def _script() -> str:
    return """
document.addEventListener('click', async (event) => {
  const button = event.target.closest('button[data-fragment]');
  if (!button) return;
  const target = button.parentElement.querySelector('.fragment');
  button.disabled = true;
  target.textContent = 'Loading...';
  try {
    const response = await fetch(button.dataset.fragment);
    const text = await response.text();
    target.innerHTML = response.ok ? text : '<p>' + text + '</p>';
  } catch (error) {
    target.textContent = 'Failed to load section.';
  } finally {
    button.disabled = false;
  }
});
"""
