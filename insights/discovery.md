# Discovery Log

Chronological, append-only record of how memory-system ideas evolved.

## Update Rule

When a new memory-design idea is discussed:
- First append raw notes to `00-lab/immutable-work-log.md`.
- Then append a distilled dated entry to `discovery.md` with:
- What changed.
- Why it changed.
- Which files were updated.
- What remains open.

## 2026-02-14 - Foundation Baseline

Conversation established the baseline architecture captured in:
- `01-foundation/summary.md`
- `01-foundation/architecture-insights.md`
- `01-foundation/memory-ontology.md`
- `01-foundation/memory-creation-and-categorization.md`
- `01-foundation/storage-layer.md`

Key outcomes:
- Interface boundary set to `read`, `write`, `dispute`.
- Scope simplified to repo + global only (no domain layer).
- Retrieval pipeline set to scope -> relevance -> association -> threshold -> selection.
- Storage anchored on SQLite with immutable event log authority and rebuildable projections.
- Principle set to precision over recall, including "empty is correct" when confidence is low.

## 2026-02-18 - Outside-In Breakthrough Pass

Raw ideation captured in:
- `02-breakthrough/breakthrough-raw.md`

Structured reformulation captured in:
- `02-breakthrough/breakthrough-structured.md`

Key developments:
- Retrieval clarified as two-lane recall: semantic association lane + bounded keyword lane, then dedupe/merge.
- Strong emphasis that codebase state is immediate ground truth and memory is advisory utility.
- Session-end write flow clarified with duplicate checks, contradiction handling, and optional autonomous storage mode.
- Problem-solution linkage became explicit: retrieval and expansion operate over linked memories.

## 2026-02-18 - Failed Tactics Promoted To First-Class Memory

Design extension incorporated into structured and core docs:
- `02-breakthrough/breakthrough-raw.md`
- `02-breakthrough/breakthrough-structured.md`
- `01-foundation/architecture-insights.md`
- `01-foundation/memory-ontology.md`
- `01-foundation/memory-creation-and-categorization.md`
- `01-foundation/storage-layer.md`
- `01-foundation/summary.md`

Key developments:
- Failed attempts are no longer implicit only in episode text.
- Experiential memory is now modeled as linked `problems`, `solutions`, and `failed_tactics`.
- Immutable episode logs remain evidence, while normalized linked records power retrieval.

## 2026-02-18 - Utility vs Truth Framing (User Verbatim Points)

Verbatim source notes recorded in:
- `03-refinements/user-three-points-verbatim.md`

Synthesis of the three-point direction:
- Distinguish instantaneous truth (current code state) from historical memory utility.
- Track memory usefulness relative to specific problem contexts, not only global vote totals.
- Treat changes in utility and changes in truth as separable update streams over immutable history.

## 2026-02-18 - Policy Concretization: Overfitting, Weak Priors, and Chain Classes

Detail note added:
- `03-refinements/policy-overfitting-bayesian-chains.md`

What changed:
- Adopted a concrete policy against stale-memory overfitting: memory is optional utility, and current workspace/code observation is the instantaneous truth source.
- Confirmed global utility can exist as a weak prior and is best treated as computed-after-the-fact rather than primary.
- Recognized a shared Bayesian flavor between utility and truth updates:
  - utility as a belief updated by context-specific outcomes,
  - truth as a belief in `[0,1]` updated by supporting/contradicting evidence.
- Clarified "chain idea" now has two distinct forms:
  - implicit association chain via semantic/vector similarity,
  - explicit association chain via formal deterministic links (for example, base memory -> update memories).

Why it changed:
- To keep the system aligned with optionality and avoid rigid deterministic handling that drifts from the original design intent.
- To preserve immutable history while still enabling "what is useful now" and "what is likely true now" behavior.

What remains open:
- Whether to formally implement Bayesian update math or keep the same concept with lightweight heuristics.
- Exact weighting mechanics for weak global priors vs problem-specific evidence.
- Prompt wording and retrieval behavior that enforce explicit-association traversal without over-constraining exploration.

