# Tests Status

Generated: 2026-03-19 14:30:51 PDT

## Summary

- Total: 283
- Passed: 0
- Failed: 0
- Skipped/Not Run: 283

# Config Tests

- ⚪ not run alembic env should route migrations through the admin DSN when present.
- ⚪ not run alembic env should still support the single-DSN fallback when no admin DSN exists.
- ⚪ not run repo context resolution should fall back to one weak-local repo id outside git.
- ⚪ not run repo context resolution should preserve an explicit repo_id override.
- ⚪ not run top-level help should explain the Shellbrain mental model and session protocol.
- ⚪ not run init help should explain the managed bootstrap path and advanced overrides.
- ⚪ not run read help should teach focused querying and pack structure.
- ⚪ not run events help should explain fresh episodic evidence lookup.
- ⚪ not run create help should explain memory-kind choice and attempt-link rules.
- ⚪ not run update help should expose the supported update types.
- ⚪ not run admin help should always include one minimal example.
- ⚪ not run admin migrate help should always include one minimal example.
- ⚪ not run admin backup help should explain the first-class backup workflow.
- ⚪ not run admin doctor help should explain the safety report path.
- ⚪ not run admin install-claude-hook help should explain the trusted Claude setup step.
- ⚪ not run admin session-state help should expose inspect, clear, and gc management paths.
- ⚪ not run repo-targeting flags should work before the operational subcommand.
- ⚪ not run repo-targeting flags should also work after the operational subcommand.
- ⚪ not run --no-sync should suppress repo-local poller startup after a successful command.
- ⚪ not run admin migrate should delegate to the packaged migration runner.
- ⚪ not run unsafe app-role failures should return exit code 1 without a traceback.
- ⚪ not run admin backup create should print the created manifest as JSON.
- ⚪ not run admin doctor should print one JSON safety report.
- ⚪ not run init should print the stable outcome prefix and forward the mapped exit code.
- ⚪ not run init should disable Claude integration when --no-claude is provided.
- ⚪ not run explicit repo-root overrides should fail fast when the directory does not exist.
- ⚪ not run The shared destructive guard should always create and verify one backup.
- ⚪ not run yaml config provider should always expose separate create and update policy sections.
- ⚪ not run The longer onboarding surfaces should teach the same Shellbrain mental model.
- ⚪ not run Top-level CLI help should match the condensed taught workflow.
- ⚪ not run The reusable shellbrain skill should include Codex UI metadata.
- ⚪ not run editable installs should expose the shellbrain console script outside this repository.
- ⚪ not run git-url installs should expose the shellbrain console script outside this repository.
- ⚪ not run installed-package admin migrate should initialize an empty database from packaged artifacts.
- ⚪ not run read policy should always resolve missing read knobs from config.
- ⚪ not run read policy should always merge partial expand over config defaults.
- ⚪ not run db boot should always resolve the runtime-configured dsn env.
- ⚪ not run db boot should use the managed machine config before env-based runtime settings.
- ⚪ not run db boot should direct the user to rerun init when machine config is corrupt.
- ⚪ not run runtime yaml should always define database cli and embedding sections.
- ⚪ not run Unsafe app-role checks should fail closed unless explicitly relaxed.
- ⚪ not run Unsafe app-role checks may be downgraded explicitly for controlled debugging.
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

- ⚪ not run codex parsing should always normalize user and assistant messages into the common event shape.
- ⚪ not run claude code parsing should always normalize user and assistant messages into the common event shape.
- ⚪ not run episode parsing should always keep meaningful tool results and drop noisy tool chatter.
- ⚪ not run episode parsing should always skip unknown transcript lines without failing normalization.

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

- ⚪ events should always return not_found when no active host session exists for the repo.

### High Level Behavior

- ⚪ events should always sync the active host session and return recent stored events newest first.
- ⚪ events should always prefer the trusted caller identity over newer repo-matching host sessions.

# Guidance Tests

## Execution

### Create Solution

- ⚪ not run create solution should always emit pending_utility_votes guidance when session has unrated retrieved memories.

### Failure Handling

