# Design Summary

From design conversation 2026-02-14.

**Interfaces:** Read (ambient + targeted), write, dispute. Everything else is internal.

**Ontology:** Experiential (linked problems, solutions, and failed tactics), preferences (global + repo with inheritance/override), structural (hierarchical codebase map, built incrementally).

**Creation:** LLM writes formed memories with category tags at write time. No heuristic classifier. For experiential memory, the LLM can extract worked and failed attempts from immutable episode evidence and link both to problems. Structural shellbrain is the exception — built across episodes via read-before-write revision.

**Scoping:** Repo and global. No domain. Repo facts are physically invisible to other repos. Preferences are the only thing that crosses repo boundaries. The system stores observations, not generalizations — generalizing is the LLM's job.

**Storage:** SQLite. One DB per repo, one global DB. Event log is the authority, everything else is a rebuildable projection. Experiential projections should model linked `problems`, `solutions`, and `failed_tactics`. Embeddings are a derived cache. Budget caps keep cards in the hundreds, making brute-force retrieval trivial.

**Read pipeline:** Scope → relevance → association → threshold → selection. Nothing below threshold is returned. Empty is correct. Stricter for ambient reads, more permissive for targeted. Lower thresholds for preferences, higher for facts. For experiential recall, retrieval runs over problems/solutions/failed tactics and expands across links.

**Principles:** Precision over recall. Simplify before building. Defer what hasn't earned its complexity.