## 2026-02-18 - Dogfooding Workflow: Raw Log + Discovery Abstraction

What changed:
- Added a dedicated immutable raw-note log: `00-lab/immutable-work-log.md`.
- Clarified that `discovery.md` is an abstraction/extraction layer over raw notes.
- Updated structure guidance so agents should record notes automatically, without waiting for explicit prompts.

Why it changed:
- To dogfood the memory design process while designing it.
- To preserve intermediate reasoning and dead ends, not only polished summaries.

What remains open:
- Cadence for abstraction from raw log into discovery (every significant turn vs milestone-only).

## 2026-02-18 - Provisional Decision: Heuristics First, Bayesian-Compatible Later

What changed:
- Set abstraction cadence: raw log updates every ideation turn; discovery updates when there is a decision, policy shift, or a coherent new open-question cluster.
- Took a provisional stance on update mechanics: lightweight heuristics first for truth/utility updates, with Bayesian compatibility preserved for later.

Why it changed:
- Current evidence volume is low, so full Bayesian machinery now risks complexity before signal quality justifies it.
- A heuristic-first path keeps momentum while still preserving the conceptual Bayesian framing already recognized in this project.

What remains open:
- Graduation criteria from heuristic to Bayesian updates (for example, observation count, calibration error, or drift frequency thresholds).
- Exact heuristic forms for truth update and utility update in v1.

## 2026-02-18 - Ratified Direction: JSON Contracts and Evidence Strictness Split

What changed:
- Ratified interface direction: use a clean scoped memory API/tool surface with JSON request/response contracts.
- Ratified evidence policy split:
  - truth updates require supporting evidence references,
  - utility updates allow optional evidence.
- Ratified update style: keep lightweight heuristic updates in `[0,1]` now, while preserving a path to Bayesian formalization later.

Why it changed:
- JSON contracts improve reliability for LLM interaction without over-constraining reasoning behavior.
- Strict truth evidence protects against drift; optional utility evidence avoids heavy attribution overhead in low-friction workflows.
- Heuristic-first keeps momentum during ideation and low-volume operation.

What remains open:
- Exact scoped API verbs and payload fields.
- Fallback behavior when utility updates have no evidence (for example, smaller deltas or deferred persistence).
- Concrete v1 heuristic update function details.

## 2026-02-18 - Ratified Interface Semantics: `read`, `write`, `update` + Validation Layer

What changed:
- Ratified interface operation split:
  - `read`: retrieval only.
  - `write`: creates immutable memory records.
  - `update`: adjusts dynamic values on existing memory IDs (`truth`, `utility`) in `[0,1]`.
- Ratified interpretation for "update memories":
  - Statements like "X changed in the codebase and invalidates Y" are new memories and therefore use `write` (kind `change`), not `update`.
- Ratified memory kind set for v1 interface contracts:
  - `problem`, `solution`, `failed_tactic`, `fact`, `preference`, `change`.
- Ratified categorization rule:
  - The writing agent provides explicit `scope` and `kind` (no ambiguous `auto` categorization in payloads).
- Ratified validation placement:
  - A validation layer sits directly under the interface.
  - It performs schema validation (JSON shape/types/required fields) and semantic validation (domain rules such as evidence requirements).

Why it changed:
- This split resolves ambiguity between immutable memory creation and mutable value adjustment.
- It preserves append-only memory history while still allowing current utility/truth projections to evolve.
- It makes agent behavior parseable and auditable without over-constraining reasoning.

What remains open:
- Exact canonical JSON payload definitions and required-field matrix by operation.
- Final semantic validation rules by memory kind (for example, required links for `solution` and `failed_tactic`).

## 2026-02-18 - Ratified Card: Exact JSON Schemas for `read` / `write` / `update`

Card added:
- `04-contracts/memory-interface-json-schemas-v1.md`

What changed:
- Recorded the exact approved JSON schemas verbatim for:
  - `memory.read.request`
  - `memory.write.request`
  - `memory.update.request`
