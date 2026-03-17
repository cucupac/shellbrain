# Immutable Work Log

Raw, append-only design notes while iterating on the shellbrain system.

Rules:
- Append only; do not rewrite prior entries.
- Corrections are new entries that reference the earlier timestamp.
- Keep entries terse and factual.

## 2026-02-18 01:40:38 CST

- Proposed: dogfood the shellbrain design process by auto-recording notes without being asked.
- Worked: two-layer logging model (`immutable-work-log.md` raw + `discovery.md` abstraction) fits the current workflow.
- Did not work / risk: relying only on `discovery.md` loses raw context and intermediate reasoning.
- Open: how often to abstract raw notes into discovery (every turn vs milestone-only).
- Files touched: `insights/README.md`, `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-18 01:45:54 CST

- Proposed: decide between formal Bayesian updates and lightweight heuristic updates for truth/utility.
- Worked: framing as a staged approach preserves velocity while keeping Bayesian compatibility.
- Did not work / risk: full Bayesian formalization now is likely overfit/over-complex given low-volume evidence.
- Decision (provisional): use lightweight heuristic updates in v1; design signals so Bayesian updating can be added later without schema or ontology churn.
- Cadence decision: append to raw log every ideation turn; add to `discovery.md` only when there is a decision, policy shift, or new open-question cluster.
- Open: explicit thresholds for when to graduate from heuristics to Bayesian (for example, minimum observations per memory/problem neighborhood).
- Files touched: `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-18 01:55:00 CST

- Proposed: use LLM certainty plus supporting evidence references for truth/utility updates.
- Worked: lightweight rule can require evidence without introducing rigid taxonomy.
- Did not work / risk: requiring strict evidence for every utility signal may be too heavy in low-friction workflows.
- Open: should truth updates require hard evidence while utility updates allow softer evidence from session outcomes?
- Files touched: `insights/00-lab/immutable-work-log.md`.

## 2026-02-18 01:59:00 CST

- Proposed: utility evidence should be optional; truth evidence should be strict.
- Worked: reducing strict attribution burden for utility preserves practicality.
- Did not work / risk: utility updates without evidence can drift or overfit if unconstrained.
- Proposed interface direction: use a clean scoped shellbrain API with JSON payloads/returns rather than freeform text parsing.
- Open: best interaction form for the model layer (tool-style API, CLI wrapper, or both).
- Files touched: `insights/00-lab/immutable-work-log.md`.

## 2026-02-18 02:24:04 CST

- Proposed: consolidate status and define concrete next implementation decisions.
- Worked: explicit request to move from ideation summary to concrete spec targets.
- Did not work / risk: delaying concrete contract decisions may stall transition to implementation.
- Open: choose exact API verbs/payloads, update function shape, and evidence reference contract.
- Files touched: .


## 2026-02-18 02:24:40 CST (Correction)

- Correction for entry `2026-02-18 02:24:04 CST`: malformed `Files touched` field due shell interpolation in append command.
- Correct files touched: `insights/00-lab/immutable-work-log.md`.

## 2026-02-18 02:30:00 CST

- Proposed: make categorization explicit via write-contract choices (scope + kind) with LLM judgment plus lightweight validation.
- Worked: concrete JSON shape for `read` and `write` reduces ambiguity about how categorization happens.
- Did not work / risk: too many enum choices could reintroduce rigidity if not kept minimal.
- Open: final canonical kind set (fact/preference/tactic vs experiential subtypes) and auto-vs-explicit override behavior.
- Files touched: `insights/00-lab/immutable-work-log.md`.

## 2026-02-18 02:32:59 CST

- Proposed: clarify update API semantics and remove ambiguous auto categorization in write payloads.
- Worked: distinguish optional two-step update (propose/apply) from simpler one-step commit flow.
- Did not work / risk: auto categorization field name created confusion about where judgment lives.
- Open: whether v1 uses two-step approval flow or single update endpoint with dry_run/commit mode.
- Files touched: insights/00-lab/immutable-work-log.md.

## 2026-02-18 02:38:22 CST

