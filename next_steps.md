# Next Steps

## Immediate Operationalization

- Add a real `shellbrain --help` path so an agent that gets stuck can recover its bearings without guessing.
- Make help output cover the actual v1 workflow:
  - `events` to inspect recent episode events,
  - `create` / `update` with explicit `evidence_refs`,
  - `read` for retrieval-only shellbrain access.
- Add command-specific help and short examples so the agent can see the expected JSON shape for all four operations from the CLI itself.

- Add a session-start skill that teaches an agent how to use the shellbrain system correctly.
- The skill should cover:
  - when to call `read`,
  - when to call `events`,
  - how to pick event ids as evidence,
  - how to call `create` / `update`,
  - common failure modes and how to recover.
- Treat this as part of making the system usable in practice, not optional documentation polish.

- Keep storage durable even if the Docker container is destroyed.
- The key requirement is that shellbrain data must live on host-mounted disk or another durable local storage path, not only inside an ephemeral container filesystem.
- The current local Docker shape already bind-mounts PostgreSQL data to a host path; preserve that invariant and document it clearly as the default local deployment shape.
- Add automated durability validation:
  - write sentinel shellbrain data,
  - destroy and recreate the DB container with the same host data directory,
  - assert the shellbrain rows still exist.
- Add automated backup/restore smoke validation so portability is proven in practice, not only described in docs.
- Treat "survives Docker uninstall" as an architecture + backup/export requirement:
  - host-owned data path outside Docker-managed state,
  - plus a restoreable logical export path.
- Verify that backup/restore expectations match the actual runtime/storage setup.

- Define how this system is consumed from a completely different repo.
- Decide whether the operational path is:
  - installable CLI via `pip`,
  - editable/dev install,
  - wrapper script,
  - or another distribution mechanism.
- Document what another repo or agent environment needs in order to use it:
  - install step,
  - database/runtime prerequisites,
  - config/env vars,
  - how `repo_id` is inferred,
  - how transcript discovery works outside this repo.
- Add a concrete bootstrap/onboarding path so the shellbrain system is portable rather than only usable from this working tree.

## 1. Episodes and Session Transfer Support

- `episodes` and `episode_events` are implemented and validated end to end.
- Remaining work is to operationalize the rest of the episodic model:
  - define the canonical `episode_events.content` payload contract,
  - validate that payload at the edge,
  - wire `session_transfers` into real handoff flows,
  - add execution tests that prove transfer writes work against PostgreSQL.

## 2. Backup and Export Baseline

- Add a concrete logical backup/export workflow using `pg_dump` or `pg_dumpall`.
- Add a documented restore workflow so moving the system to another machine is routine rather than ad hoc.
- Decide the default backup cadence and retention policy for local operation.
- Add a small script or command surface so backup/export is part of the operational path, not just a requirement in docs.

## 3. External Packaging and CLI Help

- Ship an install story and entrypoint so another repo can use this without depending on `python -m memory_shellbrain.periphery.cli.main` from this working tree.
- Add real command-specific help and short examples for `create`, `read`, `update`, and `events`.
- Document the external bootstrap path:
  - install step,
  - database and migration prerequisites,
  - config/env vars,
  - how `repo_id` is inferred or overridden,
  - how transcript discovery works outside this repo,
  - what background side effects occur on successful CLI calls.
- Avoid leaving the external usage path implicit in test scripts.

## 4. Durable Local Storage Validation

- Add a black-box durability test that proves memories survive DB-container deletion and recreation when the same host data directory is reused.
- Add a black-box restore test that proves a logical export can recreate the shellbrain set in a fresh database.
- Keep these tests at the operational layer:
  - they should exercise the real Docker/postgres deployment shape,
  - not only the SQLAlchemy repositories in-process.
- Treat Docker uninstall safety as something supported by host-owned storage + restore workflow, rather than by a CI test that literally uninstalls Docker.

## 5. Agent-Facing Context Pack Metadata

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

## 6. Retrieval Metadata and Usage Signals

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

## 7. System Performance Metrics

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

## 8. Later: Local Model for Triage / Filtering

- Consider a smaller local model ahead of the main model for cheap first-pass categorization or filtering.
- Possible uses:
  - classify query intent before retrieval
  - filter obviously irrelevant memories
  - route between retrieval strategies
  - perform cheap reranking before the higher-cost model sees context
- Treat this as a later optimization after baseline metadata and metrics exist, so we can measure whether it actually improves quality, latency, or cost.

## 9. Usability: Batch Questions for Memory Reads

- Support a single shellbrain-read call that accepts multiple questions at once, instead of forcing the LLM into sequential reads.
- The goal is to let the model ask for "everything I need to know" in one interaction when it has several sub-questions.
- Return results in a structured place the LLM can inspect directly, for example:
  - one section per question
  - shared results that apply across questions
  - deduped memories reused across the batch
  - per-question rationale for why each shellbrain was included
- This should reduce extra tool turns and token burn caused by back-to-back shellbrain queries.
- Design the interface so batching is a first-class usability path, not just a thin wrapper around repeated single-question retrieval.

## 10. Later: Scenario Lift

- Keep scenario lift out of the current v1 read output.
- Revisit it later as a separate project once the atomic-shellbrain path, metadata, and operational surface are stable.
- When revisited, define:
  - scenario projection schema,
  - ranking inputs,
  - constructor trigger boundaries,
  - pack quotas and display shape.

## 11. V2: Automatic Related-Memory Reinforcement

- Treat this as v2, not v1.
- Add a background task that looks at which memories are repeatedly retrieved, cited, or used together.
- Use those co-usage signals to suggest or reinforce soft `associated_with` links automatically.
- Keep this separate from explicit agent-authored links like `depends_on`.
- Decide the exact evidence threshold before it is allowed to create or reinforce a link.
- Keep the reinforcement path auditable so auto-created links can be inspected, downgraded, or removed.

## 12. Possible Consideration: Exact-Retry Idempotency

- Consider exact-request retry dedupe for mutating operations if duplicate writes become an operational issue.
- Keep this narrow: exact normalized request replay within a short window, not fuzzy duplicate detection on shellbrain text.
- Treat this as optional until there is real evidence that retries are creating duplicate data in practice.

## 13. Later: Learned Memory-Type Classification

- Once enough labeled memories exist, train a lightweight classifier to predict shellbrain type from the shellbrain text and nearby context.
- Use it to suggest or auto-fill `kind` so the agent does not need to classify every shellbrain by hand forever.
- Keep the agent able to override the prediction, especially while the classifier is still immature.
- Track classifier confidence and disagreement rate before letting it become more automatic.
- Treat this as a later optimization after the corpus is large enough to provide useful training data.
