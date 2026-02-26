# Memory Storage Relational Schema v1 (SQLite)

Status: ratified direction from the 2026-02-18 conversation; extended on 2026-02-21 for episodic session metadata and transfer logs; naming aligned on 2026-02-25.

This card captures the concrete storage schema aligned to the approved interface and modeling decisions:
- relational (SQLite), not graph DB, for v1;
- no mutable truth/accuracy score;
- `solution` and `failed_tactic` are regular memories;
- direct problem-to-attempt linking via `problem_attempts`;
- fact changes represented as immutable chain links that produce a current fact snapshot;
- formal associations represented by explicit edges + immutable edge observations;
- work-session partitioning with immutable per-session episodic events and transfer metadata.

## Authoritative vs derived

- Authoritative: immutable records/tables (`memories`, links, observations, episodes/events/transfers, evidence refs).
- Derived: query-time or materialized views (`current_fact_snapshot`, `global_utility`, dependency counts).

## SQL DDL

```sql
PRAGMA foreign_keys = ON;

-- 1) Core immutable memory records
CREATE TABLE memories (
  id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL,
  scope TEXT NOT NULL CHECK (scope IN ('repo', 'global')),
  kind TEXT NOT NULL CHECK (kind IN (
    'problem', 'solution', 'failed_tactic', 'fact', 'preference', 'change'
  )),
  text TEXT NOT NULL,
  create_confidence REAL CHECK (create_confidence >= 0 AND create_confidence <= 1),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1))
);

CREATE INDEX idx_memories_repo_scope_kind ON memories(repo_id, scope, kind);
CREATE INDEX idx_memories_created_at ON memories(created_at);

-- 2) Embeddings (derived cache, linked per memory)
CREATE TABLE memory_embeddings (
  memory_id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
  model TEXT NOT NULL,
  dim INTEGER NOT NULL CHECK (dim > 0),
  vector BLOB NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- 3) Direct problem -> attempt links (no scenario table)
CREATE TABLE problem_attempts (
  problem_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  attempt_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('solution', 'failed_tactic')),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  PRIMARY KEY (problem_id, attempt_id)
);

CREATE INDEX idx_problem_attempts_problem ON problem_attempts(problem_id);
CREATE INDEX idx_problem_attempts_attempt ON problem_attempts(attempt_id);

-- 4) Fact update chain: old fact + change memory -> new fact
CREATE TABLE fact_updates (
  id TEXT PRIMARY KEY,
  old_fact_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  change_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  new_fact_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (old_fact_id, change_id, new_fact_id)
);

CREATE INDEX idx_fact_updates_old_fact ON fact_updates(old_fact_id);
CREATE INDEX idx_fact_updates_new_fact ON fact_updates(new_fact_id);

-- 5) Formal association edges (explicit + learned, bounded relation types)
CREATE TABLE association_edges (
  id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL,
  from_memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  to_memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  relation_type TEXT NOT NULL CHECK (relation_type IN ('depends_on', 'associated_with')),
  source_mode TEXT NOT NULL DEFAULT 'agent' CHECK (source_mode IN ('agent', 'implicit', 'mixed')),
  state TEXT NOT NULL DEFAULT 'tentative' CHECK (state IN ('tentative', 'confirmed', 'deprecated')),
  strength REAL NOT NULL DEFAULT 0 CHECK (strength >= 0 AND strength <= 1),
  obs_count INTEGER NOT NULL DEFAULT 0 CHECK (obs_count >= 0),
  positive_obs INTEGER NOT NULL DEFAULT 0 CHECK (positive_obs >= 0),
  negative_obs INTEGER NOT NULL DEFAULT 0 CHECK (negative_obs >= 0),
  salience_sum REAL NOT NULL DEFAULT 0 CHECK (salience_sum >= 0),
  last_reinforced_at TEXT,
  last_used_at TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  CHECK (from_memory_id <> to_memory_id),
  UNIQUE (repo_id, from_memory_id, to_memory_id, relation_type)
);

CREATE INDEX idx_assoc_edges_from ON association_edges(repo_id, from_memory_id, relation_type, state, strength);
CREATE INDEX idx_assoc_edges_to ON association_edges(repo_id, to_memory_id, relation_type, state, strength);

-- 6) Immutable association observations (reinforcement events)
CREATE TABLE association_observations (
  id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL,
  edge_id TEXT REFERENCES association_edges(id) ON DELETE CASCADE,
  from_memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  to_memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  relation_type TEXT NOT NULL CHECK (relation_type IN ('depends_on', 'associated_with')),
  source TEXT NOT NULL CHECK (source IN ('agent_explicit', 'implicit_coactivation', 'agent_feedback')),
  problem_id TEXT REFERENCES memories(id) ON DELETE SET NULL,
  episode_id TEXT REFERENCES episodes(id) ON DELETE SET NULL,
  valence REAL NOT NULL CHECK (valence >= -1 AND valence <= 1),
  salience REAL NOT NULL DEFAULT 0.5 CHECK (salience >= 0 AND salience <= 1),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  CHECK (from_memory_id <> to_memory_id)
);

CREATE INDEX idx_assoc_obs_pair_time ON association_observations(repo_id, from_memory_id, to_memory_id, created_at);
CREATE INDEX idx_assoc_obs_problem ON association_observations(repo_id, problem_id, created_at);
CREATE INDEX idx_assoc_obs_episode ON association_observations(repo_id, episode_id, created_at);

-- 7) Utility observations by retrieved memory and problem context
CREATE TABLE utility_observations (
  id TEXT PRIMARY KEY,
  memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  problem_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  vote REAL NOT NULL CHECK (vote >= -1 AND vote <= 1),
  rationale TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX idx_utility_obs_memory ON utility_observations(memory_id);
CREATE INDEX idx_utility_obs_problem ON utility_observations(problem_id);
CREATE INDEX idx_utility_obs_created_at ON utility_observations(created_at);

-- 8) Episodes (work-session container + metadata)
CREATE TABLE episodes (
  id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL,
  thread_id TEXT,
  title TEXT,
  objective TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed', 'archived')),
  started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  ended_at TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX idx_episodes_repo_status_started ON episodes(repo_id, status, started_at);
CREATE INDEX idx_episodes_repo_thread ON episodes(repo_id, thread_id);

-- 9) Immutable episodic events (one row per message/tool call)
CREATE TABLE episode_events (
  id TEXT PRIMARY KEY,
  episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL CHECK (seq > 0),
  source TEXT NOT NULL CHECK (source IN ('user', 'assistant', 'tool', 'system')),
  content TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (episode_id, seq)
);

CREATE INDEX idx_episode_events_episode_created ON episode_events(episode_id, created_at);

-- 10) Immutable cross-session transfer log
CREATE TABLE session_transfers (
  id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL,
  from_episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  to_episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  event_id TEXT NOT NULL REFERENCES episode_events(id) ON DELETE CASCADE,
  transfer_kind TEXT NOT NULL CHECK (transfer_kind IN (
    'message_handoff', 'context_summary', 'task_split', 'task_merge'
  )),
  rationale TEXT,
  transferred_by TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (from_episode_id, to_episode_id, event_id, transfer_kind)
);

CREATE INDEX idx_session_transfers_from ON session_transfers(from_episode_id, created_at);
CREATE INDEX idx_session_transfers_to ON session_transfers(to_episode_id, created_at);
CREATE INDEX idx_session_transfers_event ON session_transfers(event_id);

-- 11) Evidence references and many-to-many links
CREATE TABLE evidence_refs (
  id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL,
  ref TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE UNIQUE INDEX uq_evidence_repo_ref ON evidence_refs(repo_id, ref);

CREATE TABLE memory_evidence (
  memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  evidence_id TEXT NOT NULL REFERENCES evidence_refs(id) ON DELETE CASCADE,
  PRIMARY KEY (memory_id, evidence_id)
);

CREATE INDEX idx_memory_evidence_evidence ON memory_evidence(evidence_id);

CREATE TABLE association_edge_evidence (
  edge_id TEXT NOT NULL REFERENCES association_edges(id) ON DELETE CASCADE,
  evidence_id TEXT NOT NULL REFERENCES evidence_refs(id) ON DELETE CASCADE,
  PRIMARY KEY (edge_id, evidence_id)
);

CREATE INDEX idx_assoc_edge_evidence_evidence ON association_edge_evidence(evidence_id);
```