- Proposed: settle v1 interface semantics: write creates immutable memories (including change/update memories), update adjusts dynamic values (truth/utility).
- Worked: clear separation resolves confusion between "update memory" and "update operation".
- Did not work / risk: if update operation is treated as hard overwrite, provenance can be lost; recommend event-backed projection under the hood.
- Open: exact allowed kind enum and required evidence fields by operation.
- Files touched: insights/00-lab/immutable-work-log.md.

## 2026-02-18 02:47:58 CST

- Proposed: persist approved interface schemas as a concrete contract card and link from discovery.
- Worked: captured exact approved JSON schemas for read/write/update in a single source-of-truth card.
- Did not work / risk: none noted in this step.
- Open: semantic validation matrix details by kind remain to be finalized.
- Files touched: insights/04-contracts/memory-interface-json-schemas-v1.md, insights/discovery.md, insights/README.md, insights/00-lab/immutable-work-log.md.

## 2026-02-18 21:50:21 CST

- Proposed: audit convo transcript against `insights/` and fill missing ratified refinements.
- Worked: identified and captured missing synthesis around anti-rigidity update policy and late interface clarifications.
- Did not work / risk: some fallback mechanics were approved directionally but remain underspecified numerically.
- Open: exact bounded update math and exact no-evidence utility fallback behavior.
- Files touched: `insights/03-refinements/lightweight-update-policy-and-interface-clarifications.md`, `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-18 23:30:45 CST

- Proposed: lock a concrete storage schema matching the approved interface and latest modeling decisions.
- Worked: converged on relational SQLite v1 with explicit graph semantics via link tables.
- Worked: simplified experiential linkage to direct `problem_attempts` (no separate scenario table in v1).
- Worked: removed mutable truth/accuracy score; modeled fact correctness via immutable `fact_updates` chains and `current_fact_snapshot` view.
- Worked: captured utility as contextual observations in `[-1,1]` via `(memory_id, problem_id, vote)`.
- Did not work / risk: full trigger-level enforcement of all semantic invariants was deferred; still relies on interface semantic validation.
- Open: whether scenario-level metadata earns reintroducing a scenario container later.
- Files touched: `insights/04-contracts/memory-storage-relational-schema-v1.md`, `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-19 02:08:59 CST

- Proposed: separate naming into policy layer (`Read Policy`, `Write Policy`) and interface verb layer (`create`, `read`, `update`).
- Worked: clarified that `update` is operationally a write-path action while still remaining its own interface verb for cleaner agent behavior.
- Worked: established deterministic routing mental model: `read` -> Read Policy; `create`/`update` -> Write Policy.
- Did not work / risk: term drift remains because current contract payloads still use `op: "write"` while conversation naming now prefers `create`.
- Open: whether to rename wire-level `op: "write"` to `op: "create"` now, or support `create/write` aliasing for a transition period.
- Files touched: `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-19 02:21:32 CST

- Proposed: ratify a concrete Write Policy v1 that bridges interface verbs and relational schema side effects.
- Worked: locked policy routing and boundaries — `read` uses Read Policy; `create` and `update` use Write Policy; LLM still decides shellbrain judgment (`kind`, `scope`, text, links, evidence refs) while policy enforces deterministic validity/storage.
- Worked: locked write validity as 3 ordered gates: schema validity -> write-policy semantic validity -> DB integrity validity (single atomic transaction or full reject).
- Worked: locked strict evidence stance for create in v1 (`evidence_refs >= 1` for all create kinds, including `preference`, where evidence may be conversation/user-turn references).
- Worked: locked deterministic update mapping:
  - `archive_state` -> `memories.archived`,
  - `utility_vote` -> `utility_observations`,
  - `fact_update_link` -> `fact_updates` with kind checks.
- Did not work / risk: evidence pointer storage is concrete (`evidence_refs` table), but canonical storage contract for the underlying episodic source content remains underspecified.
- Open: define episodic ongoing log contract (where source content lives + canonical `evidence_ref` pointer format).
- Files touched: `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-19 02:28:14 CST

- Proposed: finalize episodic ongoing log strategy so evidence pointers have a single canonical target.
- Worked: ratified single source of truth in SQLite for episodic data; any plaintext/markdown running log is export-only and non-authoritative.
- Worked: ratified minimal episodic schema direction:
  - `episodes(id, repo_id, started_at, ended_at)`
  - `episode_events(id, episode_id, seq, content, created_at)`
