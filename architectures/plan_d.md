# Memory System — Implementation Plan

## Phase 0: Foundation (the log)

Define episode schema: user text, model text, tool outputs, stable IDs, hashes.

Implement append-only episode log at `~/.shellbrain/episodes/`.

Write serialization (JSON lines or SQLite — pick one, don't abstract).

Build `shellbrain record` CLI command that accepts a raw episode and appends.

No cards, no retrieval, no intelligence. Just durable storage that never loses work.

**Done when:** episodes are being written reliably from real agent sessions.

## Phase 1: Card store + write path

Define card schema: id, kind, statement, scope, status, evidence refs, embedding, created_at.

Four kinds: `preference`, `fact`, `negative_result`, `tactic`. No more.

Status enum: `active`, `needs_recheck`, `deprecated`.

Implement card storage at `~/.shellbrain/cards/` (SQLite or flat files, same choice as log).

Build the consolidation LLM call: reads episode, proposes candidate cards with evidence refs.

Thin rule layer: budget caps per (scope, kind), dedup by embedding similarity, evidence required.

Consolidation ledger: log every proposal, admission, rejection with reasons.

Wire post-episode hook: after record, auto-trigger consolidation.

**Done when:** real episodes produce reasonable cards with citations. Ledger is inspectable.

## Phase 2: Retrieval (the hard part)

Generate embeddings for all cards (pick a model, stick with it).

Build similarity index (FAISS, annoy, or even brute-force at low volume).

Implement `shellbrain recall`: query by scope + embedding similarity + recency.

Return ranked candidate set. No packing yet — just candidates.

Implement `shellbrain search`: explicit query, bypasses auto-pack, returns raw matches with citations.

Implement `shellbrain check`: lightweight probe — "is this still true?" against card store.

**Done when:** recall returns relevant cards for real task contexts. search works for browsing.

## Phase 3: Context packing

Build the LLM packing call: given candidates, current task context, pick what goes in.

Slot guidance (not hard rules): constraints first, negative results for errors, tactics for how-to.

Diversity cap: max 1-2 cards per topic in the final pack.

Implement pre-pack hook: runs recall, builds candidate set, LLM judges, injects context block.

The agent now sees something like: `[memory: 8 cards loaded, 2 constraints, 1 negative result...]`

**Done when:** agent sessions start with relevant, non-redundant shellbrain context injected automatically.

## Phase 4: Lifecycle + mid-session updates

Implement `shellbrain update`: deprecate, supersede, promote. Requires evidence ref.

**Preference/constraint lifecycle:** near-permanent, changed only by explicit user statement.

**Fact lifecycle:** active until tool output contradicts. Flip to deprecated with evidence link.

**Negative result lifecycle:** high priority on context match, quiet otherwise.

**Tactic lifecycle:** active until superseded by a better tactic or deprecated by failure evidence.

Agent can now call update mid-episode when it discovers something is wrong.

**Done when:** cards transition states correctly. Deprecated cards stop appearing in auto-pack.

## Phase 5: Deprecation + dedup (no decay)

Nothing fades by age or disuse. No timers. No LLM "would I keep this?" reviews.

Cards are active until concrete evidence says otherwise:

- **Fact:** tool output contradicts it → deprecated with evidence link.
- **Preference/constraint:** user explicitly changes it → superseded.
- **Tactic:** failure evidence or user correction → deprecated.
- **Negative result:** underlying issue is fixed (tests pass now) → deprecated.

Deprecated cards stay in the store, searchable, but excluded from auto-pack.

Redundancy handled by dedup sweep: merge near-duplicates by embedding + lexical overlap.

Budget caps remain as a write-path guardrail. Store grows, retrieval handles relevance.

Wire `shellbrain dedup` CLI for on-demand merge runs.

**Done when:** stale cards get deprecated by evidence, not vibes. Store stays clean via dedup.

## Phase 6: Graph edges + associative retrieval

Add explicit graph edges: `supersedes`, `deprecated_by`, `scoped_within`.

Build lightweight neighbor index over embeddings.

At retrieval: after top-K direct matches, do 1-2 associative hops (cosine > threshold).

Neighbors enter candidate set for LLM to judge. Not auto-included.

Hard bound: 2 hops max. Relevance is not transitive.

**Done when:** retrieval surfaces useful related cards that direct search wouldn't have found.

## Phase 7: Scope + generalization

Per-repo `.shellbrain/` directory: scope ID linking to central store.

Repo-specific config overrides (what counts as build success, etc.).

Promotion rules: repo → domain when LLM observes same lesson across repos, or user says so.

Domain → global: only on explicit user statement.

Conservative by default. False generalization is worse than redundant narrow cards.

**Done when:** cross-repo knowledge surfaces when relevant. No false generalization leaking.

## Phase 8: Hardening + instrumentation

`shellbrain status` CLI: ledger summary, store health, card counts by scope/kind/status.

Retrieval quality tracking: did the agent use what was packed? Did the user correct it?

Consolidation quality tracking: are cards being written that never get retrieved?

Edge cases: concurrent episodes, corrupted log recovery, embedding model migration.

Documentation: API reference, card kind semantics, lifecycle diagrams.

**Done when:** you can answer "is the shellbrain system helping?" with data, not vibes.

## What's deliberately deferred

- Causal attribution / decision points / arm-level credit assignment.
- Statistical utility convergence (needs volume you don't have yet).
- Multi-user support.
- Rich ontology of graph edge types beyond the three needed.
- Automated revalidation probes (grep checks, file existence). Add if passive deprecation proves too slow.
- Time-based decay of any kind. If this ever seems needed, it means deprecation signals are missing.