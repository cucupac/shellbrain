# Storage Layer

From design conversation 2026-02-14.

## Physical split

- One SQLite DB per repo. Contains event log, cards, embeddings, FTS index.
- One global SQLite DB. Same schema, preferences only.
- Retrieval reads current repo DB + global DB. Nothing else.
- The repo boundary is physical, not a WHERE clause. Can't accidentally leak.
- Delete a repo, delete its DB, done.

Within repo DBs, experiential shellbrain should be represented as linked records:
- `problems`
- `solutions`
- `failed_tactics`
- link/edge table(s) between them

Episode logs remain immutable evidence and do not replace these retrieval projections.

## Why SQLite, not a vector DB

Need structured filtering, full-text search, relational integrity, append-only ordering, AND vector similarity. Vector DBs give one of those. SQLite gives all but one, and cosine is trivially computed in application code at this scale.

## Scale

Budget caps bound repo cards to hundreds, not thousands. Brute-force cosine over a few hundred vectors takes milliseconds. No ANN index needed. Budget caps are both entropy control and a performance guarantee.

## Query cost

The real cost per read is one embedding model call to embed the query (~10-50ms local, one network round trip if API). Similarity computation over the candidate set is negligible.

## Read flow

1. Open repo DB + global DB.
2. Load all active cards (hundreds).
3. Embed the query once.
4. Cosine against all stored vectors. Milliseconds.
5. Lexical scores (FTS/Jaccard). Milliseconds.
6. Blend, threshold, traverse linked experiential neighbors, select.

## Embeddings

Stored in the DB as vectors. Computed by a real embedding model. The card statement is the source of truth. The embedding is a derived cache, recomputable. Swap models, re-embed all cards.

## Event log is the authority

Cards, embeddings, FTS index are all projections. Rebuilt by replaying the event log. The log is the only thing that must survive.