- Worked: ratified event granularity as one row per individual message/tool call (not one row per full turn), while keeping `content` minimally structured.
- Worked: ratified v1 evidence pointer unit as whole-event references (`ref = episode_event_id`), deferring span-level offsets.
- Did not work / risk: if event payload shape is left too implicit, implementations may diverge on what gets serialized into `content`.
- Open: define canonical v1 `episode_events.content` payload shape and canonical `evidence_ref` string format.
- Files touched: `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-21 19:06:49 CST

- Proposed: extend episodic schema to explicitly represent work sessions (session IDs + metadata) and immutable cross-session message transfers.
- Worked: ratified `episodes` as the work-session container and extended metadata (`thread_id`, `title`, `objective`, `status`, `started_at`, `ended_at`).
- Worked: ratified stronger per-session event constraints in `episode_events` (`source`, unique `(episode_id, seq)`).
- Worked: added immutable `session_transfers` model to record cross-session handoff metadata (`from_episode_id`, `to_episode_id`, `event_id`, `transfer_kind`, `rationale`, `transferred_by`, timestamps).
- Worked: preserved single canonical SQLite episodic store while keeping logs session-partitioned by IDs (not one undifferentiated stream, not one DB/file per session).
- Did not work / risk: `episodes` naming may continue to read as narrative episodes instead of explicit work sessions unless aliasing or rename strategy is defined.
- Open: canonical `episode_events.content` payload shape and canonical `evidence_ref` pointer string format remain unresolved.
- Files touched: `insights/04-contracts/memory-storage-relational-schema-v1.md`, `insights/discovery.md`, `insights/00-lab/immutable-work-log.md`.

## 2026-02-21 19:52:04 CST

- Proposed: concretize read-policy context-pack assembly using lane-specific thresholds plus rank fusion (RRF), instead of raw-score max between semantic and keyword lanes.
- Worked: defined `rank` explicitly as lane-local query position and captured concrete RRF formula for direct-seed ranking.
- Worked: specified how fused seed score is used operationally:
  - select direct bucket seeds,
  - anchor explicit/implicit expansion scores,
  - fill bounded mode quotas,
  - dedupe and spill underfilled buckets,
  - enforce hard `limit`.
- Worked: captured explicit policy choice point for fact-update chains:
  - full closure vs bounded depth (user currently leaning bounded depth, e.g. 3).
- Did not work / risk: mode quota values and update-chain depth are still unresolved, so behavior can still drift across implementations.
- Open: finalize quota values by mode and finalize full-closure vs bounded-depth chain policy.
- Files touched: `insights/03-refinements/read-policy-context-pack-rrf-draft.md`, `insights/00-lab/immutable-work-log.md`.

## 2026-02-21 20:18:36 CST

- Proposed: ratify v1 read-policy pack construction and ratify write-policy extension for synchronous scenario projection construction.
- Worked: ratified read-policy seed retrieval over all atomic shellbrain kinds (`problem`, `solution`, `failed_tactic`, `fact`, `change`, optional `preference`) with lane-specific thresholds and RRF fusion.
- Worked: ratified explicit use of scores for pack assembly only (gating, ranking, spillover, scenario ranking), not as absolute truth semantics.
- Worked: ratified scenario-aware read layer:
  - derive scenario bundles from matched atomic members,
  - rank scenario bundles by matched-member evidence,
  - include bounded scenario summaries and members in final pack.
- Worked: ratified write-policy extension:
  - run `scenario_constructor(affected_ids)` synchronously in write path,
  - update derived scenario projections in same transaction as authoritative writes,
  - abort full transaction on projection failure.
- Worked: ratified bounded fact-update-chain expansion direction for read context relevance and token control (`max_update_chain_depth` tunable, suggested default `3`).
- Did not work / risk: final mode quota values and final scenario projection schema details remain open.
- Open: lock per-mode pack quotas and finalize scenario projection table naming/fields.
- Files touched: `insights/03-refinements/read-policy-context-pack-v1.md`, `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-21 20:34:42 CST

- Proposed: concretize whether/how global utility prior is used in v1 read policy.
- Worked: ratified that `global_utility` is weak and late-stage only:
  - never used for threshold gating,
  - never allowed to rescue irrelevant memories,
  - applied only as tie-breaker/near-tie nudger.