## Derived views

```sql
-- Facts that have not been superseded by a newer fact in the chain
CREATE VIEW current_fact_snapshot AS
SELECT m.*
FROM memories m
WHERE m.kind = 'fact'
  AND m.archived = 0
  AND NOT EXISTS (
    SELECT 1
    FROM fact_updates fu
    WHERE fu.old_fact_id = m.id
  );

-- Computed global utility prior (can later add recency weighting)
CREATE VIEW global_utility AS
SELECT
  memory_id,
  AVG(vote) AS utility_mean,
  COUNT(*) AS observations
FROM utility_observations
GROUP BY memory_id;

-- Number of memories that each memory directly depends on
CREATE VIEW direct_dependency_counts AS
SELECT
  repo_id,
  from_memory_id AS memory_id,
  COUNT(*) AS dependency_count
FROM association_edges
WHERE relation_type = 'depends_on' AND state != 'deprecated'
GROUP BY repo_id, from_memory_id;

-- Number of direct dependents per memory
CREATE VIEW direct_dependent_counts AS
SELECT
  repo_id,
  to_memory_id AS memory_id,
  COUNT(*) AS dependent_count
FROM association_edges
WHERE relation_type = 'depends_on' AND state != 'deprecated'
GROUP BY repo_id, to_memory_id;
```

## Semantic invariants (enforced in interface validation, optional DB triggers)

- `problem_attempts.problem_id` must reference `memories.kind = 'problem'`.
- `problem_attempts.attempt_id` must reference:
  - `kind = 'solution'` when `role = 'solution'`,
  - `kind = 'failed_tactic'` when `role = 'failed_tactic'`.
- `fact_updates` requires:
  - `old_fact_id` and `new_fact_id` with `kind = 'fact'`,
  - `change_id` with `kind = 'change'`.
- `association_edges` requires:
  - `from_memory_id` and `to_memory_id` exist in same `repo_id` visibility domain,
  - `from_memory_id != to_memory_id`,
  - relation type in (`depends_on`, `associated_with`).
- `association_observations` should reference an existing `association_edges.id` when observation corresponds to an upserted edge.
- `association_observations.problem_id` should reference a `kind = 'problem'` memory when present.
- `utility_observations.problem_id` should reference a `kind = 'problem'` memory.
- `episode_events.episode_id` must reference a valid `episodes.id`; `seq` is unique per episode.
- `session_transfers.from_episode_id` and `session_transfers.to_episode_id` should be different session IDs.
- `session_transfers.event_id` should reference an event that belongs to `from_episode_id`.

## Why no truth score in v1

- Fact correctness changes are represented by immutable `fact_updates` that yield newer facts.
- Current truth is the snapshot view (`current_fact_snapshot`), not a mutable truth/accuracy scalar.
- This keeps provenance clear and avoids unnecessary uncertainty machinery in early versions.
