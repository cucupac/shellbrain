# Read Policy Notes

This folder holds the retrieval and pack-assembly logic for the ratified read pipeline.

## Lexical Lane Rationale

The keyword lane uses app-side BM25 scoring plus a coverage-aware admission gate.

Why the old approach was wrong:
- The previous PostgreSQL FTS query construction was too permissive.
- It effectively admitted memories on any token-prefix hit.
- In a dual-lane RRF system, noisy keyword admission pollutes direct seeds.

Why hard `AND` was also wrong:
- Hard all-term matching is cleaner than the old permissive lane, but it over-corrects.
- This repository stores short atomic memories, so a relevant shellbrain can easily miss one query term and still be useful.
- A hard all-terms gate hurts lexical recall too much for `targeted` reads.

## Current Decision

The lexical lane now has three parts:
- `lexical_query.py`: deterministic normalization only.
- `bm25.py`: BM25 scoring and coverage-gate helpers.
- `retrieval/seed_retrieval.py`: use-case orchestration over a visibility-gated corpus from the SQL adapter.

The gate is based on weighted query coverage:

```text
coverage = matched_query_idf_weight / total_query_idf_weight
```

Where:
- `matched_query_idf_weight` is the sum of BM25 IDF weights for the informative query terms found in a memory.
- `total_query_idf_weight` is the sum of BM25 IDF weights for all informative query terms in the query.

Mode thresholds:
- `targeted`: `coverage >= 0.65`
- `ambient`: `coverage >= 0.80`

This gives the lexical lane the shape we want for this repo:
- stricter than pure OR matching,
- softer than hard AND,
- more permissive for `targeted` reads,
- stricter for `ambient` reads,
- still compatible with semantic + keyword RRF fusion.
