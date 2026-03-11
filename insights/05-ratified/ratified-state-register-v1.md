# Ratified State Register v1

Status: canonical digest of what is currently ratified.
Last updated: 2026-02-25.

## Purpose

Provide one place to answer:
- what is ratified now,
- what older language is superseded,
- what is still open.

Implementation-facing pack:
- `insights/06-working-set/`

## Supersession Rule (Newer Wins)

- If two files conflict, the newer ratified decision wins.
- Use this precedence order for implementation guidance:
  1. This register and its referenced latest discovery entry.
  2. Latest dated ratification entries in `insights/discovery.md`.
  3. Older foundation/breakthrough/refinement language.
- Older wording remains historical context unless explicitly re-ratified.

## Ratified Decisions (Active)

### 1) Interface and policy boundaries
- External interface verbs are conceptually `create`, `read`, `update`.
- Policy routing is fixed:
  - `read` -> Read Policy.
  - `create` -> Create Policy.
  - `update` -> Update Policy.
- Validation layer sits directly below interface and enforces:
  - schema validity,
  - semantic write/read policy validity,
  - DB integrity compatibility.
- Write-path atomicity is required: accepted operations commit in one transaction or fully abort.
- Two-layer interface model is ratified:
  - strict internal contract (full payload, deterministic validation),
  - ergonomic CLI adapter (contextual field inference before strict validation).
- Ergonomic adapter rule is ratified:
  - explicit agent-provided fields always override inferred defaults.

### 2) Naming locks (ratified in this conversation)
- Canonical interface creation verb is `create` (not `write`).
- Episodic container naming stays `episodes` (do not rename to `work_sessions`).

### 3) Memory model and kinds
- Active atomic memory kinds:
  - `problem`, `solution`, `failed_tactic`, `fact`, `preference`, `change`.
- Experiential memory is explicit linked records, not hidden in episode text only.
- Failed tactics are first-class memories, not metadata on solutions/facts.

### 4) Truth and utility stance
- Current code/workspace observation is instantaneous truth.
- Memory is advisory utility and may be stale.
- v1 truth evolution is modeled via immutable facts + fact-update chain links, not mutable truth score fields.
- Utility is contextual (problem-linked observations), with optional global weak prior usage.

### 5) Write/update semantics
- `create` writes immutable memories and immutable link/evidence records.
- `update` is limited to lifecycle/feedback mechanics:
  - `archive_state`,
  - `utility_vote`,
  - `fact_update_link`,
  - `association_link`.
- "X changed and invalidates Y" is represented with immutable writes:
  - create `change`,
  - create replacement `fact`,
  - link via `fact_update_link`.
- Create-path evidence policy is strict in Create Policy v1:
  - `evidence_refs >= 1` for all create kinds (preferences may cite user/session evidence).
- Formal-association write path is ratified:
  - explicit links authored by agent via `create.links.associations[]` or `update.association_link`,
  - implicit co-activation reinforcement channel runs under the hood and strengthens/weakens association edges.

### 6) Storage model
- PostgreSQL 16 relational v1 is ratified.
- Authoritative immutable tables include memories, links, utility observations, episodes/events/transfers, and evidence references.
- Formal-association storage is ratified:
  - `association_edges`,
  - `association_observations`,
  - `association_edge_evidence`.
- Derived views include:
  - `current_fact_snapshot`,
  - `global_utility`,
  - dependency/dependent count views.
- Graph behavior is represented through explicit relational link tables.

### 7) Episodic model
- Canonical episodic source is PostgreSQL tables (not markdown logs).
- `episodes` is the session container with lifecycle metadata.
- `episode_events` is one row per individual message/tool call with per-episode ordered sequence.
- `session_transfers` captures immutable cross-session handoff provenance.

### 8) Read policy v1 shape
- Dual-lane seed retrieval is ratified:
  - semantic lane + keyword lane.
