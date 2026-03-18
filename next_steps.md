# Next Steps

## Current Baseline

These are done and should not still be treated as open roadmap items:

- `shellbrain` is packaged as an installable CLI and is intended to be installed once per machine, not per repo.
- `shellbrain --help` and subcommand help exist and teach the `read -> events -> create/update` workflow.
- A Codex session-start skill exists and is installable in `$CODEX_HOME/skills`.
- Local PostgreSQL storage is host-backed, and destructive persistence tests exist for:
  - container delete/recreate
  - backup/restore
  - local cluster migration to `shellbrain` naming
- Scenario lift remains intentionally deferred from the current read output.

## Immediate Priorities

### 1. Real-World Dogfooding

- Use `shellbrain` in real external repos and real agent sessions.
- Focus on operator friction rather than backend correctness:
  - whether `read` returns useful context at session start
  - whether `events` finds the right session reliably
  - whether write decisions feel natural or too cumbersome
  - whether background sync behavior is surprising
  - whether failure messages are actionable
- Capture concrete examples of where the tool helps, where it is noisy, and where it is ignored.

### 2. Agent Usage Metadata and Analytics

- Add first-class metadata about how agents use Shellbrain so later analysis is possible without replaying raw transcripts by hand.
- At minimum, capture enough information to answer questions like:
  - how many memories were created per session
  - how many `read` calls happened per session
  - how many memories were returned per read
  - what kinds of memories were returned
  - how many `events` were inspected before writes
  - how many user prompts and assistant messages existed in the active episode
  - how many tool events existed in the active episode
  - what tool types appeared in the episode evidence
  - how often a read returned zero results
  - how often an agent wrote nothing after calling `events`
- Treat this as structured product telemetry, not ad hoc logs.
- Prefer a durable event or summary table so later statistics can be computed directly.
- Keep the first version narrow and cheap:
  - one record per CLI invocation
  - one record per read result summary
  - one record per write result summary
  - one record per synced episode summary
- Useful fields to consider:
  - timestamp
  - repo_id
  - host_app
  - session / episode id
  - operation type
  - success / error outcome
  - counts of user / assistant / tool events
  - counts of memories returned / created / updated / archived
  - returned memory ids and kinds
  - whether `--no-sync` was used
  - latency by stage where available
- Add tests that prove these records are written deterministically and can support downstream stats queries.

### 3. Usage Entropy, Protocol Compliance, and Session Guidance

- Good docs and a good skill are necessary, but they will not eliminate usage variance by themselves.
- The real risk is protocol entropy across agents and sessions, for example:
  - one agent queries multiple times during the search, another only once at session start
  - one agent writes `problem` / `failed_tactic` / `solution`, another forgets one or more of them
  - one agent places `utility_vote` updates on all relevant retrieved memories, another only updates one and stops
  - one agent stores facts and changes carefully, another remembers only the experiential path
- Treat this as a product problem, not just a prompt-writing problem.
- The system should make the desired workflow easier to follow than the incomplete workflow.

Near-term remedy direction:

- add usage metadata first so protocol variance becomes measurable
- add a session ledger so Shellbrain can remember:
  - which reads happened this session
  - which memories were returned
  - which evidence events were inspected
  - which writes have already been made
  - which retrieved memories still need `utility_vote`
  - whether a `problem` has a corresponding `solution` / `failed_tactic` set yet
- add a session closeout / normalization surface that asks the agent to finish the protocol:
  - store the `problem`
  - store each `failed_tactic`
  - store the `solution`
  - store any durable `fact`, `preference`, or `change`
  - place `utility_vote` updates on the key retrieved memories
- add soft lints and nudges rather than hard failures at first, for example:
  - reads happened but no `utility_vote` updates were written
  - a `solution` was stored without a corresponding `problem`
  - a session queried many prior attempts but wrote nothing back
  - a write happened without fresh `events`
  - a `change` was written without the matching fact-evolution follow-through
- keep these as warnings / closeout prompts first, then decide later whether any should become stronger enforcement.

This should reduce reliance on the agent "remembering the protocol from scratch" and shift that burden into Shellbrain itself.

### 4. Episode Content Contract for Analytics

- Define the canonical `episode_events.content` payload shape explicitly enough that analytics can rely on it.
- Ensure the normalized event payload makes it easy to count:
  - user prompts
  - assistant responses
  - tool invocations
  - tool result types
