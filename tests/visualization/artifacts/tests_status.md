# Tests Status

Generated: 2026-03-18 23:40:58 PDT

## Summary

- Total: 242
- Passed: 83
- Failed: 0
- Skipped/Not Run: 159

# Config Tests

- ✅ repo context resolution should infer repo_id from the resolved repo_root basename.
- ✅ repo context resolution should preserve an explicit repo_id override.
- ✅ top-level help should explain the Shellbrain mental model and session protocol.
- ✅ read help should teach focused querying and pack structure.
- ✅ events help should explain fresh episodic evidence lookup.
- ✅ create help should explain memory-kind choice and attempt-link rules.
- ✅ update help should expose the supported update types.
- ✅ admin help should always include one minimal example.
- ✅ admin migrate help should always include one minimal example.
- ✅ admin install-claude-hook help should explain the trusted Claude setup step.
- ✅ admin session-state help should expose inspect, clear, and gc management paths.
- ✅ repo-targeting flags should work before the operational subcommand.
- ✅ repo-targeting flags should also work after the operational subcommand.
- ✅ --no-sync should suppress repo-local poller startup after a successful command.
- ✅ admin migrate should delegate to the packaged migration runner.
- ✅ explicit repo-root overrides should fail fast when the directory does not exist.
- ⚪ not run yaml config provider should always expose separate create and update policy sections.
- ⚪ not run The longer onboarding surfaces should teach the same Shellbrain mental model.
- ⚪ not run Top-level CLI help should match the condensed taught workflow.
- ⚪ not run The reusable shellbrain skill should include Codex UI metadata.
- ✅ editable installs should expose the shellbrain console script outside this repository.
- ✅ git-url installs should expose the shellbrain console script outside this repository.
- ✅ installed-package admin migrate should initialize an empty database from packaged artifacts.
- ⚪ not run read policy should always resolve missing read knobs from config.
- ⚪ not run read policy should always merge partial expand over config defaults.
- ⚪ not run db boot should always resolve the runtime-configured dsn env.
- ⚪ not run runtime yaml should always define database cli and embedding sections.
- ⚪ not run seed retrieval should always apply configured semantic and keyword thresholds.
- ⚪ not run update policy should always expose its configured gate list.

# Create Tests

## Validation

### Link Rules

- ⚪ not run solution memories should always include links.problem_id.
- ⚪ not run failed_tactic memories should always include links.problem_id.
- ⚪ not run non-attempt kinds should always reject links.problem_id.
- ⚪ not run create association lists should always reject duplicate target+relation pairs.

### Reference Checks

- ⚪ not run create should always reject problem references that do not exist.
- ⚪ not run create should always reject problem references outside repo visibility.
- ⚪ not run create should always require links.problem_id to reference a problem memory.
- ⚪ not run create should always reject association targets outside repo visibility.
- ⚪ not run create should always reject evidence refs that do not resolve to stored episode events.
- ⚪ not run create should always reject evidence refs that belong to another repo's episode.

### Request Shape

- ⚪ not run create requests should always reject unknown fields.
- ⚪ not run create requests should always enforce unique evidence refs.
- ⚪ not run create requests should always require at least one evidence ref.
- ⚪ not run create requests should always reject op/repo_id at the agent interface.
- ⚪ not run create hydration should always infer configured scope when omitted.
- ⚪ not run create hydration should always preserve explicit scope over configured defaults.

## Execution

### Association Records

- ⚪ not run create with associations should always persist association_edge and association_observation rows.

### Effect Ordering

- ⚪ not run create plans should always preserve deterministic effect ordering by operation type.

### Embeddings

- ⚪ not run create should always persist a memory_embedding row in PostgreSQL when real embeddings are enabled.
- ⚪ not run create should always persist one memory_embedding row for the new memory.
- ⚪ not run local embedding providers should always return embeddings when sentence-transformers is available.
- ⚪ not run local embedding providers should always fail fast when sentence-transformers is unavailable.

### Evidence Links

- ⚪ not run create should always attach each evidence ref exactly once in memory_evidence.
- ⚪ not run create with associations should always link evidence refs in association_edge_evidence.

