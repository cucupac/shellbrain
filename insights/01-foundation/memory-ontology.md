# Memory Ontology

From design conversation 2026-02-14.

## Three categories

### 1. Experiential — "what happened"

Problem/failure/solution triples. Episodic. Anchored to specific situations.
- Written after episodes.
- Queried by problem similarity.
- Stale when codebase changes invalidate them.
- A tactic without its problem is meaningless. They're linked, not separate cards.
- Model as linked shellbrain records: `problem`, `solution`, `failed_tactic`.
- `solution` and `failed_tactic` are distinct shellbrain types even when both come from the same episode.
- The immutable episodic log is evidence; experiential records are the normalized retrieval layer.

### 2. Preferences — "how things should be done"

Statements about style, approach, conventions.
- Two levels: global (user-wide) and repo (repo-specific).
- Repo extends or overrides global. Child-class inheritance.
- Retrieval must resolve conflicts: repo wins over global when they contradict.
- Written when user states a preference.
- Stale when user contradicts.

### 3. Structural — "what is this codebase"

Semantic map. Module boundaries, abstractions, data flow, naming, where things live.
- Not episodic. Built incrementally, revised over time, never complete.
- Hierarchical: high-level architecture → module-level → detail.
- Queried by what part of the codebase the LLM is touching.
- Goes stale constantly as code evolves. Hardest to keep fresh.

## Why they're distinct

Different write patterns, read patterns, staleness behavior, and shape.
- Experiential: linked graph (problems, solutions, failed tactics).
- Preferences: key-value with inheritance.
- Structural: hierarchical map, coarse to fine.

## Same store, different projections

One event log records all observations. Card projections diverge by category.
Retrieval engine needs to know which category it's searching — query strategy differs for each.