- Add edge validation if the content contract needs to harden before analytics are layered on top.
- Keep the content contract compact and stable; avoid turning it back into raw transcript blobs.

### 5. Backup and Export Operational Surface

- Persistence validation exists, but the operator surface is still thin.
- Add a concrete backup/export command or script using `pg_dump`.
- Add a concrete restore command or script.
- Document the expected restore flow for:
  - same-machine recovery
  - migration to a new machine
  - recovery after Docker removal
- Decide the default local backup cadence and retention expectation.

## Near-Term Product Improvements

### 6. Session Nudges, Supervisor Model, and Possible Back-Channel

- Today Shellbrain is effectively pull-based from the agent's point of view:
  - the agent calls `read`, `events`, `create`, or `update`
  - Shellbrain replies inside that tool response
- That means the simplest guidance path today is to attach nudges to the next Shellbrain response, not to interrupt the agent mid-session.
- We should think seriously about whether a stronger back-channel is possible.

Research question:

- can a local supervisor process communicate back into an active Codex or Claude Code session while the session is still running?

Possible directions:

- investigate whether the host apps expose a writable thread/message API or another supported message-injection surface
- if a writable host back-channel exists, a local supervisor agent could:
  - watch protocol compliance during the session
  - send reminders like:
    - "you queried but have not updated utility yet"
    - "you found a fact change; consider writing `change` + new `fact` + `fact_update_link`"
    - "you solved a problem but have not yet stored failed tactics"
- if no writable back-channel exists, use the fallback pattern:
  - maintain app-level pending nudges in Shellbrain
  - surface them in the next `read` / `events` / `create` / `update` response
  - possibly add a dedicated closeout or "what am I forgetting?" command

This is worth exploring because a supervisor loop could reduce protocol entropy much more effectively than static instructions alone.

### 7. Operator Experience Refinements

- Continue tightening the global-install assumption across docs and operator workflows.
- Keep the expected machine-level setup explicit:
  - one global CLI install
  - shell profile export for `SHELLBRAIN_DB_DSN`
  - one-time `shellbrain admin migrate`
- Watch for confusion around repo inference:
  - current behavior is cwd-based, not git-root-based
  - decide later whether git-root inference is worth adding
- Consider making first-run embedding downloads less surprising on the `read` path.

### 8. Product Ideas Worth Borrowing

- MoltBrain is worth treating as a useful comparison point for operator experience, not as a blueprint for Shellbrain's trust model.
- Borrow the parts that improve discoverability, observability, and day-to-day usability without giving up Shellbrain's explicit evidence discipline.

Near-term product ideas worth borrowing:

- make the install and bootstrap path feel more like a polished user tool:
  - prefer a crisp global-install story
  - consider a `shellbrain doctor` or equivalent environment check
  - make database/bootstrap state easier to verify at a glance
- add a proper operator-facing viewer:
  - browse memories by repo, kind, and recency
  - inspect evidence links and utility history
  - inspect what a read returned and why
  - inspect episodes and episode events without raw SQL
- add analytics and export surfaces:
  - session-level usage summaries
  - memory creation / retrieval / utility trends
  - lightweight export for backup, analysis, or sharing
- add curation affordances where they help humans manage the corpus:
  - favorites / pins for especially important memories
  - lightweight tags or labels if they improve navigation
  - manual review surfaces for high-value memories

What not to borrow by default:

- do not make durable memory creation fully automatic
- do not replace explicit `events -> evidence_refs -> create/update` with summary-only extraction
- do not blur the distinction between episodic capture and durable semantic / procedural memory

The right borrowing strategy is:

- borrow MoltBrain's product polish and operator visibility
- keep Shellbrain's evidence-backed, typed, case-based reasoning core intact

### 9. Agent-Facing Context Pack Metadata

- The read result already returns structured JSON with top-level sections:
  - `meta`
  - `direct`
  - `explicit_related`
  - `implicit_related`
- Extend each item so the pack is more inspectable and self-explanatory:
  - shellbrain type
  - text/content
  - why it was included
  - relation/anchor metadata when relevant
  - priority/order within its section
- Keep `scenarios` explicitly deferred for now.
- Do not treat scenario lift as part of the current v1 output surface until it is intentionally reintroduced.

### 10. Retrieval Metadata and Usage Signals

