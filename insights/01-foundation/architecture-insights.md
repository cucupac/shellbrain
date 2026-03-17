# Architecture Insights

From design conversation 2026-02-14.

## Two scopes, not three

Repo and global. Domain is gone.

- Facts and tactics are evidence-grounded in the repo they were observed in. They lose meaning outside that context. They live and die at repo scope.
- Preferences are about the user, not the code. They travel everywhere. They live at global scope (or repo scope if repo-specific).
- Domain was "patterns across some repos." That's generalization. Generalization is the LLM's job, not the shellbrain system's job.

## No cross-repo leakage

Repo A's facts are invisible in repo B. Not lower-ranked — invisible. Hard filter, not soft score.

The LLM working in repo A needs two things: the user (global preferences) and the current repo (repo facts/tactics). Nothing else.

This makes the scoper a WHERE clause, not a scoring component.

## The shellbrain system stores observations, not generalizations

The system's job is to remember what it saw, anchored to evidence. The LLM's job is to infer, generalize, and adapt. Forcing the storage layer to generalize (e.g., abstracting a fact for promotion) puts inference in the wrong layer.

## Three kinds, not six

Preference, fact, tactic. That's it.

- Constraint is a preference with stronger language. Same kind, evidence tells you the strength.
- Commitment is a time-bounded fact. Store as fact.
- Negative result is a tactic outcome. Store failed tactics as first-class linked records, not only as fact metadata.

## Three LLM interfaces

Read, write, dispute. Everything else is internal.

- Read: ambient (pack at conversation start) and targeted (search mid-task).
- Write: record evidence-anchored observations.
- Dispute: flag a served shellbrain as wrong.

## The read pipeline

Scope → relevance → association → threshold → selection.

- Scope: hard filter (current repo + global).
- Relevance: semantic similarity to query.
- Association: walk from direct matches to neighbors with decay. Core, not an add-on.
- Threshold: minimum score floor. Below it, return nothing. Empty is correct.
- Selection: fill context budget with diversity constraints.

For experiential retrieval, query across linked problem, solution, and failed-tactic memories, then expand across links before final selection.

## Experiential graph shape

Model experiential shellbrain as linked nodes:
- Problems
- Solutions (worked attempts)
- Failed tactics (did-not-work attempts)

The immutable episode log remains raw evidence. Retrieval serves normalized nodes linked to that evidence.

## Threshold philosophy

Returning nothing is better than returning noise.

- Ambient reads (pack): stricter threshold. Query is speculative.
- Targeted reads (search): more permissive. LLM constructed the query from a specific need.
- Preferences: lower threshold. Getting user preferences wrong is high-cost.
- Facts: higher threshold. A wrong or stale fact actively hurts.

## Three architectural layers

1. Interface — read, write, dispute. What the LLM sees.
2. Engines — retrieval pipeline, consolidation pipeline, dispute pipeline. The logic.
3. Store — event log, reducers, projections. The substrate.

## Simplify before building

Cut what hasn't earned its complexity:
- Utility attribution (win/loss on tactics): defer until tactic volume justifies it.
- Causal gates: defer until running at scale.
- Observability dashboards: defer until there's data worth dashboarding.
- Recovery pipeline: replay from log is sufficient for single-user local SQLite.

Build the simplest version that preserves: evidence-grounded writes, budget-controlled entropy, and precision-over-recall retrieval.
