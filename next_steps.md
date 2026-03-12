# Next Steps

## 1. Episodes and Session Transfer Support

- Implement the `episodes`, `episode_events`, and `session_transfers` persistence path end to end.
- Define the canonical `episode_events.content` payload contract and validate it at the edge.
- Add execution tests that prove episode creation, event append, and session-transfer writes work against PostgreSQL.
- Wire episode/session provenance into the parts of the system that are supposed to record it, rather than leaving the tables idle.

## 2. Backup and Export Baseline

- Add a concrete logical backup/export workflow using `pg_dump` or `pg_dumpall`.
- Add a documented restore workflow so moving the system to another machine is routine rather than ad hoc.
- Decide the default backup cadence and retention policy for local operation.
- Add a small script or command surface so backup/export is part of the operational path, not just a requirement in docs.

## 3. Read-Policy Config Cleanup

- Make the read-side hyperparameters concrete in `app/config/defaults/read_policy.yaml`.
- Move hardcoded RRF defaults out of `app/boot/retrieval.py` and load them from YAML.
- Put context-pack builder knobs in the same read-policy config surface:
  - `N_direct`
  - `N_explicit`
  - `N_implicit`
  - later, scenario-related pack defaults
- Ensure CLI hydration and runtime policy code both read from the same config source so there is one clear source of truth.

## 4. Context-Pack Builder

- Implement real pack assembly on top of the new scoring stage.
- Add quota-based bucket selection, dedupe, spillover, and hard-cap enforcement.
- Add tests for pack assembly behavior before extending scenario work.

## 5. Agent-Facing Context Pack Shape

- Design the read result as structured JSON for LLM agents rather than a flat list of IDs.
- Start with clear top-level sections:
  - `direct`
  - `explicit_related`
  - `implicit_related`
  - later, `scenarios`
- Each item should eventually carry enough context to be self-explanatory:
  - memory type
  - text/content
  - why it was included
  - relation/anchor metadata when relevant
  - priority/order within its section

## 6. Retrieval Metadata and Usage Signals

- Add lightweight metadata to every read result so behavior is inspectable without digging through logs.
- Useful fields to include:
  - accessed memory IDs
  - access timestamps
  - retrieval scores / rank position
  - memory type and source
  - freshness / last-updated time
  - token count per memory and per assembled pack
  - whether an item was directly matched, explicitly related, or implicitly related
  - whether an item was actually included vs. dropped by quotas or caps
- Track simple usage stats over time:
  - read frequency by memory
  - inclusion frequency by memory
  - drop frequency due to cap pressure
  - stale-memory hit rate
  - duplicate / near-duplicate retrieval rate

## 7. System Performance Metrics

- Define a small metrics set that tells us whether the memory setup is becoming more useful.
- Candidate metrics:
  - retrieval precision proxy: fraction of returned memories that are later referenced or used
  - context-pack utilization: fraction of included memories that affect the final answer
  - miss rate: cases where needed memory exists but was not retrieved
  - latency split: retrieval time, packing time, total read time
  - token efficiency: useful tokens / total context tokens sent to the model
  - freshness quality: share of retrieved memories that are recent enough for the task
  - repetition rate: how often the same low-value memories keep showing up
  - user correction rate: how often the answer is corrected because context was missing or noisy
- Add a feedback loop so these metrics can drive tuning of quotas, scoring, and dedupe rules.

## 8. Later: Local Model for Triage / Filtering

- Consider a smaller local model ahead of the main model for cheap first-pass categorization or filtering.
- Possible uses:
  - classify query intent before retrieval
  - filter obviously irrelevant memories
  - route between retrieval strategies
  - perform cheap reranking before the higher-cost model sees context
- Treat this as a later optimization after baseline metadata and metrics exist, so we can measure whether it actually improves quality, latency, or cost.

## 9. Usability: Batch Questions for Memory Reads

- Support a single memory-read call that accepts multiple questions at once, instead of forcing the LLM into sequential reads.
- The goal is to let the model ask for "everything I need to know" in one interaction when it has several sub-questions.
- Return results in a structured place the LLM can inspect directly, for example:
  - one section per question
  - shared results that apply across questions
  - deduped memories reused across the batch
  - per-question rationale for why each memory was included
- This should reduce extra tool turns and token burn caused by back-to-back memory queries.
- Design the interface so batching is a first-class usability path, not just a thin wrapper around repeated single-question retrieval.

## 10. V2: Automatic Related-Memory Reinforcement

- Treat this as v2, not v1.
- Add a background task that looks at which memories are repeatedly retrieved, cited, or used together.
- Use those co-usage signals to suggest or reinforce soft `associated_with` links automatically.
- Keep this separate from explicit agent-authored links like `depends_on`.
- Decide the exact evidence threshold before it is allowed to create or reinforce a link.
- Keep the reinforcement path auditable so auto-created links can be inspected, downgraded, or removed.

## 11. Possible Consideration: Exact-Retry Idempotency

- Consider exact-request retry dedupe for mutating operations if duplicate writes become an operational issue.
- Keep this narrow: exact normalized request replay within a short window, not fuzzy duplicate detection on memory text.
- Treat this as optional until there is real evidence that retries are creating duplicate data in practice.

## 12. Later: Learned Memory-Type Classification

- Once enough labeled memories exist, train a lightweight classifier to predict memory type from the memory text and nearby context.
- Use it to suggest or auto-fill `kind` so the agent does not need to classify every memory by hand forever.
- Keep the agent able to override the prediction, especially while the classifier is still immature.
- Track classifier confidence and disagreement rate before letting it become more automatic.
- Treat this as a later optimization after the corpus is large enough to provide useful training data.