- ⚪ not run guidance failures should always require events when batch utility votes omit evidence and no recent events exist.

### Reminders

- ⚪ not run guidance reminders should always be rate limited per problem.

### Update Batch

- ⚪ not run update batch should always apply multiple utility votes and clear pending candidates.

# Identity Tests

## Execution

### Claude Hook

- ⚪ not run claude hook identity should always resolve one trusted main caller from Shellbrain hook env.
- ⚪ not run claude hook identity should always resolve one trusted subagent caller when agent_key is present.

### Codex Runtime

- ⚪ not run codex runtime identity should always resolve one trusted caller from CODEX_THREAD_ID.

### Failure Handling

- ⚪ not run identity failure handling should always return host_hook_missing when Claude runtime is detected without trusted Shellbrain identity.
- ⚪ not run identity failure handling should always return host_identity_drifted when one trusted identity transcript cannot be resolved.

### Fallback

- ⚪ not run identity fallback should always mark the discovered events candidate untrusted when no runtime identity exists.

### Hook Install

- ⚪ not run claude hook install should always write one repo-local settings file with Shellbrain identity exports.
- ⚪ not run claude hook install should merge the managed SessionStart entry non-destructively.

# Persistence Tests

## Execution

### Backup Restore

- ⚪ not run admin backup create should always write a verifiable artifact and manifest.
- ⚪ not run admin backup verify should fail when the artifact content no longer matches the manifest hash.
- ⚪ not run admin backup restore should never allow in-place restores into protected DB names.
- ⚪ not run admin backup restore should sanitize unsupported pg_dump session settings before psql.
- ⚪ not run persistence should recover sentinel shellbrain data through pg_dump and restore into a fresh database.

### Container Lifecycle

- ⚪ not run persistence should preserve sentinel shellbrain data across DB container deletion and recreation.

### Local Migration

- ⚪ not run local migration should preserve legacy data while promoting the cluster to shellbrain naming.

# Protection Tests

## Execution

### Db Targeting

- ⚪ not run instance guard should refuse the exact protected live DSN.
- ⚪ not run instance guard should refuse production-shaped database names even without a live fingerprint.
- ⚪ not run instance fingerprinting should classify one DB independently of app/admin role usernames.
- ⚪ not run destructive guard should refuse databases that are not explicitly stamped disposable.
- ⚪ not run destructive guard should never allow automation against live instances.
- ⚪ not run destructive guard should allow explicitly stamped test instances.

### Scripts

- ⚪ not run run_tests should refuse to start unless one disposable test DSN is configured.
- ⚪ not run run_tests should abort before any DDL when the test DSN points at a protected target.

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
- ⚪ not run read requests should always reject hidden expansion override knobs at the agent interface.

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

# Recovery Tests

## Execution

- ⚪ not run init should stop with blocked_config_corrupt when corrupt machine state cannot be rediscovered.
- ⚪ not run init should create a backup first and report repaired when bootstrap state needs repair.
- ⚪ not run blocked conflicts should not leave machine state stranded in provisioning.
- ⚪ not run auto Claude handling should not mutate config when only repo-local Claude files are present.
- ⚪ not run forced Claude mode should install the hook even without runtime auto-detection.
- ⚪ not run role creation should not use server-side bind params inside CREATE/ALTER ROLE.
- ⚪ not run created containers should reserve their declared host ports for future init runs.

### Missing Backup Behavior

- ⚪ not run backup verify should fail clearly when no backup manifests exist.
- ⚪ not run backup restore should fail clearly when no backup manifests exist.

# Resilience Tests

## Execution

### Permission Failures

- ⚪ not run doctor should still produce one report when the app DSN is not configured.
- ⚪ not run doctor should summarize backup age and both role-safety channels.

# Session State Tests

## Execution

### Cleanup

- ⚪ not run session state save should atomically replace the caller file without leaking temp files.
- ⚪ not run session state clear should only delete the explicitly named caller file.
- ⚪ not run session state gc should always remove stale state files after 7 days.

### Create

- ⚪ not run create problem should always set current_problem_id in trusted session state.

### Events

- ⚪ not run events should always persist trusted caller session state.

### Expiry

