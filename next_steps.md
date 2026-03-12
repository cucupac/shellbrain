# Next Steps

## 1. Read-Policy Config Cleanup

- Make the read-side hyperparameters concrete in `app/config/defaults/read_policy.yaml`.
- Move hardcoded RRF defaults out of `app/boot/retrieval.py` and load them from YAML.
- Put context-pack builder knobs in the same read-policy config surface:
  - `N_direct`
  - `N_explicit`
  - `N_implicit`
  - later, scenario-related pack defaults
- Ensure CLI hydration and runtime policy code both read from the same config source so there is one clear source of truth.

## 2. Context-Pack Builder

- Implement real pack assembly on top of the new scoring stage.
- Add quota-based bucket selection, dedupe, spillover, and hard-cap enforcement.
- Add tests for pack assembly behavior before extending scenario work.

## 3. Agent-Facing Context Pack Shape

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

## 4. Retrieval Metadata and Usage Signals

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

## 5. System Performance Metrics

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

## 6. Later: Local Model for Triage / Filtering

- Consider a smaller local model ahead of the main model for cheap first-pass categorization or filtering.
- Possible uses:
  - classify query intent before retrieval
  - filter obviously irrelevant memories
  - route between retrieval strategies
  - perform cheap reranking before the higher-cost model sees context
- Treat this as a later optimization after baseline metadata and metrics exist, so we can measure whether it actually improves quality, latency, or cost.

## 7. Usability: Batch Questions for Memory Reads

- Support a single memory-read call that accepts multiple questions at once, instead of forcing the LLM into sequential reads.
- The goal is to let the model ask for "everything I need to know" in one interaction when it has several sub-questions.
- Return results in a structured place the LLM can inspect directly, for example:
  - one section per question
  - shared results that apply across questions
  - deduped memories reused across the batch
  - per-question rationale for why each memory was included
- This should reduce extra tool turns and token burn caused by back-to-back memory queries.
- Design the interface so batching is a first-class usability path, not just a thin wrapper around repeated single-question retrieval.