- Confirmed operation semantics in the card:
  - `write` creates immutable memories,
  - `update` adjusts dynamic values,
  - \"update memory\" statements are `write` with `kind: change`.
- Confirmed validation placement directly under the interface (schema + semantic validation).

Why it changed:
- To make the interface concrete and implementation-ready without ambiguity.
- To preserve the approved contract in a single source-of-truth card that discovery can link to.

What remains open:
- Final semantic validation matrix by kind/field requirement (especially linking requirements and edge-case rules).

## 2026-02-18 - Retrospective Gap Fill: Lightweight Update Policy + Late Interface Clarifications

Card added:
- `03-refinements/lightweight-update-policy-and-interface-clarifications.md`

What changed:
- Captured the ratified anti-rigidity principle explicitly: avoid fixed update taxonomies and keep reasoning freeform while contracts stay minimal.
- Captured the ratified lightweight update shape explicitly: dynamic `truth` and `utility` in `[0,1]`, confidence/rationale/refs at reflection time, bounded deterministic adjustment (not pure intuition).
- Captured attribution reality for utility updates: optional evidence is acceptable, with weaker/deferred impact when evidence is missing.
- Captured late interface clarifications in one place:
  - single `update` op with `mode: "dry_run" | "commit"` rather than separate `propose_update`/`apply_update`,
  - explicit `scope` + `kind` in `write` (no `auto`),
  - `read.kinds` as include filter.

Why it changed:
- These points were discussed and approved in the thread but were spread across transcript turns and not represented as a dedicated refinement note.

What remains open:
- Exact numerical update-function parameters (caps/damping/skip thresholds).
- Final fallback policy for utility updates with no evidence (small delta vs defer).

## 2026-02-18 - Ratified Card: Concrete Relational Storage Schema v1 (No Truth Score)

Card added:
- `04-contracts/memory-storage-relational-schema-v1.md`

What changed:
- Ratified relational (SQLite) storage for v1, with graph semantics represented through explicit link tables rather than a graph database.
- Ratified top-level memory kinds as stored immutable records:
  - `problem`, `solution`, `failed_tactic`, `fact`, `preference`, `change`.
- Ratified direct experiential linkage with:
  - `problem_attempts(problem_id, attempt_id, role)` where role is `solution` or `failed_tactic`.
- Ratified fact-change modeling as immutable chain links:
  - `old_fact_id + change_id -> new_fact_id` via `fact_updates`.
- Ratified current-fact representation as a derived snapshot view:
  - `current_fact_snapshot`.
- Ratified utility storage as contextual observations:
  - `utility_observations(memory_id, problem_id, vote in [-1,1])`.
- Ratified removal of mutable truth/accuracy score in v1.

Why it changed:
- To make data storage as concrete as the already-approved interface schemas.
- To preserve provenance and append-only history while keeping the model simple and implementation-ready.
- To avoid premature complexity from truth-scoring machinery when fact updates already encode truth evolution explicitly.

What remains open:
- Whether scenario-level metadata should reintroduce a scenario container later.
- Whether semantic invariants should also be enforced with DB triggers in addition to interface semantic validation.

## 2026-02-19 - Ratified Naming Split: Interface Verbs vs Policy Layers

What changed:
- Ratified policy-layer names:
  - `Read Policy` for retrieval behavior.
  - `Write Policy` for create/update acceptance, validation, and DB side effects.
- Ratified interface-verb framing:
  - `create`, `read`, `update` as the conceptual external verbs.
- Ratified routing between layers:
  - `read` routes to Read Policy.
  - `create` and `update` route to Write Policy.
- Ratified that `update` remains a distinct interface verb (rather than collapsing everything into create/write), even though it is write-path behavior internally.

Why it changed:
- To reduce naming ambiguity between policy and API layers.
- To keep the interface clear for agents while preserving a strict internal write-path rule system.
- To avoid turning create/write into a catch-all operation with overloaded semantics.

Files updated:
- `insights/00-lab/immutable-work-log.md`
- `insights/discovery.md`