### Failure Handling

- ⚪ not run validation failures should always write nothing.
- ⚪ not run embedding failures should always write nothing.
- ⚪ not run mid-write side-effect failures should always roll back all prior side effects.

### Memory Records

- ⚪ not run create(problem) should always persist one shellbrain row and no problem_attempt row.
- ⚪ not run create(solution) should always persist one problem_attempt row with role solution.
- ⚪ not run create(failed_tactic) should always persist one problem_attempt row with role failed_tactic.

# Episodes Tests

## Validation

### Normalization

- ✅ codex parsing should always normalize user and assistant messages into the common event shape.
- ✅ claude code parsing should always normalize user and assistant messages into the common event shape.
- ✅ episode parsing should always keep meaningful tool results and drop noisy tool chatter.
- ✅ episode parsing should always skip unknown transcript lines without failing normalization.

### Source Discovery

- ⚪ not run codex source resolution should always find a rollout transcript from a thread id.
- ⚪ not run claude code source resolution should always find a transcript from local session metadata.
- ⚪ not run source resolution should always recover when the transcript moved within known host roots.
- ⚪ not run source resolution should always fail clearly when the host transcript can no longer be found.

## Execution

### Failure Handling

- ⚪ not run episode rows should always reject duplicate repo_id and thread_id pairs.
- ⚪ not run episode_event rows should always reject duplicate host_event_key values within one episode.
- ⚪ not run episode import should always surface a user-actionable error when a host source disappears.
- ⚪ not run episode import should always roll back partial writes if a DB write fails mid-import.

### High Level Behavior

- ⚪ not run codex and claude code imports should always produce the same stored event shape for equivalent flows.
- ⚪ not run episode import should always store compact event content rather than raw noisy transcript blobs.
- ⚪ not run episode import should always preserve user and assistant order.

### Record Writes

- ⚪ not run first episode import should always create one episode and ordered episode events.
- ⚪ not run re-import of the same host session should always not duplicate episode events.
- ⚪ not run incremental re-import should always append only newly seen events.
- ⚪ not run the same host session should always map to the same stored episode.

# Events Tests

## Validation

### Request Shape

- ⚪ not run events requests should always accept an optional limit without extra selectors.
- ⚪ not run events requests should always enforce configured limit bounds.
- ⚪ not run events requests should always reject unknown fields.
- ⚪ not run events hydration should always infer repo_id and the default limit.

## Execution

### Failure Handling

- ⚪ not run events should always return not_found when no active host session exists for the repo.

### High Level Behavior

- ✅ events should always sync the active host session and return recent stored events newest first.
- ✅ events should always prefer the trusted caller identity over newer repo-matching host sessions.

# Guidance Tests

## Execution

### Create Solution

- ✅ create solution should always emit pending_utility_votes guidance when session has unrated retrieved memories.

### Failure Handling

- ✅ guidance failures should always require events when batch utility votes omit evidence and no recent events exist.

### Reminders

- ✅ guidance reminders should always be rate limited per problem.

### Update Batch

- ✅ update batch should always apply multiple utility votes and clear pending candidates.

# Identity Tests

## Execution

### Claude Hook

- ✅ claude hook identity should always resolve one trusted main caller from Shellbrain hook env.
- ✅ claude hook identity should always resolve one trusted subagent caller when agent_key is present.

### Codex Runtime

- ✅ codex runtime identity should always resolve one trusted caller from CODEX_THREAD_ID.

### Failure Handling

- ✅ identity failure handling should always return host_hook_missing when Claude runtime is detected without trusted Shellbrain identity.
- ✅ identity failure handling should always return host_identity_drifted when one trusted identity transcript cannot be resolved.

### Fallback

- ✅ identity fallback should always mark the discovered events candidate untrusted when no runtime identity exists.

### Hook Install

- ✅ claude hook install should always write one repo-local settings file with Shellbrain identity exports.

# Persistence Tests

## Execution

### Backup Restore

- ⚪ not run persistence should recover sentinel shellbrain data through pg_dump and restore into a fresh database.

### Container Lifecycle

- ⚪ not run persistence should preserve sentinel shellbrain data across DB container deletion and recreation.