- Worked: captured reliability shrinkage by observation count:
  - `u_shrunk = utility_mean * (obs / (obs + lambda_utility))`.
- Worked: captured concrete late-stage adjustment:
  - `final_score = base_score + alpha_utility * u_shrunk`,
  - with small `alpha_utility` (suggested `0.05`) and within-bucket near-tie application.
- Did not work / risk: numeric defaults for `lambda_utility` and near-tie band are still open and can influence ranking stability if set poorly.
- Open: finalize `lambda_utility`, near-tie band width, and final `alpha_utility`.
- Files touched: `insights/03-refinements/read-policy-context-pack-v1.md`, `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-24 20:51:46 CST

- Proposed: create a single ratified-state register so "what is currently ratified" can be read in one place without re-walking all prior files.
- Worked: added `insights/05-ratified/ratified-state-register-v1.md` as a canonical digest with explicit supersession rule ("newer ratified decisions win").
- Worked: resolved current naming decisions from this conversation:
  - prefer `create` over `write` for interface creation verb,
  - keep `episodes` naming (do not rename to `work_sessions`).
- Worked: mapped known doc-drift points to newer ratified direction inside the register.
- Did not work / risk: several implementation-tuning and payload-format decisions still remain open and must still be ratified in discovery before considered locked.
- Open: canonical `episode_events.content` payload, canonical `evidence_refs.ref` format, read quota defaults, scenario projection schema/trigger boundaries, utility-prior numeric defaults, near-tie mode policy, final semantic-validation matrix publication.
- Files touched: `insights/05-ratified/ratified-state-register-v1.md`, `insights/README.md`, `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-24 20:56:05 CST

- Proposed: bring interface and DB schema cards fully in line with newer ratified naming and policy decisions.
- Worked: updated interface contract from `write` to `create`:
  - `memory.write.request` -> `memory.create.request`,
  - `op: "write"` -> `op: "create"`,
  - operation semantics/examples switched to create-language.
- Worked: made create evidence requirement explicit in JSON schema shape (`memory.evidence_refs` required with `minItems: 1`), matching ratified Write Policy v1 strict-create evidence.
- Worked: aligned storage card naming/details:
  - `memories.write_confidence` -> `memories.create_confidence`,
  - authoritative wording normalized to episodes/events/transfers,
  - episodic section title clarified as episodes as the work-session container.
- Did not work / risk: if any implementation already shipped `op: "write"` or `write_confidence`, migration/compatibility handling is still needed.
- Open: decide compatibility posture for legacy payloads/storage naming (`write` aliases and column rename migration rules) if existing implementations already depend on old names.
- Files touched: `insights/04-contracts/memory-interface-json-schemas-v1.md`, `insights/04-contracts/memory-storage-relational-schema-v1.md`, `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-24 21:10:09 CST

- Proposed: refine the semantic-validation matrix proposal to avoid over-constraining unratified behavior before implementation lock.
- Worked: accepted adjustment set for matrix finalization:
  - treat `global`-scope restriction to `preference` as pending (not hard-enforced yet),
  - do not enforce one-successor-only fact chains in v1 yet,
  - keep DB-trigger usage minimal in v1 (hard invariants only),
  - require idempotency/duplicate behavior to be explicitly specified,
  - require explicit validation-stage error contract (`schema_error`, `semantic_error`, `integrity_error`, etc.).
- Did not work / risk: if these constraints are not recorded in discovery/register, teams may still lock premature constraints into implementation.
- Open: publish the full semantic validation matrix card with exact per-op/per-kind rules and error payloads.
- Files touched: `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`, `insights/05-ratified/ratified-state-register-v1.md`.

## 2026-02-24 21:14:17 CST

- Proposed: create a dedicated implementation working-set directory so all currently concrete subsystem specs are reachable in one place.
- Worked: added `insights/06-working-set/` with one subsystem card per area:
  - agent interface,
  - write policy,
  - read policy,
  - DB schema,
  - validation rules,
  - context-pack builder,
  - plus manifest and README.
- Worked: linked the new directory from `insights/README.md` and cross-linked from ratified register.
- Did not work / risk: working-set cards are digest layers; if source cards change without sync updates, drift can reappear.
- Open: keep working-set cards synchronized with source contracts/policy cards on every new ratification.
- Files touched: `insights/06-working-set/README.md`, `insights/06-working-set/00-manifest-v1.md`, `insights/06-working-set/01-agent-interface-v1.md`, `insights/06-working-set/02-write-policy-v1.md`, `insights/06-working-set/03-read-policy-v1.md`, `insights/06-working-set/04-db-schema-v1.md`, `insights/06-working-set/05-validation-rules-v1.md`, `insights/06-working-set/06-context-pack-builder-v1.md`, `insights/README.md`, `insights/05-ratified/ratified-state-register-v1.md`, `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-25 21:45:32 CST