What remains open:
- Whether to rename wire-level `op: "write"` to `op: "create"` in the interface contract, or support `create/write` aliasing for a migration window.

## 2026-02-19 - Ratified Write Policy v1 (Create/Update Determinism)

What changed:
- Ratified policy routing:
  - `read` -> Read Policy.
  - `create` and `update` -> Write Policy.
- Ratified role split:
  - LLM provides judgment and intent (`kind`, `scope`, statement text, links, evidence refs).
  - Write Policy performs deterministic acceptance/rejection and DB side effects.
- Ratified ordered validity gates for write-path operations:
  - schema validity,
  - semantic write-policy validity,
  - DB integrity validity.
- Ratified atomicity:
  - accepted create/update requests execute in one transaction;
  - any failure aborts all side effects.
- Ratified strict evidence requirement for create in v1:
  - `evidence_refs >= 1` for all create kinds (`problem`, `solution`, `failed_tactic`, `fact`, `preference`, `change`).
  - for preferences, evidence may be user-message/session references (not necessarily code references).
- Ratified deterministic side-effect mapping:
  - `create(problem|fact|preference|change)` -> `memories` (+ evidence link rows),
  - `create(solution|failed_tactic)` -> `memories` + `problem_attempts` (+ evidence link rows),
  - `update(archive_state)` -> `memories.archived`,
  - `update(utility_vote)` -> `utility_observations`,
  - `update(fact_update_link)` -> `fact_updates` (with kind checks).

Why it changed:
- To close the implementation gap between schema definitions and executable behavior.
- To make write-path behavior unambiguous and auditable for implementers.
- To preserve LLM judgment while enforcing deterministic storage rules.

Files updated:
- `insights/00-lab/immutable-work-log.md`
- `insights/discovery.md`

What remains open:
- Concrete episodic ongoing log contract for source content storage (the target that `evidence_refs.ref` points to).
- Canonical `evidence_ref` pointer format for episode/user/tool/file spans.
- Whether wire-level `op: "write"` should be renamed to `op: "create"` or aliased during migration.

## 2026-02-19 - Ratified Episodic Log Direction v1 (Single Source + Minimal Event Model)

What changed:
- Ratified episodic storage authority:
  - SQLite episodic tables are canonical.
  - Any append-only text log is optional export only (non-authoritative).
- Ratified minimal episodic schema direction:
  - `episodes(id, repo_id, started_at, ended_at)`
  - `episode_events(id, episode_id, seq, content, created_at)`
- Ratified event granularity:
  - one row per individual message/tool call,
  - not one row per full turn blob.
- Ratified v1 evidence targeting:
  - `evidence_refs.ref` points to whole event IDs (`episode_event_id`).
  - span-level pointers (`event_id:start:end`) are deferred.
- Ratified write-path ergonomics:
  - runtime auto-captures episodic events,
  - LLM references generated event IDs in `evidence_refs` during create/update operations.

Why it changed:
- To eliminate dual-source drift between DB and ad-hoc append logs.
- To keep evidence links stable, auditable, and easy to dereference.
- To keep v1 schema minimal while preserving fine-grained evidence precision via per-event rows.

Files updated:
- `insights/00-lab/immutable-work-log.md`
- `insights/discovery.md`

What remains open:
- Canonical payload format for `episode_events.content` in v1.
- Canonical string format for `evidence_refs.ref` (for example, `event:<id>` vs plain `<id>`).
- Whether any minimal event metadata should be mandatory in `content` (for example, source role or tool name) without introducing rigid event-type enums.

## 2026-02-21 - Ratified Episodic Session Extensions v1 (Work Session Metadata + Transfer Log)

What changed:
- Ratified that each `episodes` row is the canonical work-session container (for example, one chat thread or closely related problem cluster).
- Extended `episodes` metadata to support session-level tracing and lifecycle:
  - `thread_id`, `title`, `objective`, `status`, `started_at`, `ended_at`.
- Extended `episode_events` to strengthen per-session immutability/ordering:
  - one event per message/tool call,
  - explicit `source`,
  - unique `(episode_id, seq)` ordering.