### Local Migration

- ⚪ not run local migration should preserve legacy data while promoting the cluster to shellbrain naming.

# Read Tests

## Validation

### Unit

- ⚪ not run read hydration should always infer repo_id and default knobs when omitted.
- ⚪ not run read hydration should always preserve explicit payload values over inferred defaults.
- ⚪ not run read hydration should always merge partial expand overrides over config defaults.
- ⚪ not run read requests should always reject unknown fields.
- ⚪ not run read requests should always reject op values other than read.
- ⚪ not run read requests should always require non-empty query text.
- ⚪ not run read requests should always limit kinds filters to ratified shellbrain kinds.
- ⚪ not run read requests should always require unique kinds filters.
- ⚪ not run read requests should always reject config override knobs at the agent interface.

## Execution

### Context Pack

- ⚪ not run read context pack config should always define mode-specific limits in read policy yaml.
- ⚪ not run read context pack config should always define direct-heavy quotas by mode in read policy yaml.
- ⚪ not run read context pack config should always load RRF defaults from the read policy yaml.
- ⚪ not run context pack builder should always use targeted mode as eight items by default.
- ⚪ not run context pack builder should always use ambient mode as twelve items by default.
- ⚪ not run read context pack should always return grouped sections under data.pack.
- ⚪ not run read context pack should always order sections as meta, direct, explicit_related, then implicit_related.
- ⚪ not run read context pack should always assign global priority values in displayed order.
- ⚪ not run read context pack should always include kind and text for each returned memory.
- ⚪ not run read context pack should always include why_included for every item.
- ⚪ not run read context pack should always include anchor_memory_id only for non-direct items.
- ⚪ not run read context pack should always include relation_type only for association-link items.
- ⚪ not run read context pack should always omit scenarios in this slice.
- ⚪ not run context pack builder should always fill targeted quotas in direct-first order.
- ⚪ not run context pack builder should always fill ambient quotas with more related context than targeted mode.
- ⚪ not run context pack builder should always deduplicate repeated memories across sections.
- ⚪ not run context pack builder should always let earlier sections win dedupe ties.
- ⚪ not run context pack builder should always shrink a small custom limit in direct-first order.
- ⚪ not run context pack builder should always use spillover when a section underfills.
- ⚪ not run context pack builder should always pick the highest-scoring unselected candidates during spillover.
- ⚪ not run context pack builder should always enforce the hard limit after quotas and spill.

### Determinism

- ⚪ not run read should always return each shellbrain at most once even if reached by multiple paths.
- ⚪ not run read should always produce deterministic ordering for the same input and snapshot.

### Expansion

- ⚪ not run read should always include linked problem attempts when problem-link expansion is enabled.
- ⚪ not run read should always include linked fact updates when fact-update expansion is enabled.
- ⚪ not run read should always include linked association neighbors only when enabled and edge strength passes threshold.
- ⚪ not run read should always expand association neighbors only up to max_association_depth.

### High Level Behavior

- ⚪ not run read should always be retrieval-only and never mutate database state.
- ⚪ not run read should always enforce repo visibility and include_global scope rules.
- ⚪ not run read should always apply kinds as include-only filters.
- ⚪ not run read should always enforce a hard output cap equal to limit.
- ⚪ not run read should always return an empty pack when nothing passes retrieval gates.

### Keyword

- ⚪ not run keyword retrieval should always admit high-coverage partial matches while rejecting low-coverage generic partial matches.
- ⚪ not run keyword retrieval should always be stricter for ambient reads than for targeted reads.
- ⚪ not run keyword retrieval should always rank denser shorter matches ahead of verbose matches.
- ⚪ not run keyword retrieval should always gate the visible lexical corpus before scoring.
- ⚪ not run keyword retrieval should always break equal-score ties by shellbrain identifier.

### Scoring

