# Next Steps

## Where We Are

- `shellbrain` is now a packaged machine-level CLI with the core workflow in place:
  - `init`
  - `read`
  - `events`
  - `create`
  - `update`
- Operator/admin surfaces exist and are tested:
  - `shellbrain admin doctor`
  - `shellbrain admin backup create|list|verify|restore`
  - `shellbrain admin session-state inspect|clear|gc`
- Trusted caller identity, per-caller session state, and guidance nudges are implemented.
- Usage telemetry is already live, not speculative:
  - command invocation records
  - read summaries and read-result items
  - write summaries and write-effect items
  - episode sync summaries and tool-type counts
  - derived analytics views for command usage, memory retrieval, write effects, sync health, and session protocol
- Read-pack metadata is already in the product:
  - `meta`, `direct`, `explicit_related`, `implicit_related`
  - `kind`, `text`, `why_included`, `priority`
  - `anchor_memory_id` and `relation_type` where relevant
- Scenario lift is still intentionally deferred from the returned read pack.
- The only explicit read-policy TODOs left in code are:
  - `app/core/policies/read_policy/utility_prior.py`
  - `app/core/policies/read_policy/scenario_lift.py`

## Near-Term Priorities

### 1. Dogfood in real repos

- Use Shellbrain in external repos and real agent sessions.
- Capture concrete friction instead of abstract theory:
  - bad or empty session selection
  - confusing guidance
  - reads that return noise
  - `events` runs that do not lead to a natural write
  - surprising bootstrap or model-readiness behavior

### 2. Put a user-facing surface on top of the telemetry we already store

- The backend telemetry and SQL views now exist; the missing piece is operator visibility.
- Add an operator-facing report or viewer for:
  - session protocol summary per thread
  - sync health by host app
  - top retrieved memories
  - write and utility activity
  - zero-result and ambiguity rates
- The goal is to answer normal product questions without raw SQL.

### 3. Finish the protocol-assist loop

- Current guidance mostly covers pending `utility_vote` follow-through.
- Extend that into a clearer closeout path that can tell an agent:
  - what reads happened this session
  - what retrieved memories still need utility votes
  - whether a `problem` has matching `solution` / `failed_tactic`
  - whether fresh `events` were inspected before a write
- Keep this in soft-nudge territory first. Do not jump to hard failures before dogfooding proves the nudges help.

### 4. Improve retrieval quality, not just retrieval observability

- Implement the near-tie utility prior in `app/core/policies/read_policy/utility_prior.py`.
- Use the existing telemetry to find:
  - repeated low-value memories
  - stale-but-frequent hits
  - duplicate packs across similar reads
  - misses where the right memory existed but was not surfaced
- Tune quotas and scoring only after looking at real usage.

### 5. Tighten operator polish

- Make first-run model download and readiness less surprising.
- Keep repo identity and `--repo-root` behavior explicit.
- Decide the expected backup cadence and retention guidance for the normal local install path.

## Later, On Purpose

- Batch multiple read questions into one call, with deduped shared results.
- Build real handoff flows on top of `session_transfers`.
- Revisit scenario lift only after the atomic-memory path and operator surface feel stable.

## Not V1 Unless Evidence Forces It

- automatic related-memory reinforcement
- learned memory-type classification
- a smaller local triage or rerank model ahead of the main retrieval path
- exact-retry idempotency for writes