- Added immutable cross-session handoff tracking with:
  - `session_transfers(from_episode_id, to_episode_id, event_id, transfer_kind, rationale, transferred_by, created_at)`.
- Kept the prior storage stance intact:
  - one canonical SQLite episodic store,
  - session partitioning by ID,
  - no markdown file as authoritative log.

Why it changed:
- To preserve strict immutable history while preventing unrelated tasks from blending into one undifferentiated episodic stream.
- To support explicit handoff provenance when context/messages are transferred between work sessions.
- To keep the model implementation-ready without introducing per-session database/file fragmentation.

Files updated:
- `insights/04-contracts/memory-storage-relational-schema-v1.md`
- `insights/00-lab/immutable-work-log.md`
- `insights/discovery.md`

What remains open:
- Canonical payload shape for `episode_events.content` in v1.
- Canonical `evidence_refs.ref` string format for event pointers.
- Whether to keep DB naming as `episodes` long-term or rename to `work_sessions` with compatibility aliases.

## 2026-02-21 - Ratified Read Policy v1 (RRF + Scenario Lift) and Write Policy Scenario Constructor

Card added:
- `03-refinements/read-policy-context-pack-v1.md`

What changed:
- Ratified read-policy seed retrieval over all atomic memory kinds:
  - `problem`, `solution`, `failed_tactic`, `fact`, `change` (and optionally `preference`).
- Ratified dual-lane seed retrieval with lane-specific thresholds and rank-fusion:
  - semantic lane + keyword lane,
  - RRF-based seed ranking (instead of raw-score max across unlike score scales).
- Ratified concrete meaning/use of scores in read path:
  - threshold gating,
  - direct-seed ranking,
  - explicit/implicit expansion ranking,
  - spillover ordering,
  - scenario bundle ranking.
- Ratified scenario-aware context-pack assembly:
  - derive scenario bundles from matched atomic memories,
  - rank scenarios from matched-member evidence,
  - include bounded scenario summaries + bounded member selections in final pack.
- Ratified bounded fact-update-chain expansion direction for retrieval:
  - `max_update_chain_depth` is tunable (default suggestion: `3`) for context relevance/token control.
- Ratified write-policy extension for scenario construction:
  - run `scenario_constructor(affected_ids)` synchronously in write path,
  - update derived scenario projections in same transaction as authoritative writes,
  - abort full transaction if projection update fails.

Why it changed:
- Read-policy naming/routing had been ratified, but concrete context-pack inclusion mechanics were still underspecified.
- Scenario was recognized as a useful abstraction for both humans and LLMs, requiring deterministic construction and storage semantics.
- A synchronous projection step keeps scenario abstraction available immediately after writes while preserving transactional consistency.

Files updated:
- `insights/03-refinements/read-policy-context-pack-v1.md`
- `insights/00-lab/immutable-work-log.md`
- `insights/discovery.md`

What remains open:
- Final per-mode quota values for `N_direct`, `N_explicit`, `N_implicit`, `N_scenario`.
- Final default for `max_update_chain_depth` (currently suggested `3`).
- Final scenario projection schema names/fields and constructor trigger boundaries.

## 2026-02-21 - Ratified Global Utility Prior Use in Read Policy v1

Card updated:
- `03-refinements/read-policy-context-pack-v1.md`

What changed:
- Ratified that `global_utility` is used in v1 as a weak prior only:
  - never for threshold gating,
  - never to rescue irrelevant memories,
  - only as late-stage tie-breaker / near-tie nudger.
- Ratified reliability shrinkage by observation count:
  - `u_shrunk = utility_mean * (obs / (obs + lambda_utility))`.
- Ratified late-stage score adjustment shape:
  - `final_score = base_score + alpha_utility * u_shrunk`.
- Ratified safety constraints:
  - `alpha_utility` remains small (suggested `0.05`),
  - applied within bucket and near-tie bands rather than across broad score gaps.