- ⚪ not run read scoring should always preserve RRF ordering for fused direct seeds.
- ⚪ not run read scoring should always rank a dual-lane hit above single-lane hits.
- ⚪ not run read scoring should always break equal RRF scores by shellbrain identifier.
- ⚪ not run read scoring should always rank shallower explicit candidates above deeper ones.
- ⚪ not run read scoring should always rank stronger association edges above weaker ones.
- ⚪ not run read scoring should always ignore relation strength for non-association explicit links.
- ⚪ not run read scoring should always rank higher-similarity implicit candidates above lower ones.
- ⚪ not run read scoring should always rank lower-hop implicit candidates above higher-hop ones.
- ⚪ not run read scoring should always return raw explicit metadata for downstream scoring.
- ⚪ not run read scoring should always return raw implicit metadata for downstream scoring.
- ⚪ not run read scoring should always order competing expanded candidates via the scoring stage.

### Semantic

- ⚪ not run read should always return semantic seed matches when lexical retrieval misses.
- ⚪ not run read should always apply repo visibility, include_global, and kinds filters before admitting semantic matches.
- ⚪ not run read should always fuse semantic and keyword direct hits without duplicating shared memories.
- ⚪ not run read should always expand implicit semantic neighbors only up to semantic_hops depth.
- ⚪ not run read should always keep semantic ordering deterministic for the same input and snapshot.
- ⚪ not run read should always exclude archived memories from direct retrieval and all expansion paths.
- ⚪ not run read should always return visible semantic matches through the real semantic lane when lexical retrieval misses.
- ⚪ not run read should always apply archived, repo visibility, include_global, and kinds filters in the real semantic lane.
- ⚪ not run read should always expand semantic neighbors through the real semantic lane only up to semantic_hops depth.
- ⚪ not run read should always return semantic direct matches through the live query-embedding seam when lexical retrieval misses.
- ⚪ not run read should always fuse live semantic seeds with keyword direct hits without duplicates.
- ⚪ not run read should always surface query-embedding failure as a structured read error rather than silently dropping the semantic lane.

# Session State Tests

## Execution

### Cleanup

- ✅ session state gc should always remove stale state files after 7 days.

### Create

- ✅ create problem should always set current_problem_id in trusted session state.

### Events

- ✅ events should always persist trusted caller session state.

### Expiry

- ✅ idle expiry should always reset working-session fields after 24 hours.

### Isolation

- ✅ multi agent isolation should always keep distinct session state files per caller_id.

# Telemetry Tests

## Validation

### Event Content

- ✅ episode event content should always include normalized tool telemetry fields when present.
- ✅ episode event content should always omit tool telemetry fields for non-tool events.
- ✅ codex and claude code should always normalize equivalent tool results into the same analytics shape.

## Execution

### Derived Views

- ✅ usage_command_daily should always aggregate daily command outcomes from operation invocations.
- ✅ usage_memory_retrieval should always aggregate retrieval frequency and last-seen timestamps from read result items.
- ✅ usage_write_effects should always aggregate write effect types and counts from write effect items.
- ✅ usage_sync_health should always aggregate sync outcomes and tool-type counts by host.
- ✅ usage_session_protocol should always aggregate per-thread read, events, and write counts.
- ✅ usage_session_protocol should always aggregate zero-result reads and ambiguous session selections.
- ✅ usage_session_protocol should always aggregate writes preceded by events and events followed by no write.

### Episode Sync Runs

- ✅ events should always append one episode sync run for inline transcript sync.
- ✅ poller sync should always append one episode sync run with source poller.
- ✅ episode sync runs should always record imported-event count and total event counts by source.
- ✅ episode sync runs should always record tool-type counts from the normalized episode content.

### Failure Handling

- ✅ read validation failures should always append one failed operation invocation and no read summary row.
- ✅ create validation failures should always append one failed operation invocation and no write summary row.
- ✅ update validation failures should always append one failed operation invocation and no write summary row.
- ✅ events not_found should always append one failed operation invocation and no episode sync run.
- ✅ events sync failures should always append one failed operation invocation and one failed episode sync run.
- ✅ unexpected operational failures should always append one failed operation invocation with internal-error stage.
- ✅ poller sync failures should always append one failed episode sync run.

### Operation Invocations