- Add lightweight metadata to every read result so behavior is inspectable without digging through logs.
- Useful fields to include:
  - accessed shellbrain IDs
  - access timestamps
  - retrieval scores / rank position
  - shellbrain type and source
  - freshness / last-updated time
  - token count per shellbrain and per assembled pack
  - whether an item was directly matched, explicitly related, or implicitly related
  - whether an item was actually included vs. dropped by quotas or caps
- Track simple usage stats over time:
  - read frequency by shellbrain
  - inclusion frequency by shellbrain
  - drop frequency due to cap pressure
  - stale-shellbrain hit rate
  - duplicate / near-duplicate retrieval rate

### 11. System Performance Metrics

- Define a small metrics set that tells us whether the shellbrain setup is becoming more useful.
- Candidate metrics:
  - retrieval precision proxy: fraction of returned memories that are later referenced or used
  - context-pack utilization: fraction of included memories that affect the final answer
  - miss rate: cases where needed shellbrain exists but was not retrieved
  - latency split: retrieval time, packing time, total read time
  - token efficiency: useful tokens / total context tokens sent to the model
  - freshness quality: share of retrieved memories that are recent enough for the task
  - repetition rate: how often the same low-value memories keep showing up
  - user correction rate: how often the answer is corrected because context was missing or noisy
- Add a feedback loop so these metrics can drive tuning of quotas, scoring, and dedupe rules.

## Later Work

### 12. Episodes and Session Transfer Support

- `episodes` and `episode_events` are implemented and validated end to end.
- Remaining work is to operationalize the rest of the episodic model:
  - wire `session_transfers` into real handoff flows
  - add execution tests that prove transfer writes work against PostgreSQL
  - decide how transfer events should participate in agent-facing analytics

### 13. Later: Local Model for Triage / Filtering

- Consider a smaller local model ahead of the main model for cheap first-pass categorization or filtering.
- Possible uses:
  - classify query intent before retrieval
  - filter obviously irrelevant memories
  - route between retrieval strategies
  - perform cheap reranking before the higher-cost model sees context
- Treat this as a later optimization after baseline metadata and metrics exist, so we can measure whether it actually improves quality, latency, or cost.

### 14. Usability: Batch Questions for Memory Reads

- Support a single shellbrain-read call that accepts multiple questions at once, instead of forcing the LLM into sequential reads.
- The goal is to let the model ask for "everything I need to know" in one interaction when it has several sub-questions.
- Return results in a structured place the LLM can inspect directly, for example:
  - one section per question
  - shared results that apply across questions
  - deduped memories reused across the batch
  - per-question rationale for why each shellbrain was included
- This should reduce extra tool turns and token burn caused by back-to-back shellbrain queries.
- Design the interface so batching is a first-class usability path, not just a thin wrapper around repeated single-question retrieval.

### 15. Later: Scenario Lift

- Keep scenario lift out of the current v1 read output.
- Revisit it later as a separate project once the atomic-shellbrain path, metadata, and operational surface are stable.
- When revisited, define:
  - scenario projection schema
  - ranking inputs
  - constructor trigger boundaries
  - pack quotas and display shape

### 16. V2: Automatic Related-Memory Reinforcement

- Treat this as v2, not v1.
- Add a background task that looks at which memories are repeatedly retrieved, cited, or used together.
- Use those co-usage signals to suggest or reinforce soft `associated_with` links automatically.
- Keep this separate from explicit agent-authored links like `depends_on`.
- Decide the exact evidence threshold before it is allowed to create or reinforce a link.
- Keep the reinforcement path auditable so auto-created links can be inspected, downgraded, or removed.

### 16. Possible Consideration: Exact-Retry Idempotency

- Consider exact-request retry dedupe for mutating operations if duplicate writes become an operational issue.
- Keep this narrow: exact normalized request replay within a short window, not fuzzy duplicate detection on shellbrain text.
- Treat this as optional until there is real evidence that retries are creating duplicate data in practice.

### 17. Later: Learned Memory-Type Classification

- Once enough labeled memories exist, train a lightweight classifier to predict shellbrain type from the shellbrain text and nearby context.
- Use it to suggest or auto-fill `kind` so the agent does not need to classify every shellbrain by hand forever.
- Keep the agent able to override the prediction, especially while the classifier is still immature.
- Track classifier confidence and disagreement rate before letting it become more automatic.
- Treat this as a later optimization after the corpus is large enough to provide useful training data.