Why it changed:
- To concretize prior discussions that global utility should be a weak computed prior rather than a primary retrieval signal.
- To avoid sparse-data overfitting while still using historical helpfulness when resolving close candidate decisions.
- To align retrieval behavior with the existing architecture principle that relevance leads and memory utility is advisory.

Files updated:
- `insights/03-refinements/read-policy-context-pack-v1.md`
- `insights/00-lab/immutable-work-log.md`
- `insights/discovery.md`

What remains open:
- Final defaults for `lambda_utility`, near-tie band width, and `alpha_utility`.
- Whether near-tie behavior is mode-specific (`ambient` vs `targeted`) or shared.

## 2026-02-25 - Ratified State Register v1 + Naming Locks (`create`, `episodes`)

What changed:
- Added a canonical ratified-state digest:
  - `05-ratified/ratified-state-register-v1.md`
- Ratified supersession rule for evolving docs:
  - newer ratified decisions override older conflicting language.
- Ratified naming lock from this conversation:
  - prefer `create` over `write` for the interface creation verb.
- Ratified naming lock from this conversation:
  - keep `episodes` naming (do not rename to `work_sessions`).
- Updated `insights/README.md` structure and discovery pointers to include the new ratified-state register.

Why it changed:
- To remove recurring ambiguity caused by timeline evolution and mixed-era terminology.
- To provide one stable "what is ratified now" source so implementation can proceed without re-resolving prior drift each time.

Files updated:
- `insights/05-ratified/ratified-state-register-v1.md`
- `insights/README.md`
- `insights/00-lab/immutable-work-log.md`
- `insights/discovery.md`

What remains open:
- Canonical payload shape for `episode_events.content`.
- Canonical string format for `evidence_refs.ref`.
- Final per-mode context-pack quotas (`N_direct`, `N_explicit`, `N_implicit`, `N_scenario`).
- Final default for `max_update_chain_depth`.
- Final scenario projection schema names/fields and constructor trigger boundaries.
- Final defaults for `lambda_utility`, near-tie band width, and final `alpha_utility`.
- Whether near-tie behavior is mode-specific (`ambient` vs `targeted`) or shared.
- Final published semantic validation matrix by operation/kind and any DB-trigger enforcement expansion.

## 2026-02-25 - Contracts Aligned To Ratified Naming (`create`, `episodes`) and Strict Create Evidence

What changed:
- Updated interface contract card to use ratified creation verb naming end-to-end:
  - `memory.write.request` -> `memory.create.request`,
  - `op: "write"` -> `op: "create"`,
  - operation semantics/examples rewritten to create-language.
- Updated create-schema evidence requirements to match ratified Write Policy v1:
  - `memory.evidence_refs` is required and `minItems = 1` for create requests.
- Updated storage schema card naming alignment:
  - `memories.write_confidence` -> `memories.create_confidence`,
  - authoritative wording normalized to episodes/events/transfers,
  - episodic section wording clarified around `episodes` as the session container.

Why it changed:
- To remove remaining contract drift after naming locks were ratified.
- To keep interface and storage cards implementation-ready under one consistent vocabulary.
- To make strict create evidence policy explicit at schema level rather than only semantic-policy prose.

Files updated:
- `insights/04-contracts/memory-interface-json-schemas-v1.md`
- `insights/04-contracts/memory-storage-relational-schema-v1.md`
- `insights/00-lab/immutable-work-log.md`
- `insights/discovery.md`

What remains open:
- Canonical payload shape for `episode_events.content`.
- Canonical string format for `evidence_refs.ref`.
- Final per-mode context-pack quotas (`N_direct`, `N_explicit`, `N_implicit`, `N_scenario`).
- Final default for `max_update_chain_depth`.
- Final scenario projection schema names/fields and constructor trigger boundaries.
- Final defaults for `lambda_utility`, near-tie band width, and final `alpha_utility`.
- Whether near-tie behavior is mode-specific (`ambient` vs `targeted`) or shared.
- Final published semantic validation matrix by operation/kind and any DB-trigger enforcement expansion.
- Compatibility policy if any implementation already depends on legacy names (`op: "write"`, `write_confidence`).