- Proposed: ratify formal associative structure integration across interface, write policy, read policy context-pack assembly, and DB schema without adding a separate read operation.
- Worked: locked interface pattern:
  - keep top-level `create/read/update`,
  - no `association.read`,
  - add explicit association writes via `create.links.associations[]` and `update.type = association_link`.
- Worked: locked write-policy split:
  - explicit agent-authored typed links,
  - implicit under-the-hood reinforcement channel for co-activation learning.
- Worked: locked read-policy integration point:
  - association edges are expanded inside existing explicit-association bucket alongside `problem_attempts` and `fact_updates`.
- Worked: locked storage additions:
  - `association_edges`,
  - `association_observations`,
  - `association_edge_evidence`,
  - derived dependency/dependent count views.
- Worked: synchronized ratified register + working-set cards to include associative structure as part of current implementation state.
- Did not work / risk: numeric defaults for association traversal/ranking/strength update remain open and require later tuning.
- Open: finalize association traversal defaults (`max_association_depth`, fanout, min strength), relation/source weights, and implicit-channel promotion/demotion thresholds.
- Files touched: `insights/04-contracts/memory-interface-json-schemas-v1.md`, `insights/04-contracts/memory-storage-relational-schema-v1.md`, `insights/03-refinements/read-policy-context-pack-v1.md`, `insights/06-working-set/00-manifest-v1.md`, `insights/06-working-set/01-agent-interface-v1.md`, `insights/06-working-set/02-write-policy-v1.md`, `insights/06-working-set/03-read-policy-v1.md`, `insights/06-working-set/04-db-schema-v1.md`, `insights/06-working-set/05-validation-rules-v1.md`, `insights/06-working-set/06-context-pack-builder-v1.md`, `insights/05-ratified/ratified-state-register-v1.md`, `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-25 22:00:15 CST

- Proposed: ratify ergonomic agent-interface simplification so agent calls stay minimal while strict contracts remain deterministic.
- Worked: locked two-layer interface shape:
  - strict internal contract (full payload + deterministic validation),
  - ergonomic CLI adapter that hydrates contextual defaults before strict validation.
- Worked: locked explicit-vs-inferred rule:
  - explicit agent-provided values override inferred defaults.
- Worked: locked adapter inference defaults:
  - infer `repo_id` from cwd/repo resolver,
  - infer `read` defaults (mode/include_global/limit/expand knobs) from policy config,
  - infer `create` defaults (`scope`, `confidence`) when omitted.
- Worked: locked evidence guard:
  - auto-evidence attachment is allowed only when provenance is unambiguous; otherwise request must provide explicit evidence refs.
- Worked: clarified preferred explicit relation path:
  - use typed `links.associations[]` for explicit agent-authored formal relations.
- Did not work / risk: response/error schema and full semantic matrix publication remain open, so error handling details can still drift across implementations.
- Open: publish final response/error schemas and final semantic validation matrix with adapter hydration checks codified.
- Files touched: `insights/04-contracts/memory-interface-json-schemas-v1.md`, `insights/06-working-set/01-agent-interface-v1.md`, `insights/06-working-set/02-write-policy-v1.md`, `insights/06-working-set/05-validation-rules-v1.md`, `insights/06-working-set/06-context-pack-builder-v1.md`, `insights/05-ratified/ratified-state-register-v1.md`, `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-25 22:04:35 CST

- Proposed: ratify implementation tech stack so architecture/build work can begin without stack ambiguity.
- Worked: locked stack direction:
  - Python 3.12,
  - CLI-first interface,
  - JSON in/out payload style for agent interaction.
- Worked: locked storage/retrieval substrate:
  - PostgreSQL 16,
  - pgvector for embeddings,
  - PostgreSQL FTS for lexical retrieval.