- ✅ read should always append one operation invocation row with command, repo_id, outcome, and latency fields.
- ✅ create should always append one operation invocation row with command, repo_id, outcome, and latency fields.
- ✅ update should always append one operation invocation row with command, repo_id, outcome, and latency fields.
- ✅ events should always append one operation invocation row with the resolved host, session, thread, and episode ids.
- ✅ operational invocations should always record whether no-sync was used.
- ✅ repo-matching multi-session discovery should always record candidate count and selection_ambiguous when more than one session matches.

### Packaging Smoke

- ✅ installed-package admin migrate should initialize the usage telemetry tables and views from packaged artifacts.

### Read Summaries

- ✅ read should always append one read summary row with effective request metadata.
- ✅ read should always append one read result item row per returned memory in display order.
- ✅ read should always record kind, section, priority, why-included, and anchor metadata for each returned item.
- ✅ read should always record zero-results true when the context pack is empty.

### Write Summaries

- ✅ create should always append one write summary row with the created memory id, kind, scope, and evidence-ref count.
- ✅ create should always append one write effect row per planned side effect in plan order.
- ✅ successful writes should always record planned-effect count for downstream effect aggregation.
- ✅ update utility_vote should always append one write summary row with update type utility_vote and utility observation count.
- ✅ update association_link should always append one write summary row with update type association_link and association effect count.
- ✅ update fact_update_link should always append one write summary row with update type fact_update_link and fact-update count.
- ✅ update archive_state should always append one write summary row with update type archive_state and archived-memory count.

### Persistence / Backup Restore

- ✅ persistence should recover sentinel usage telemetry rows through pg_dump and restore into a fresh database.

### Persistence / Container Lifecycle

- ✅ persistence should preserve sentinel usage telemetry rows across DB container deletion and recreation.

### Persistence / Local Migration

- ✅ local migration should preserve sentinel usage telemetry while promoting the cluster to shellbrain naming.

# Update Tests

## Validation

### Failure Handling

- ⚪ not run rejected update requests should always write nothing.

### Hydration

- ⚪ not run update hydration should always infer repo_id when omitted.
- ⚪ not run update hydration should always preserve explicit repo_id over inferred defaults.

### Link Rules

- ⚪ not run association_link updates should always reject self-links.
- ⚪ not run fact_update_link updates should always require distinct fact endpoints and reserve memory_id for the change memory.

### Reference Checks

- ⚪ not run update requests should always require memory_id to reference a visible memory.
- ⚪ not run utility_vote updates should always require problem_id to reference a visible problem memory.
- ⚪ not run fact_update_link updates should always require visible fact endpoints and memory_id to reference a visible change memory.
- ⚪ not run fact_update_link updates should always require fact endpoints and a change-shellbrain target.
- ⚪ not run association_link updates should always require to_memory_id to reference a visible memory.
- ⚪ not run association_link updates should always reject evidence refs from another repo's episode.
- ⚪ not run optional update evidence should always resolve to stored episode events when supplied.

### Request Shape

- ⚪ not run update requests should always reject unrecognized update.type values.
- ⚪ not run update requests should always reject op/repo_id at the agent interface.
- ⚪ not run update requests should always accept batch utility-vote payloads.

## Execution

### Failure Handling

- ⚪ not run problem_attempt rows should always reject identical problem_id and attempt_id values.
- ⚪ not run fact_update rows should always reject identical old_fact_id and new_fact_id values.
- ⚪ not run fact_update rows should always reject change_id values that equal old_fact_id or new_fact_id.
- ⚪ not run episode rows should always reject ended_at values earlier than started_at.
- ⚪ not run session_transfer rows should always reject identical from_episode_id and to_episode_id values.
- ⚪ not run failed update execution should always roll back every partial write.

### High Level Behavior

- ⚪ not run archiving a shellbrain should always change only its archived flag.
- ⚪ not run non-archiving updates should always leave the original shellbrain row unchanged.

### Record Writes

- ⚪ not run update(utility_vote) commit should always append one utility_observation with the provided payload.
- ⚪ not run update(fact_update_link) commit should always append one fact_update with change_id equal to memory_id.
- ⚪ not run update(association_link) commit should always persist edge, observation, and edge evidence links.
- ⚪ not run each update type should always write only its own kind of related record.