## 2026-02-25 - Ratified Refinements For Semantic Validation Matrix Lock

What changed:
- Ratified pre-lock constraints for the upcoming semantic validation matrix:
  - `global` scope restriction to `preference` is not yet hard-enforced; keep as pending policy.
  - do not enforce one-successor-only fact chain behavior in v1 (branching policy remains open).
  - keep DB triggers minimal in v1; reserve them for hard integrity invariants.
  - require explicit idempotency/duplicate handling policy in the validation matrix.
  - require explicit validation-stage error contract (for example `schema_error`, `semantic_error`, `integrity_error`, `not_found`, `conflict`).

Why it changed:
- To prevent premature constraints from being mistaken as ratified policy.
- To keep implementation deterministic while preserving intentionally open design decisions.
- To ensure the semantic matrix captures behavior and error semantics, not only acceptance checks.

Files updated:
- `insights/00-lab/immutable-work-log.md`
- `insights/discovery.md`
- `insights/05-ratified/ratified-state-register-v1.md`

What remains open:
- Publish the full semantic validation matrix card with exact per-operation/per-kind rules and error payload schemas.
- Canonical payload shape for `episode_events.content`.
- Canonical string format for `evidence_refs.ref`.
- Final per-mode context-pack quotas (`N_direct`, `N_explicit`, `N_implicit`, `N_scenario`).
- Final default for `max_update_chain_depth`.
- Final scenario projection schema names/fields and constructor trigger boundaries.
- Final defaults for `lambda_utility`, near-tie band width, and final `alpha_utility`.
- Whether near-tie behavior is mode-specific (`ambient` vs `targeted`) or shared.
- Compatibility policy if any implementation already depends on legacy names (`op: "write"`, `write_confidence`).

## 2026-02-25 - Added Implementation Working Set Directory (`06-working-set`)

What changed:
- Added a dedicated implementation-facing directory:
  - `06-working-set/`
- Added subsystem cards for the current working set:
  - `01-agent-interface-v1.md`
  - `02-write-policy-v1.md`
  - `03-read-policy-v1.md`
  - `04-db-schema-v1.md`
  - `05-validation-rules-v1.md`
  - `06-context-pack-builder-v1.md`
- Added supporting files:
  - `06-working-set/README.md`
  - `06-working-set/00-manifest-v1.md`
- Updated `insights/README.md` to include this directory in canonical structure.
- Cross-linked ratified register to the implementation pack.

Why it changed:
- To provide one stable "working set" location for implementation handoff and execution.
- To reduce navigation overhead across historical stages while preserving the full chronology in discovery.

Files updated:
- `insights/06-working-set/README.md`
- `insights/06-working-set/00-manifest-v1.md`
- `insights/06-working-set/01-agent-interface-v1.md`
- `insights/06-working-set/02-write-policy-v1.md`
- `insights/06-working-set/03-read-policy-v1.md`
- `insights/06-working-set/04-db-schema-v1.md`
- `insights/06-working-set/05-validation-rules-v1.md`
- `insights/06-working-set/06-context-pack-builder-v1.md`
- `insights/README.md`
- `insights/05-ratified/ratified-state-register-v1.md`
- `insights/00-lab/immutable-work-log.md`
- `insights/discovery.md`

What remains open:
- Publish the full semantic validation matrix card with exact per-operation/per-kind rules and error payload schemas.
- Canonical payload shape for `episode_events.content`.
- Canonical string format for `evidence_refs.ref`.
- Final per-mode context-pack quotas (`N_direct`, `N_explicit`, `N_implicit`, `N_scenario`).
- Final default for `max_update_chain_depth`.
- Final scenario projection schema names/fields and constructor trigger boundaries.
- Final defaults for `lambda_utility`, near-tie band width, and final `alpha_utility`.
- Whether near-tie behavior is mode-specific (`ambient` vs `targeted`) or shared.
- Compatibility policy if any implementation already depends on legacy names (`op: "write"`, `write_confidence`).