- Worked: locked data/migration/validation/testing tooling:
  - SQLAlchemy Core,
  - Alembic,
  - Pydantic v2,
  - pytest.
- Worked: locked execution shape:
  - core shellbrain engine package + thin CLI hydration adapter.
- Worked: recorded stack in working-set and ratified register.
- Did not work / risk: final CLI command naming and output envelope schema still open; background worker strategy beyond in-process jobs still open.
- Open: finalize CLI command map/output envelope and define criteria for escalating to queue-backed worker model.
- Files touched: `insights/06-working-set/07-tech-stack-v1.md`, `insights/06-working-set/README.md`, `insights/06-working-set/00-manifest-v1.md`, `insights/05-ratified/ratified-state-register-v1.md`, `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-02-25 22:18:39 CST

- Proposed: ratify local PostgreSQL durability requirements so data survives container deletion and Docker uninstall.
- Worked: locked operational durability property for local deployment:
  - PostgreSQL data directory must be host bind-mounted (outside container-only filesystem state),
  - container lifecycle operations (delete/recreate) must not be data-destructive.
- Worked: locked portability baseline:
  - logical backup/export path (`pg_dump`/`pg_dumpall`) is part of v1 expectations for easy transfer across machines/runtimes.
- Worked: reconciled stale storage wording so active contract cards match ratified PostgreSQL substrate:
  - `06-working-set/04-db-schema-v1.md` now states PostgreSQL 16 + pgvector + PostgreSQL FTS,
  - `04-contracts/memory-storage-relational-schema-v1.md` now carries PostgreSQL-oriented schema contract wording.
- Worked: synchronized ratified register + working-set tech stack card with the durability/portability policy.
- Did not work / risk: if host bind-mount path is deleted by user/OS, durability is still lost; backup scheduling/retention policy is not yet ratified.
- Open: define concrete default host-path conventions and backup cadence/retention policy.
- Files touched: `insights/04-contracts/memory-storage-relational-schema-v1.md`, `insights/06-working-set/04-db-schema-v1.md`, `insights/06-working-set/07-tech-stack-v1.md`, `insights/05-ratified/ratified-state-register-v1.md`, `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-03-11 16:20:10 PDT

- Proposed: simplify read-policy ranking by removing the planned utility-based near-tie adjustment.
- Worked: superseded the earlier utility-prior read-ranking idea and documented that choice as over-engineering for v1.
- Worked: clarified that online read ranking remains driven by retrieval relevance, RRF fusion, expansion scoring, and deterministic pack assembly only.
- Worked: preserved `global_utility` as optional historical metadata for possible offline analysis or future non-ranking uses.
- Did not work / risk: future product surfaces that want to expose utility will need a separate ratified purpose and should not silently re-enter online ranking.
- Open: finalize pack quotas, expansion/ranking knobs, update-chain depth defaults, and scenario projection boundaries.
- Files touched: `insights/03-refinements/read-policy-context-pack-v1.md`, `insights/06-working-set/03-read-policy-v1.md`, `insights/05-ratified/ratified-state-register-v1.md`, `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.

## 2026-03-12 22:42:00 PDT

- Proposed: verify whether Codex desktop and Claude Code desktop sessions are actually persisted locally in a way that can power passive episodic ingestion.
- Worked: proved Codex stores machine-readable per-thread rollout JSONL files under `~/.codex/sessions/.../rollout-<timestamp>-<thread-id>.jsonl`.
- Worked: proved Claude Code stores session metadata under `~/Library/Application Support/Claude/claude-code-sessions/.../local_<session-id>.json` and transcript JSONL separately under `~/.claude/projects/<cwd-encoded>/<cliSessionId>.jsonl`.
- Worked: proved Claude's own app log records transcript load counts, which gives an additional local confirmation/debug surface.
- Worked: established that passive episodes are practical for Codex and Claude Code without asking the main agent to log every turn manually.
- Did not work / risk: ordinary non-Code Claude desktop chats are still not proven to expose a comparable local transcript file.
- Open: define the canonical imported `episode_events.content` payload and canonical host-event evidence-ref format.
- Files touched: `insights/00-lab/immutable-work-log.md`, `insights/discovery.md`.