- ⚪ not run idle expiry should always reset working-session fields after 24 hours.

### Isolation

- ⚪ not run multi agent isolation should always keep distinct session state files per caller_id.

# Telemetry Tests

## Validation

### Event Content

- ⚪ not run episode event content should always include normalized tool telemetry fields when present.
- ⚪ not run episode event content should always omit tool telemetry fields for non-tool events.
- ⚪ not run codex and claude code should always normalize equivalent tool results into the same analytics shape.

## Execution

### Derived Views

- ⚪ not run usage_command_daily should always aggregate daily command outcomes from operation invocations.
- ⚪ not run usage_memory_retrieval should always aggregate retrieval frequency and last-seen timestamps from read result items.
- ⚪ not run usage_write_effects should always aggregate write effect types and counts from write effect items.
- ⚪ not run usage_sync_health should always aggregate sync outcomes and tool-type counts by host.
- ⚪ not run usage_session_protocol should always aggregate per-thread read, events, and write counts.
- ⚪ not run usage_session_protocol should always aggregate zero-result reads and ambiguous session selections.
- ⚪ not run usage_session_protocol should always aggregate writes preceded by events and events followed by no write.

### Episode Sync Runs

- ⚪ events should always append one episode sync run for inline transcript sync.
- ⚪ poller sync should always append one episode sync run with source poller.
- ⚪ episode sync runs should always record imported-event count and total event counts by source.
- ⚪ episode sync runs should always record tool-type counts from the normalized episode content.

### Failure Handling

- ⚪ read validation failures should always append one failed operation invocation and no read summary row.
- ⚪ create validation failures should always append one failed operation invocation and no write summary row.
- ⚪ update validation failures should always append one failed operation invocation and no write summary row.
- ⚪ events not_found should always append one failed operation invocation and no episode sync run.
- ⚪ events sync failures should always append one failed operation invocation and one failed episode sync run.
- ⚪ unexpected operational failures should always append one failed operation invocation with internal-error stage.
- ⚪ poller sync failures should always append one failed episode sync run.

### Operation Invocations

- ⚪ read should always append one operation invocation row with command, repo_id, outcome, and latency fields.
- ⚪ create should always append one operation invocation row with command, repo_id, outcome, and latency fields.
- ⚪ update should always append one operation invocation row with command, repo_id, outcome, and latency fields.
- ⚪ events should always append one operation invocation row with the resolved host, session, thread, and episode ids.
- ⚪ operational invocations should always record whether no-sync was used.
- ⚪ repo-matching multi-session discovery should always record candidate count and selection_ambiguous when more than one session matches.

### Packaging Smoke

- ⚪ not run installed-package admin migrate should initialize the usage telemetry tables and views from packaged artifacts.

### Read Summaries

- ⚪ not run read should always append one read summary row with effective request metadata.
- ⚪ not run read should always append one read result item row per returned memory in display order.
- ⚪ not run read should always record kind, section, priority, why-included, and anchor metadata for each returned item.
- ⚪ not run read should always record zero-results true when the context pack is empty.

### Write Summaries

- ⚪ not run create should always append one write summary row with the created memory id, kind, scope, and evidence-ref count.
- ⚪ not run create should always append one write effect row per planned side effect in plan order.
- ⚪ not run successful writes should always record planned-effect count for downstream effect aggregation.
- ⚪ not run update utility_vote should always append one write summary row with update type utility_vote and utility observation count.
- ⚪ not run update association_link should always append one write summary row with update type association_link and association effect count.
- ⚪ not run update fact_update_link should always append one write summary row with update type fact_update_link and fact-update count.
- ⚪ not run update archive_state should always append one write summary row with update type archive_state and archived-memory count.

### Persistence / Backup Restore

- ⚪ not run persistence should recover sentinel usage telemetry rows through pg_dump and restore into a fresh database.

### Persistence / Container Lifecycle

- ⚪ not run persistence should preserve sentinel usage telemetry rows across DB container deletion and recreation.

### Persistence / Local Migration

- ⚪ not run local migration should preserve sentinel usage telemetry while promoting the cluster to shellbrain naming.

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