- Rank fusion uses RRF for direct-seed ordering.
- Pack assembly is bounded and deterministic:
  - direct bucket,
  - explicit-link expansion bucket,
  - implicit semantic expansion bucket,
  - dedupe/spill,
  - final hard cap.
- Explicit-link expansion includes formal association links from `association_edges`.
- No separate association-read interface is added; association traversal is integrated inside the existing read-policy expansion step.
- Scenario lift is ratified as derived read abstraction and write-path projection dependency.
- `global_utility` is not part of online read ranking in v1.
- Earlier utility tie-break / near-tie nudge plans are superseded as over-engineering for the current retrieval system.
- Retrieval ordering remains grounded in direct-seed fusion, bucket-local expansion scoring, and deterministic pack assembly.

### 9) Semantic-matrix shaping constraints (ratified pre-lock)
- Do not hard-enforce `global` scope restriction to `preference` until separately ratified.
- Do not hard-enforce one-successor-only fact chains in v1.
- Keep DB triggers minimal in v1 and focus them on hard integrity invariants.
- Final semantic matrix must include explicit idempotency/duplicate handling rules.
- Final semantic matrix must include explicit validation-stage error contract.

### 10) Ergonomic adapter defaults (ratified shape)
- `repo_id` is inferred from cwd/repo resolver for agent-facing CLI calls unless explicitly set.
- `read` defaults (mode/include_global/limits/expand knobs) are inferred from policy config unless explicitly set.
- `create` defaults (`scope`, `confidence`) are inferred when omitted unless explicitly set.
- Auto-attached evidence refs are allowed only when provenance is unambiguous; otherwise request must provide explicit evidence refs.
- Typed association links (`links.associations[]`) are the preferred explicit relation path for agent-authored formal relationships.

### 11) Tech stack (ratified for implementation start)
- Runtime language: Python 3.12.
- Interface mode: CLI-first, JSON input/output for agent calls.
- Storage: PostgreSQL 16 with pgvector + PostgreSQL FTS.
- Durability requirement: data persistence must survive container deletion and Docker uninstall.
- Local storage discipline: PostgreSQL must use host bind-mounted data directory paths for local runs (not container-only filesystem state).
- Portability requirement: logical backup/export path (`pg_dump`/`pg_dumpall`) is part of v1 operational baseline.
- Data/migrations: SQLAlchemy Core + Alembic.
- Validation/tests: Pydantic v2 + pytest.
- Execution shape: core memory engine package + thin CLI hydration adapter.
- Background processing: start with in-process/session-end consolidation; escalate to queue worker only if needed.

## Resolved Drift Calls (Use Newer Direction)

- Use `create` terminology over older `write` wording when they conflict.
- Keep `episodes` over rename proposals like `work_sessions`.
- Prefer no mutable truth score (later contracts/storage) over earlier `[0,1] truth-score` draft framing.
- Treat strict create evidence requirements as canonical and codified at both schema shape and semantic-validation layers.
- Treat `create/read/update` contract framing as current v1 direction; older `dispute` language is historical baseline context.

## Still Open (Not Yet Ratified)

- Canonical `episode_events.content` payload shape.
- Canonical `evidence_refs.ref` pointer string format.
- Final read-pack quota defaults:
  - `N_direct`, `N_explicit`, `N_implicit`, `N_scenario`.
- Final default for `max_update_chain_depth`.
- Final scenario projection schema names/fields and constructor trigger boundaries.
- Final defaults for association traversal/ranking knobs:
  - `max_association_depth`,
  - `max_association_fanout`,
  - `min_association_strength`,
  - relation/source weighting.
- Final published semantic validation matrix by operation/kind and optional DB-trigger enforcement scope.
- Future alias policy if interface names are ever changed.

## Update Protocol

- Keep this file as a digest, not a replacement for chronology.
- Any new ratification should:
  1. append raw entry to `00-lab/immutable-work-log.md`,
  2. append ratified entry to `insights/discovery.md`,
  3. update this register so current state stays one-hop readable.
