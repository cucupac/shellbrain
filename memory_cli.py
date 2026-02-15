#!/usr/bin/env python3
"""Local-first memory system implementing phases 1-5 of plan C.

This module provides:
- Canonical append-only episodes + events
- Reducer-backed card projections and consolidation
- Retrieval/search + deterministic pack snapshots + exposures
- Dispute lifecycle + outcome attribution + utility stats
- Operational hardening: status, rebuilds, recovery checks, migration, gates
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_DB = ".memory/memory.db"
SCHEMA_VERSION = 1
RULE_VERSION = "v1"

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "has",
    "have",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "with",
    "you",
    "your",
    "i",
    "we",
    "this",
    "those",
    "these",
}

KINDS = [
    "preference",
    "constraint",
    "commitment",
    "fact",
    "tactic",
    "negative_result",
]

NORMATIVE_KINDS = {"preference", "constraint", "commitment"}

KIND_PRIORITY = {
    "constraint": 0,
    "commitment": 1,
    "preference": 2,
    "negative_result": 3,
    "tactic": 4,
    "fact": 5,
}

BUDGET_CAPS = {
    "repo": {
        "preference": 80,
        "constraint": 120,
        "commitment": 120,
        "fact": 300,
        "tactic": 120,
        "negative_result": 120,
    },
    "domain": {
        "preference": 40,
        "constraint": 60,
        "commitment": 60,
        "fact": 180,
        "tactic": 80,
        "negative_result": 80,
    },
    "global": {
        "preference": 20,
        "constraint": 30,
        "commitment": 30,
        "fact": 100,
        "tactic": 40,
        "negative_result": 40,
    },
}

EPISODE_KIND_CAPS = {
    "fact": 4,
    "tactic": 2,
    "negative_result": 2,
    "preference": 2,
    "constraint": 1,
    "commitment": 1,
}

EPISODE_SOFT_CAP = 12

DISPUTE_WEIGHTS = {
    "tool_output": 1.0,
    "doc_span": 0.7,
    "user_span": 0.4,
}

DISPUTE_THRESHOLDS = {
    "repo": 2.0,
    "domain": 3.0,
    "global": 4.0,
}

PACK_TOTAL_CAP = 8
PACK_SLOT_CAPS = {
    "constraints_commitments": 3,
    "negative_result": 2,
    "tactic": 2,
    "fact": 3,
}
PACK_TOPIC_CAP = 2

TERMINAL_OUTCOMES = {
    "tool_success",
    "tool_failure",
    "user_confirmed_helpful",
    "user_corrected",
}

# Phase 5 operator defaults
DEFAULT_TREND_DAYS = 30
GATE_MIN_SAMPLE_EPISODES = 10
GATE_MIN_EVENTS_7D = 100
GATE_MIN_PRECISION_PROXY = 0.65
GATE_MAX_CORRECTION_RATE = 0.30
GATE_MAX_BOUNDEDNESS_GROWTH_RATIO = 0.20
GATE_PLATEAU_DELTA = 0.05


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def deterministic_id(prefix: str, *parts: str, size: int = 16) -> str:
    src = "|".join(parts)
    return f"{prefix}_{sha256_text(src)[:size]}"


def tokenize(text: str) -> List[str]:
    raw = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [t for t in raw if t not in STOPWORDS]


def normalize_statement(text: str, max_len: int = 280) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def jaccard_similarity(a: str, b: str) -> float:
    ta = set(tokenize(a))
    tb = set(tokenize(b))
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def cosine_similarity_text(a: str, b: str) -> float:
    ca = Counter(tokenize(a))
    cb = Counter(tokenize(b))
    if not ca or not cb:
        return 0.0
    common = set(ca.keys()) & set(cb.keys())
    dot = sum(ca[t] * cb[t] for t in common)
    na = sum(v * v for v in ca.values()) ** 0.5
    nb = sum(v * v for v in cb.values()) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def pseudo_embedding(text: str, dim: int = 64, salt: str = "pseudo-v1") -> List[float]:
    vec = [0.0] * dim
    for tok in tokenize(text):
        h = int(hashlib.md5(f"{salt}:{tok}".encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        vec[idx] += 1.0
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def cosine_from_vectors(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def contains_failure_signal(text: str) -> bool:
    t = (text or "").lower()
    signals = ["error", "failed", "exception", "traceback", "non-zero", "timeout", "panic"]
    return any(s in t for s in signals)


def topic_key(statement: str) -> str:
    tokens = tokenize(statement)
    for tok in tokens:
        if len(tok) >= 4:
            return tok
    return tokens[0] if tokens else "general"


@dataclass
class Candidate:
    candidate_id: str
    kind: str
    statement: str
    scope_tier: str
    scope_id: str
    topic_key: str
    evidence_ref_ids: List[str]


class MemoryEngine:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS episodes (
              episode_id TEXT PRIMARY KEY,
              user_text TEXT NOT NULL,
              assistant_text TEXT NOT NULL,
              model_name TEXT,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              payload_hash TEXT NOT NULL,
              started_at TEXT NOT NULL,
              ended_at TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS artifacts (
              artifact_id TEXT PRIMARY KEY,
              episode_id TEXT NOT NULL REFERENCES episodes(episode_id),
              artifact_kind TEXT NOT NULL CHECK (artifact_kind IN ('tool_output', 'doc')),
              content_path TEXT NOT NULL,
              content_hash TEXT NOT NULL,
              mime_type TEXT,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS evidence_refs (
              evidence_ref_id TEXT PRIMARY KEY,
              episode_id TEXT NOT NULL REFERENCES episodes(episode_id),
              artifact_id TEXT REFERENCES artifacts(artifact_id),
              ref_kind TEXT NOT NULL CHECK (ref_kind IN ('user_span', 'tool_output', 'doc_span')),
              target_id TEXT NOT NULL,
              start_offset INTEGER,
              end_offset INTEGER,
              line_start INTEGER,
              line_end INTEGER,
              excerpt_text TEXT,
              ref_hash TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS memory_events (
              event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              episode_id TEXT NOT NULL REFERENCES episodes(episode_id),
              seq_no INTEGER NOT NULL,
              event_type TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              payload_hash TEXT NOT NULL,
              idempotency_key TEXT NOT NULL UNIQUE,
              producer TEXT NOT NULL,
              rule_version TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE (episode_id, seq_no)
            );

            CREATE INDEX IF NOT EXISTS idx_memory_events_episode ON memory_events (episode_id, seq_no);
            CREATE INDEX IF NOT EXISTS idx_memory_events_type ON memory_events (event_type, created_at);

            CREATE TABLE IF NOT EXISTS cards (
              card_id TEXT PRIMARY KEY,
              kind TEXT NOT NULL CHECK (kind IN ('preference', 'constraint', 'commitment', 'fact', 'tactic', 'negative_result')),
              statement TEXT NOT NULL,
              scope_tier TEXT NOT NULL CHECK (scope_tier IN ('repo', 'domain', 'global')),
              scope_id TEXT NOT NULL,
              topic_key TEXT NOT NULL,
              tags_json TEXT NOT NULL DEFAULT '[]',
              status TEXT NOT NULL CHECK (status IN ('active', 'needs_recheck', 'deprecated', 'archived')),
              supersedes_card_id TEXT REFERENCES cards(card_id),
              created_event_id INTEGER NOT NULL,
              updated_event_id INTEGER NOT NULL,
              archived_at TEXT
            );

            CREATE TABLE IF NOT EXISTS card_evidence_refs (
              card_id TEXT NOT NULL REFERENCES cards(card_id),
              evidence_ref_id TEXT NOT NULL REFERENCES evidence_refs(evidence_ref_id),
              PRIMARY KEY (card_id, evidence_ref_id)
            );

            CREATE TABLE IF NOT EXISTS consolidation_decisions (
              decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id INTEGER NOT NULL,
              episode_id TEXT NOT NULL,
              candidate_id TEXT,
              action TEXT NOT NULL,
              reason_code TEXT,
              details_json TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS consolidation_ledger (
              episode_id TEXT PRIMARY KEY,
              proposed_count INTEGER NOT NULL,
              admitted_count INTEGER NOT NULL,
              rejected_count INTEGER NOT NULL,
              merged_count INTEGER NOT NULL,
              superseded_count INTEGER NOT NULL,
              archived_count INTEGER NOT NULL,
              reason_breakdown_json TEXT NOT NULL,
              computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS cards_fts USING fts5(
              card_id UNINDEXED,
              statement,
              topic_key,
              tags,
              tokenize='porter unicode61'
            );

            CREATE TABLE IF NOT EXISTS card_embeddings (
              card_id TEXT PRIMARY KEY REFERENCES cards(card_id),
              embedding_model TEXT NOT NULL,
              embedding_vector TEXT NOT NULL,
              updated_event_id INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pack_snapshots (
              pack_id TEXT PRIMARY KEY,
              episode_id TEXT NOT NULL REFERENCES episodes(episode_id),
              channel TEXT NOT NULL CHECK (channel IN ('auto_pack', 'search', 'explicit_read', 'check')),
              query_text TEXT,
              policy_version TEXT NOT NULL,
              ranked_candidates_json TEXT NOT NULL,
              selected_cards_json TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS exposures (
              exposure_id TEXT PRIMARY KEY,
              episode_id TEXT NOT NULL REFERENCES episodes(episode_id),
              pack_id TEXT REFERENCES pack_snapshots(pack_id),
              card_id TEXT NOT NULL REFERENCES cards(card_id),
              channel TEXT NOT NULL CHECK (channel IN ('auto_pack', 'search', 'explicit_read', 'check')),
              rank_position INTEGER,
              score_total REAL,
              source_event_id INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS disputes (
              dispute_id TEXT PRIMARY KEY,
              card_id TEXT NOT NULL REFERENCES cards(card_id),
              evidence_ref_id TEXT NOT NULL REFERENCES evidence_refs(evidence_ref_id),
              weight REAL NOT NULL,
              event_id INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS card_status_history (
              card_id TEXT NOT NULL REFERENCES cards(card_id),
              event_id INTEGER NOT NULL,
              from_status TEXT NOT NULL,
              to_status TEXT NOT NULL,
              reason_code TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (card_id, event_id)
            );

            CREATE TABLE IF NOT EXISTS outcomes (
              event_id INTEGER PRIMARY KEY,
              episode_id TEXT NOT NULL REFERENCES episodes(episode_id),
              outcome_type TEXT NOT NULL,
              evidence_ref_ids_json TEXT NOT NULL,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS utility_stats (
              card_id TEXT PRIMARY KEY REFERENCES cards(card_id),
              wins INTEGER NOT NULL DEFAULT 0,
              losses INTEGER NOT NULL DEFAULT 0,
              reuse INTEGER NOT NULL DEFAULT 0,
              updated_event_id INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cards_scope_kind ON cards (scope_tier, scope_id, kind, status);
            CREATE INDEX IF NOT EXISTS idx_exposures_episode ON exposures (episode_id, channel, created_at);
            CREATE INDEX IF NOT EXISTS idx_outcomes_episode ON outcomes (episode_id, created_at);
            """
        )
        self.conn.commit()

    # ----------------------------
    # Canonical log write path
    # ----------------------------

    def record_episode_from_file(self, input_path: str, producer: str = "cli") -> Dict[str, Any]:
        with open(input_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return self.record_episode(payload, producer=producer)

    def record_episode(self, payload: Dict[str, Any], producer: str = "cli") -> Dict[str, Any]:
        episode_id = payload.get("episode_id") or f"ep_{uuid.uuid4().hex[:16]}"
        user_text = payload.get("user_text", "")
        assistant_text = payload.get("assistant_text", "")
        model_name = payload.get("model_name")
        started_at = payload.get("started_at") or now_iso()
        ended_at = payload.get("ended_at") or now_iso()
        metadata = payload.get("metadata", {})
        artifacts = payload.get("artifacts", [])
        evidence_refs = payload.get("evidence_refs", [])

        canon = {
            "episode_id": episode_id,
            "user_text": user_text,
            "assistant_text": assistant_text,
            "model_name": model_name,
            "metadata": metadata,
            "started_at": started_at,
            "ended_at": ended_at,
        }
        payload_hash = sha256_text(canonical_json(canon))

        with self.conn:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO episodes (
                  episode_id, user_text, assistant_text, model_name, metadata_json,
                  payload_hash, started_at, ended_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode_id,
                    user_text,
                    assistant_text,
                    model_name,
                    canonical_json(metadata),
                    payload_hash,
                    started_at,
                    ended_at,
                ),
            )

            self.append_event(
                episode_id=episode_id,
                event_type="episode_recorded",
                payload={
                    "schema_version": SCHEMA_VERSION,
                    "episode_id": episode_id,
                    "payload_hash": payload_hash,
                },
                idempotency_key=f"episode_recorded:{episode_id}:{payload_hash}",
                producer=producer,
                rule_version=RULE_VERSION,
                apply=True,
            )

            for i, art in enumerate(artifacts):
                artifact_id = art.get("artifact_id") or f"art_{uuid.uuid4().hex[:16]}"
                artifact_kind = art.get("artifact_kind", "tool_output")
                mime_type = art.get("mime_type", "text/plain")
                art_meta = art.get("metadata", {})
                content = art.get("content", "")
                content_path = art.get("content_path")
                if not content_path:
                    art_dir = os.path.join(os.path.dirname(self.db_path), "artifacts")
                    os.makedirs(art_dir, exist_ok=True)
                    content_path = os.path.join(art_dir, f"{artifact_id}.txt")
                    with open(content_path, "w", encoding="utf-8") as f:
                        f.write(content)
                elif content and not os.path.exists(content_path):
                    os.makedirs(os.path.dirname(content_path), exist_ok=True)
                    with open(content_path, "w", encoding="utf-8") as f:
                        f.write(content)

                if content:
                    content_hash = sha256_text(content)
                else:
                    if os.path.exists(content_path):
                        with open(content_path, "r", encoding="utf-8") as f:
                            content_hash = sha256_text(f.read())
                    else:
                        content_hash = sha256_text("")

                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO artifacts (
                      artifact_id, episode_id, artifact_kind, content_path,
                      content_hash, mime_type, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        episode_id,
                        artifact_kind,
                        content_path,
                        content_hash,
                        mime_type,
                        canonical_json(art_meta),
                    ),
                )

                self.append_event(
                    episode_id=episode_id,
                    event_type="artifact_recorded",
                    payload={
                        "schema_version": SCHEMA_VERSION,
                        "artifact_id": artifact_id,
                        "artifact_kind": artifact_kind,
                        "content_hash": content_hash,
                    },
                    idempotency_key=f"artifact_recorded:{episode_id}:{artifact_id}:{content_hash}",
                    producer=producer,
                    rule_version=RULE_VERSION,
                    apply=True,
                )

            for i, ref in enumerate(evidence_refs):
                evidence_ref_id = ref.get("evidence_ref_id") or f"ev_{uuid.uuid4().hex[:16]}"
                ref_kind = ref.get("ref_kind", "user_span")
                artifact_id = ref.get("artifact_id")
                target_id = ref.get("target_id") or (artifact_id or "episode")
                start_offset = ref.get("start_offset")
                end_offset = ref.get("end_offset")
                line_start = ref.get("line_start")
                line_end = ref.get("line_end")
                excerpt_text = ref.get("excerpt_text")
                if not excerpt_text:
                    excerpt_text = self.extract_evidence_excerpt(
                        episode_id=episode_id,
                        ref_kind=ref_kind,
                        artifact_id=artifact_id,
                        start_offset=start_offset,
                        end_offset=end_offset,
                        line_start=line_start,
                        line_end=line_end,
                    )
                ref_hash = sha256_text(excerpt_text or f"{target_id}:{start_offset}:{end_offset}:{line_start}:{line_end}")

                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO evidence_refs (
                      evidence_ref_id, episode_id, artifact_id, ref_kind, target_id,
                      start_offset, end_offset, line_start, line_end, excerpt_text, ref_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evidence_ref_id,
                        episode_id,
                        artifact_id,
                        ref_kind,
                        target_id,
                        start_offset,
                        end_offset,
                        line_start,
                        line_end,
                        excerpt_text,
                        ref_hash,
                    ),
                )

                self.append_event(
                    episode_id=episode_id,
                    event_type="evidence_ref_recorded",
                    payload={
                        "schema_version": SCHEMA_VERSION,
                        "evidence_ref_id": evidence_ref_id,
                        "ref_kind": ref_kind,
                        "ref_hash": ref_hash,
                    },
                    idempotency_key=f"evidence_ref_recorded:{episode_id}:{evidence_ref_id}:{ref_hash}",
                    producer=producer,
                    rule_version=RULE_VERSION,
                    apply=True,
                )

            self.append_event(
                episode_id=episode_id,
                event_type="consolidation_triggered",
                payload={
                    "schema_version": SCHEMA_VERSION,
                    "episode_id": episode_id,
                    "trigger": "post_episode_record",
                },
                idempotency_key=f"consolidation_triggered:{episode_id}",
                producer=producer,
                rule_version=RULE_VERSION,
                apply=True,
            )

        return {"episode_id": episode_id, "artifacts": len(artifacts), "evidence_refs": len(evidence_refs)}

    def extract_evidence_excerpt(
        self,
        episode_id: str,
        ref_kind: str,
        artifact_id: Optional[str],
        start_offset: Optional[int],
        end_offset: Optional[int],
        line_start: Optional[int],
        line_end: Optional[int],
    ) -> str:
        if ref_kind == "user_span":
            row = self.conn.execute("SELECT user_text FROM episodes WHERE episode_id = ?", (episode_id,)).fetchone()
            if not row:
                return ""
            text = row["user_text"]
            if start_offset is not None and end_offset is not None:
                return text[start_offset:end_offset]
            return text[:280]

        if artifact_id:
            row = self.conn.execute(
                "SELECT content_path FROM artifacts WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
            if row and row["content_path"] and os.path.exists(row["content_path"]):
                with open(row["content_path"], "r", encoding="utf-8") as f:
                    content = f.read()
                if line_start is not None and line_end is not None:
                    lines = content.splitlines()
                    s = max(1, line_start)
                    e = max(s, line_end)
                    return "\n".join(lines[s - 1 : e])[:280]
                if start_offset is not None and end_offset is not None:
                    return content[start_offset:end_offset]
                return content[:280]
        return ""

    def append_event(
        self,
        episode_id: str,
        event_type: str,
        payload: Dict[str, Any],
        idempotency_key: str,
        producer: str,
        rule_version: str,
        apply: bool = True,
    ) -> Dict[str, Any]:
        payload_json = canonical_json(payload)
        payload_hash = sha256_text(payload_json)
        with self.conn:
            row = self.conn.execute(
                "SELECT event_id, episode_id, seq_no FROM memory_events WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row:
                return {
                    "event_id": row["event_id"],
                    "episode_id": row["episode_id"],
                    "seq_no": row["seq_no"],
                    "inserted": False,
                }

            seq_row = self.conn.execute(
                "SELECT COALESCE(MAX(seq_no), 0) + 1 AS next_seq FROM memory_events WHERE episode_id = ?",
                (episode_id,),
            ).fetchone()
            seq_no = seq_row["next_seq"]

            cur = self.conn.execute(
                """
                INSERT INTO memory_events (
                  episode_id, seq_no, event_type, payload_json, payload_hash,
                  idempotency_key, producer, rule_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode_id,
                    seq_no,
                    event_type,
                    payload_json,
                    payload_hash,
                    idempotency_key,
                    producer,
                    rule_version,
                ),
            )
            event_id = cur.lastrowid
            created_row = self.conn.execute(
                "SELECT created_at FROM memory_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            created_at = created_row["created_at"] if created_row else now_iso()

            if apply:
                self.apply_event(event_id, episode_id, event_type, payload, event_created_at=created_at)

            return {
                "event_id": event_id,
                "episode_id": episode_id,
                "seq_no": seq_no,
                "inserted": True,
            }

    # ----------------------------
    # Reducer/event application
    # ----------------------------

    def apply_event(
        self,
        event_id: int,
        episode_id: str,
        event_type: str,
        payload: Dict[str, Any],
        event_created_at: Optional[str] = None,
    ) -> None:
        event_ts = event_created_at or now_iso()
        if event_type in {
            "candidate_proposed",
            "card_rejected",
            "card_admitted",
            "card_merged",
            "card_superseded",
            "card_archived",
        }:
            self.apply_consolidation_event(event_id, episode_id, event_type, payload, event_created_at=event_ts)
            self.refresh_ledger(episode_id)
            if event_type in {"card_admitted", "card_merged", "card_superseded", "card_archived"}:
                card_ids = []
                if payload.get("card", {}).get("card_id"):
                    card_ids.append(payload["card"]["card_id"])
                for k in ("target_card_id", "old_card_id", "new_card_id", "card_id"):
                    if payload.get(k):
                        card_ids.append(payload[k])
                for cid in sorted(set(card_ids)):
                    self.refresh_card_indices(cid, event_id)
            return

        if event_type == "card_status_changed":
            card_id = payload["card_id"]
            from_status = payload["from_status"]
            to_status = payload["to_status"]
            reason_code = payload.get("reason_code", "status_change")
            self.conn.execute(
                "UPDATE cards SET status = ?, updated_event_id = ? WHERE card_id = ?",
                (to_status, event_id, card_id),
            )
            self.conn.execute(
                """
                INSERT OR REPLACE INTO card_status_history (
                  card_id, event_id, from_status, to_status, reason_code, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (card_id, event_id, from_status, to_status, reason_code, event_ts),
            )
            self.refresh_card_indices(card_id, event_id)
            return

        if event_type == "card_deprecated":
            card_id = payload["card_id"]
            row = self.conn.execute(
                "SELECT status FROM cards WHERE card_id = ?", (card_id,)
            ).fetchone()
            from_status = row["status"] if row else "active"
            self.conn.execute(
                "UPDATE cards SET status = 'deprecated', updated_event_id = ? WHERE card_id = ?",
                (event_id, card_id),
            )
            self.conn.execute(
                """
                INSERT OR REPLACE INTO card_status_history (
                  card_id, event_id, from_status, to_status, reason_code, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    card_id,
                    event_id,
                    from_status,
                    "deprecated",
                    payload.get("reason_code", "deprecated"),
                    event_ts,
                ),
            )
            self.refresh_card_indices(card_id, event_id)
            return

        if event_type == "dispute_recorded":
            self.conn.execute(
                """
                INSERT OR REPLACE INTO disputes (dispute_id, card_id, evidence_ref_id, weight, event_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["dispute_id"],
                    payload["card_id"],
                    payload["evidence_ref_id"],
                    payload["weight"],
                    event_id,
                    event_ts,
                ),
            )
            return

        if event_type == "exposure_recorded":
            snap = payload["pack_snapshot"]
            self.conn.execute(
                """
                INSERT OR REPLACE INTO pack_snapshots (
                  pack_id, episode_id, channel, query_text, policy_version,
                  ranked_candidates_json, selected_cards_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snap["pack_id"],
                    episode_id,
                    snap["channel"],
                    snap.get("query_text", ""),
                    snap.get("policy_version", RULE_VERSION),
                    canonical_json(snap["ranked_candidates"]),
                    canonical_json(snap["selected_cards"]),
                    event_ts,
                ),
            )
            for exp in payload.get("exposures", []):
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO exposures (
                      exposure_id, episode_id, pack_id, card_id, channel,
                      rank_position, score_total, source_event_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        exp["exposure_id"],
                        episode_id,
                        snap["pack_id"],
                        exp["card_id"],
                        exp["channel"],
                        exp["rank_position"],
                        exp["score_total"],
                        event_id,
                        event_ts,
                    ),
                )
            self.recompute_utility_projection()
            return

        if event_type == "outcome_recorded":
            self.conn.execute(
                """
                INSERT OR REPLACE INTO outcomes (
                  event_id, episode_id, outcome_type, evidence_ref_ids_json, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    episode_id,
                    payload["outcome_type"],
                    canonical_json(payload.get("evidence_ref_ids", [])),
                    canonical_json(payload.get("metadata_json", {})),
                    event_ts,
                ),
            )
            self.recompute_utility_projection()
            return

    def apply_consolidation_event(
        self,
        event_id: int,
        episode_id: str,
        event_type: str,
        payload: Dict[str, Any],
        event_created_at: Optional[str] = None,
    ) -> None:
        action = event_type
        candidate_id = payload.get("candidate_id")
        reason_code = payload.get("reason_code")
        event_ts = event_created_at or now_iso()

        self.conn.execute(
            """
            INSERT INTO consolidation_decisions (
              event_id, episode_id, candidate_id, action, reason_code, details_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                episode_id,
                candidate_id,
                action,
                reason_code,
                canonical_json(payload),
                event_ts,
            ),
        )

        if event_type == "card_admitted":
            card = payload["card"]
            self.conn.execute(
                """
                INSERT OR REPLACE INTO cards (
                  card_id, kind, statement, scope_tier, scope_id, topic_key,
                  tags_json, status, supersedes_card_id, created_event_id,
                  updated_event_id, archived_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                          COALESCE((SELECT created_event_id FROM cards WHERE card_id = ?), ?),
                          ?, NULL)
                """,
                (
                    card["card_id"],
                    card["kind"],
                    card["statement"],
                    card["scope_tier"],
                    card["scope_id"],
                    card["topic_key"],
                    canonical_json(card.get("tags", [])),
                    card.get("status", "active"),
                    card.get("supersedes_card_id"),
                    card["card_id"],
                    event_id,
                    event_id,
                ),
            )
            for ev_id in card.get("evidence_ref_ids", []):
                self.conn.execute(
                    "INSERT OR IGNORE INTO card_evidence_refs (card_id, evidence_ref_id) VALUES (?, ?)",
                    (card["card_id"], ev_id),
                )
            return

        if event_type == "card_merged":
            target_card_id = payload["target_card_id"]
            self.conn.execute(
                "UPDATE cards SET updated_event_id = ? WHERE card_id = ?",
                (event_id, target_card_id),
            )
            for ev_id in payload.get("evidence_ref_ids", []):
                self.conn.execute(
                    "INSERT OR IGNORE INTO card_evidence_refs (card_id, evidence_ref_id) VALUES (?, ?)",
                    (target_card_id, ev_id),
                )
            return

        if event_type == "card_superseded":
            old_card_id = payload["old_card_id"]
            self.conn.execute(
                "UPDATE cards SET status = 'deprecated', updated_event_id = ? WHERE card_id = ?",
                (event_id, old_card_id),
            )
            self.conn.execute(
                """
                INSERT OR REPLACE INTO card_status_history (
                  card_id, event_id, from_status, to_status, reason_code, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    old_card_id,
                    event_id,
                    payload.get("from_status", "active"),
                    "deprecated",
                    payload.get("reason_code", "superseded"),
                    event_ts,
                ),
            )
            return

        if event_type == "card_archived":
            card_id = payload["card_id"]
            row = self.conn.execute(
                "SELECT status FROM cards WHERE card_id = ?", (card_id,)
            ).fetchone()
            from_status = row["status"] if row else "active"
            self.conn.execute(
                "UPDATE cards SET status = 'archived', archived_at = ?, updated_event_id = ? WHERE card_id = ?",
                (event_ts, event_id, card_id),
            )
            self.conn.execute(
                """
                INSERT OR REPLACE INTO card_status_history (
                  card_id, event_id, from_status, to_status, reason_code, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    card_id,
                    event_id,
                    from_status,
                    "archived",
                    payload.get("reason_code", "archived"),
                    event_ts,
                ),
            )
            return

    def refresh_ledger(self, episode_id: str) -> None:
        rows = self.conn.execute(
            """
            SELECT event_type, payload_json
            FROM memory_events
            WHERE episode_id = ?
              AND event_type IN (
                'candidate_proposed', 'card_admitted', 'card_rejected',
                'card_merged', 'card_superseded', 'card_archived'
              )
            ORDER BY event_id
            """,
            (episode_id,),
        ).fetchall()

        counts = {
            "candidate_proposed": 0,
            "card_admitted": 0,
            "card_rejected": 0,
            "card_merged": 0,
            "card_superseded": 0,
            "card_archived": 0,
        }
        reasons: Dict[str, int] = defaultdict(int)
        for r in rows:
            counts[r["event_type"]] += 1
            payload = json.loads(r["payload_json"])
            reason = payload.get("reason_code")
            if reason:
                reasons[reason] += 1

        latest_row = self.conn.execute(
            "SELECT MAX(created_at) AS latest FROM memory_events WHERE episode_id = ?",
            (episode_id,),
        ).fetchone()
        computed_at = latest_row["latest"] if latest_row and latest_row["latest"] else now_iso()

        self.conn.execute(
            """
            INSERT OR REPLACE INTO consolidation_ledger (
              episode_id, proposed_count, admitted_count, rejected_count,
              merged_count, superseded_count, archived_count,
              reason_breakdown_json, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                episode_id,
                counts["candidate_proposed"],
                counts["card_admitted"],
                counts["card_rejected"],
                counts["card_merged"],
                counts["card_superseded"],
                counts["card_archived"],
                canonical_json(reasons),
                computed_at,
            ),
        )

    def refresh_card_indices(self, card_id: str, updated_event_id: int) -> None:
        row = self.conn.execute(
            "SELECT card_id, statement, topic_key, tags_json FROM cards WHERE card_id = ?",
            (card_id,),
        ).fetchone()
        if not row:
            return

        self.conn.execute("DELETE FROM cards_fts WHERE card_id = ?", (card_id,))
        self.conn.execute(
            "INSERT INTO cards_fts (card_id, statement, topic_key, tags) VALUES (?, ?, ?, ?)",
            (row["card_id"], row["statement"], row["topic_key"], row["tags_json"]),
        )

        model = "pseudo-v1"
        vec = pseudo_embedding(row["statement"], salt=model)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO card_embeddings (card_id, embedding_model, embedding_vector, updated_event_id)
            VALUES (?, ?, ?, ?)
            """,
            (row["card_id"], model, canonical_json(vec), updated_event_id),
        )

    # ----------------------------
    # Consolidation
    # ----------------------------

    def consolidate_episode(self, episode_id: str, producer: str = "cli") -> Dict[str, Any]:
        episode = self.conn.execute(
            "SELECT episode_id, metadata_json FROM episodes WHERE episode_id = ?", (episode_id,)
        ).fetchone()
        if not episode:
            raise ValueError(f"Episode not found: {episode_id}")

        metadata = json.loads(episode["metadata_json"] or "{}")
        scope_tier = metadata.get("scope_tier", "repo")
        scope_id = metadata.get("scope_id", "default")

        ev_rows = self.conn.execute(
            """
            SELECT evidence_ref_id, ref_kind, excerpt_text
            FROM evidence_refs
            WHERE episode_id = ?
            ORDER BY created_at, evidence_ref_id
            """,
            (episode_id,),
        ).fetchall()

        candidates = self.generate_candidates(episode_id, scope_tier, scope_id, ev_rows)
        candidates = sorted(
            candidates,
            key=lambda c: (
                KIND_PRIORITY.get(c.kind, 99),
                normalize_statement(c.statement).lower(),
                c.scope_tier,
                c.scope_id,
                c.candidate_id,
            ),
        )

        admitted = 0
        rejected = 0
        merged = 0
        superseded = 0

        admitted_by_kind = self.count_episode_admitted_by_kind(episode_id)
        admitted_total = sum(admitted_by_kind.values())

        for cand in candidates:
            self.append_event(
                episode_id=episode_id,
                event_type="candidate_proposed",
                payload={
                    "schema_version": SCHEMA_VERSION,
                    "candidate_id": cand.candidate_id,
                    "kind": cand.kind,
                    "statement": cand.statement,
                    "scope_tier": cand.scope_tier,
                    "scope_id": cand.scope_id,
                    "topic_key": cand.topic_key,
                    "evidence_ref_ids": cand.evidence_ref_ids,
                },
                idempotency_key=f"candidate_proposed:{episode_id}:{cand.candidate_id}",
                producer=producer,
                rule_version=RULE_VERSION,
                apply=True,
            )

            ok_evidence, reason = self.validate_evidence_invariant(cand)
            if not ok_evidence:
                rejected += 1
                self.append_reject(
                    episode_id,
                    cand,
                    "missing_required_evidence",
                    {"invariant_reason": reason},
                    producer,
                )
                continue

            best_match = self.find_best_similarity_match(cand)
            if best_match and best_match["lexical"] >= 0.80 and best_match["cosine"] >= 0.92:
                rejected += 1
                self.append_reject(
                    episode_id,
                    cand,
                    "duplicate_of_existing_card",
                    {
                        "matched_card_id": best_match["card_id"],
                        "lexical": best_match["lexical"],
                        "cosine": best_match["cosine"],
                    },
                    producer,
                )
                continue

            if best_match and (best_match["lexical"] >= 0.65 or best_match["cosine"] >= 0.78):
                rejected += 1
                self.append_reject(
                    episode_id,
                    cand,
                    "novelty_below_threshold",
                    {
                        "matched_card_id": best_match["card_id"],
                        "lexical": best_match["lexical"],
                        "cosine": best_match["cosine"],
                    },
                    producer,
                )
                continue

            if admitted_by_kind[cand.kind] >= EPISODE_KIND_CAPS[cand.kind]:
                rejected += 1
                self.append_reject(
                    episode_id,
                    cand,
                    "episode_kind_cap_exceeded",
                    {"kind_cap": EPISODE_KIND_CAPS[cand.kind]},
                    producer,
                )
                continue

            if admitted_total >= EPISODE_SOFT_CAP:
                rejected += 1
                self.append_reject(
                    episode_id,
                    cand,
                    "episode_soft_cap_exceeded",
                    {"soft_cap": EPISODE_SOFT_CAP},
                    producer,
                )
                continue

            active_scope_count = self.conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM cards
                WHERE scope_tier = ? AND kind = ? AND status IN ('active', 'needs_recheck')
                """,
                (cand.scope_tier, cand.kind),
            ).fetchone()["n"]
            if active_scope_count >= BUDGET_CAPS[cand.scope_tier][cand.kind]:
                rejected += 1
                self.append_reject(
                    episode_id,
                    cand,
                    "scope_kind_budget_exceeded",
                    {"budget": BUDGET_CAPS[cand.scope_tier][cand.kind]},
                    producer,
                )
                continue

            merged_target = self.find_exact_merge_target(cand)
            if merged_target:
                merged += 1
                self.append_event(
                    episode_id=episode_id,
                    event_type="card_merged",
                    payload={
                        "schema_version": SCHEMA_VERSION,
                        "candidate_id": cand.candidate_id,
                        "target_card_id": merged_target,
                        "evidence_ref_ids": cand.evidence_ref_ids,
                        "reason_code": "exact_statement_match",
                    },
                    idempotency_key=f"card_merged:{episode_id}:{cand.candidate_id}:{merged_target}",
                    producer=producer,
                    rule_version=RULE_VERSION,
                    apply=True,
                )
                continue

            supersede_target = self.find_supersede_target(cand)
            card_id = deterministic_id(
                "card",
                cand.kind,
                cand.scope_tier,
                cand.scope_id,
                normalize_statement(cand.statement).lower(),
            )

            self.append_event(
                episode_id=episode_id,
                event_type="card_admitted",
                payload={
                    "schema_version": SCHEMA_VERSION,
                    "candidate_id": cand.candidate_id,
                    "reason_code": "admitted",
                    "card": {
                        "card_id": card_id,
                        "kind": cand.kind,
                        "statement": cand.statement,
                        "scope_tier": cand.scope_tier,
                        "scope_id": cand.scope_id,
                        "topic_key": cand.topic_key,
                        "tags": [],
                        "status": "active",
                        "supersedes_card_id": supersede_target,
                        "evidence_ref_ids": cand.evidence_ref_ids,
                    },
                },
                idempotency_key=f"card_admitted:{episode_id}:{cand.candidate_id}:{card_id}",
                producer=producer,
                rule_version=RULE_VERSION,
                apply=True,
            )

            admitted += 1
            admitted_by_kind[cand.kind] += 1
            admitted_total += 1

            if supersede_target:
                superseded += 1
                prev_status = self.conn.execute(
                    "SELECT status FROM cards WHERE card_id = ?", (supersede_target,)
                ).fetchone()
                self.append_event(
                    episode_id=episode_id,
                    event_type="card_superseded",
                    payload={
                        "schema_version": SCHEMA_VERSION,
                        "candidate_id": cand.candidate_id,
                        "old_card_id": supersede_target,
                        "new_card_id": card_id,
                        "from_status": prev_status["status"] if prev_status else "active",
                        "reason_code": "normative_user_supersession",
                    },
                    idempotency_key=f"card_superseded:{episode_id}:{supersede_target}:{card_id}",
                    producer=producer,
                    rule_version=RULE_VERSION,
                    apply=True,
                )

        self.refresh_ledger(episode_id)
        ledger = self.conn.execute(
            "SELECT * FROM consolidation_ledger WHERE episode_id = ?", (episode_id,)
        ).fetchone()
        return {
            "episode_id": episode_id,
            "proposed": len(candidates),
            "admitted": admitted,
            "rejected": rejected,
            "merged": merged,
            "superseded": superseded,
            "ledger": dict(ledger) if ledger else {},
        }

    def generate_candidates(
        self,
        episode_id: str,
        scope_tier: str,
        scope_id: str,
        ev_rows: Sequence[sqlite3.Row],
    ) -> List[Candidate]:
        candidates: List[Candidate] = []
        for idx, row in enumerate(ev_rows):
            ref_id = row["evidence_ref_id"]
            ref_kind = row["ref_kind"]
            text = normalize_statement(row["excerpt_text"] or "")
            if not text:
                continue

            kind = "fact"
            low = text.lower()
            if ref_kind == "user_span":
                if any(k in low for k in ["prefer", "i like", "please use", "verbosity"]):
                    kind = "preference"
                elif any(k in low for k in ["must", "do not", "don't", "never", "always", "only"]):
                    kind = "constraint"
                elif any(k in low for k in ["i will", "i'll", "we will", "plan to", "going to"]):
                    kind = "commitment"
                else:
                    kind = "fact"
            elif ref_kind == "tool_output":
                if contains_failure_signal(text):
                    kind = "negative_result"
                elif any(k in low for k in ["run ", "command", "steps", "procedure", "workflow"]):
                    kind = "tactic"
                else:
                    kind = "fact"
            elif ref_kind == "doc_span":
                if any(k in low for k in ["run ", "steps", "procedure", "how to"]):
                    kind = "tactic"
                else:
                    kind = "fact"

            cand_id = deterministic_id(
                "cand",
                episode_id,
                str(idx),
                kind,
                normalize_statement(text).lower(),
            )
            candidates.append(
                Candidate(
                    candidate_id=cand_id,
                    kind=kind,
                    statement=text,
                    scope_tier=scope_tier,
                    scope_id=scope_id,
                    topic_key=topic_key(text),
                    evidence_ref_ids=[ref_id],
                )
            )
        return candidates

    def validate_evidence_invariant(self, cand: Candidate) -> Tuple[bool, str]:
        if not cand.evidence_ref_ids:
            return False, "missing_evidence"
        rows = self.conn.execute(
            f"SELECT ref_kind FROM evidence_refs WHERE evidence_ref_id IN ({','.join('?' for _ in cand.evidence_ref_ids)})",
            cand.evidence_ref_ids,
        ).fetchall()
        kinds = {r["ref_kind"] for r in rows}

        if cand.kind in {"preference", "constraint", "commitment"}:
            if "user_span" not in kinds:
                return False, "normative_requires_user_span"
        elif cand.kind == "tactic":
            if not ({"tool_output", "doc_span"} & kinds):
                return False, "tactic_requires_tool_or_doc"
        elif cand.kind == "negative_result":
            if "tool_output" not in kinds:
                return False, "negative_result_requires_tool_output"
            text = cand.statement.lower()
            if not contains_failure_signal(text):
                return False, "negative_result_requires_failure_signal"
        elif cand.kind == "fact":
            if not kinds:
                return False, "fact_requires_anchor"
        return True, "ok"

    def find_best_similarity_match(self, cand: Candidate) -> Optional[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT card_id, statement
            FROM cards
            WHERE kind = ? AND scope_tier = ? AND scope_id = ? AND status IN ('active', 'needs_recheck')
            """,
            (cand.kind, cand.scope_tier, cand.scope_id),
        ).fetchall()
        best: Optional[Dict[str, Any]] = None
        for r in rows:
            lex = jaccard_similarity(cand.statement, r["statement"])
            cos = cosine_similarity_text(cand.statement, r["statement"])
            score = (lex + cos) / 2
            if best is None or score > best["score"]:
                best = {
                    "card_id": r["card_id"],
                    "lexical": lex,
                    "cosine": cos,
                    "score": score,
                }
        return best

    def find_exact_merge_target(self, cand: Candidate) -> Optional[str]:
        norm = normalize_statement(cand.statement).lower()
        rows = self.conn.execute(
            """
            SELECT card_id, statement
            FROM cards
            WHERE kind = ? AND scope_tier = ? AND scope_id = ? AND status IN ('active', 'needs_recheck')
            ORDER BY updated_event_id DESC, card_id ASC
            """,
            (cand.kind, cand.scope_tier, cand.scope_id),
        ).fetchall()
        for r in rows:
            if normalize_statement(r["statement"]).lower() == norm:
                return r["card_id"]
        return None

    def find_supersede_target(self, cand: Candidate) -> Optional[str]:
        if cand.kind not in NORMATIVE_KINDS:
            return None
        rows = self.conn.execute(
            """
            SELECT card_id
            FROM cards
            WHERE kind = ? AND scope_tier = ? AND scope_id = ? AND topic_key = ? AND status IN ('active', 'needs_recheck')
            ORDER BY updated_event_id DESC, card_id ASC
            """,
            (cand.kind, cand.scope_tier, cand.scope_id, cand.topic_key),
        ).fetchall()
        if rows:
            return rows[0]["card_id"]
        return None

    def append_reject(
        self,
        episode_id: str,
        cand: Candidate,
        reason: str,
        details: Dict[str, Any],
        producer: str,
    ) -> None:
        self.append_event(
            episode_id=episode_id,
            event_type="card_rejected",
            payload={
                "schema_version": SCHEMA_VERSION,
                "candidate_id": cand.candidate_id,
                "kind": cand.kind,
                "statement": cand.statement,
                "reason_code": reason,
                "details": details,
            },
            idempotency_key=f"card_rejected:{episode_id}:{cand.candidate_id}:{reason}",
            producer=producer,
            rule_version=RULE_VERSION,
            apply=True,
        )

    def count_episode_admitted_by_kind(self, episode_id: str) -> Dict[str, int]:
        out = defaultdict(int)
        rows = self.conn.execute(
            """
            SELECT payload_json
            FROM memory_events
            WHERE episode_id = ? AND event_type = 'card_admitted'
            """,
            (episode_id,),
        ).fetchall()
        for r in rows:
            payload = json.loads(r["payload_json"])
            kind = payload.get("card", {}).get("kind")
            if kind:
                out[kind] += 1
        for k in KINDS:
            out[k] += 0
        return out

    def run_dedup_daily(self, producer: str = "cli") -> Dict[str, Any]:
        merged = 0
        groups = self.conn.execute(
            """
            SELECT kind, scope_tier, scope_id, COUNT(*) AS n
            FROM cards
            WHERE status IN ('active', 'needs_recheck')
            GROUP BY kind, scope_tier, scope_id
            HAVING n > 1
            """
        ).fetchall()

        for g in groups:
            rows = self.conn.execute(
                """
                SELECT c.card_id, c.statement, c.updated_event_id,
                       COUNT(cer.evidence_ref_id) AS evidence_count
                FROM cards c
                LEFT JOIN card_evidence_refs cer ON cer.card_id = c.card_id
                WHERE c.kind = ? AND c.scope_tier = ? AND c.scope_id = ?
                  AND c.status IN ('active', 'needs_recheck')
                GROUP BY c.card_id, c.statement, c.updated_event_id
                ORDER BY evidence_count DESC, updated_event_id DESC, card_id ASC
                """,
                (g["kind"], g["scope_tier"], g["scope_id"]),
            ).fetchall()
            if len(rows) < 2:
                continue
            winner = rows[0]
            for loser in rows[1:]:
                lex = jaccard_similarity(winner["statement"], loser["statement"])
                cos = cosine_similarity_text(winner["statement"], loser["statement"])
                if lex >= 0.80 and cos >= 0.92:
                    merged += 1
                    episode_id = self.latest_episode_for_card(loser["card_id"])
                    if not episode_id:
                        continue
                    ev_refs = [
                        r["evidence_ref_id"]
                        for r in self.conn.execute(
                            "SELECT evidence_ref_id FROM card_evidence_refs WHERE card_id = ?",
                            (loser["card_id"],),
                        ).fetchall()
                    ]
                    self.append_event(
                        episode_id=episode_id,
                        event_type="card_merged",
                        payload={
                            "schema_version": SCHEMA_VERSION,
                            "candidate_id": deterministic_id(
                                "cand", loser["card_id"], winner["card_id"], "dedup"
                            ),
                            "target_card_id": winner["card_id"],
                            "evidence_ref_ids": ev_refs,
                            "reason_code": "daily_dedup_merge",
                        },
                        idempotency_key=f"daily_dedup_merge:{winner['card_id']}:{loser['card_id']}",
                        producer=producer,
                        rule_version=RULE_VERSION,
                        apply=True,
                    )
                    self.append_event(
                        episode_id=episode_id,
                        event_type="card_archived",
                        payload={
                            "schema_version": SCHEMA_VERSION,
                            "card_id": loser["card_id"],
                            "reason_code": "daily_dedup_archived_duplicate",
                        },
                        idempotency_key=f"daily_dedup_archive:{loser['card_id']}",
                        producer=producer,
                        rule_version=RULE_VERSION,
                        apply=True,
                    )

        return {"merged": merged}

    def latest_episode_for_card(self, card_id: str) -> Optional[str]:
        row = self.conn.execute(
            """
            SELECT me.episode_id
            FROM consolidation_decisions cd
            JOIN memory_events me ON me.event_id = cd.event_id
            WHERE cd.details_json LIKE ?
            ORDER BY me.event_id DESC
            LIMIT 1
            """,
            (f"%{card_id}%",),
        ).fetchone()
        return row["episode_id"] if row else None

    # ----------------------------
    # Retrieval, packing, explain
    # ----------------------------

    def get_episode_scope(self, episode_id: str) -> Tuple[str, str]:
        row = self.conn.execute(
            "SELECT metadata_json FROM episodes WHERE episode_id = ?", (episode_id,)
        ).fetchone()
        if not row:
            return ("repo", "default")
        meta = json.loads(row["metadata_json"] or "{}")
        return (meta.get("scope_tier", "repo"), meta.get("scope_id", "default"))

    def archive_hygiene_pass(self, episode_id: str, producer: str = "cli") -> int:
        archived = 0
        threshold_days = 30
        cutoff = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=threshold_days)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        rows = self.conn.execute(
            """
            SELECT c.card_id, c.kind, c.scope_tier,
                   COALESCE(u.wins, 0) AS wins,
                   COALESCE(u.losses, 0) AS losses,
                   COALESCE(u.reuse, 0) AS reuse,
                   (
                     SELECT MAX(e.created_at) FROM exposures e WHERE e.card_id = c.card_id
                   ) AS last_exposed,
                   (
                     SELECT COALESCE(SUM(d.weight), 0.0) FROM disputes d WHERE d.card_id = c.card_id
                   ) AS dispute_mass
            FROM cards c
            LEFT JOIN utility_stats u ON u.card_id = c.card_id
            WHERE c.status = 'active'
            """
        ).fetchall()
        for r in rows:
            utility = (r["wins"] - r["losses"]) + 0.1 * r["reuse"]
            if r["dispute_mass"] > 0.0:
                continue
            if utility > 0.0:
                continue
            last_exposed = r["last_exposed"]
            # Never archive cards that have not yet been exposed at least once.
            if not last_exposed:
                continue
            if last_exposed > cutoff:
                continue
            self.append_event(
                episode_id=episode_id,
                event_type="card_archived",
                payload={
                    "schema_version": SCHEMA_VERSION,
                    "card_id": r["card_id"],
                    "reason_code": "archive_hygiene_low_signal",
                },
                idempotency_key=f"archive_hygiene:{r['card_id']}",
                producer=producer,
                rule_version=RULE_VERSION,
                apply=True,
            )
            archived += 1
        return archived

    def retrieve_cards(
        self,
        query: str,
        episode_id: Optional[str],
        include_archived: bool,
        limit: int,
        mode: str,
    ) -> List[Dict[str, Any]]:
        scope_tier, scope_id = ("repo", "default")
        if episode_id:
            scope_tier, scope_id = self.get_episode_scope(episode_id)

        query_vec_cache: Dict[str, List[float]] = {}
        status_clause = "status IN ('active', 'needs_recheck')"
        if include_archived or mode != "auto_pack":
            status_clause = "status IN ('active', 'needs_recheck', 'deprecated', 'archived')"

        rows = self.conn.execute(
            f"""
            SELECT c.card_id, c.kind, c.statement, c.scope_tier, c.scope_id, c.topic_key,
                   c.status, c.updated_event_id,
                   COALESCE(u.wins, 0) AS wins,
                   COALESCE(u.losses, 0) AS losses,
                   COALESCE(u.reuse, 0) AS reuse,
                   COALESCE(ce.embedding_model, 'pseudo-v1') AS embedding_model,
                   COALESCE(ce.embedding_vector, '[]') AS embedding_vector
            FROM cards c
            LEFT JOIN utility_stats u ON u.card_id = c.card_id
            LEFT JOIN card_embeddings ce ON ce.card_id = c.card_id
            WHERE {status_clause}
            """
        ).fetchall()

        out: List[Dict[str, Any]] = []
        max_event_row = self.conn.execute("SELECT COALESCE(MAX(event_id), 1) AS m FROM memory_events").fetchone()
        max_event_id = max_event_row["m"]

        for r in rows:
            lexical = jaccard_similarity(query, r["statement"])
            try:
                emb = json.loads(r["embedding_vector"])
            except json.JSONDecodeError:
                emb = []
            emb_model = r["embedding_model"] or "pseudo-v1"
            if emb_model not in query_vec_cache:
                query_vec_cache[emb_model] = pseudo_embedding(query, salt=emb_model)
            semantic = cosine_from_vectors(query_vec_cache[emb_model], emb)

            scope_score = self.scope_score(scope_tier, scope_id, r["scope_tier"], r["scope_id"])
            kind_prior = self.kind_prior(r["kind"])
            truth_weight = self.status_weight(r["status"], mode)

            utility = 0.0
            if r["kind"] == "tactic":
                denom = max(1, r["wins"] + r["losses"])  # dampen small sample sizes
                utility = ((r["wins"] - r["losses"]) / denom) + min(1.0, r["reuse"] / 10.0)

            recency = float(r["updated_event_id"]) / float(max_event_id)
            score_total = (
                0.35 * lexical
                + 0.25 * semantic
                + 0.15 * scope_score
                + 0.10 * kind_prior
                + 0.10 * truth_weight
                + 0.05 * utility
                + 0.02 * recency
            )

            if mode == "auto_pack" and r["status"] == "needs_recheck":
                score_total *= 0.35

            out.append(
                {
                    "card_id": r["card_id"],
                    "kind": r["kind"],
                    "statement": r["statement"],
                    "scope_tier": r["scope_tier"],
                    "scope_id": r["scope_id"],
                    "topic_key": r["topic_key"],
                    "status": r["status"],
                    "score_total": round(score_total, 6),
                    "score_components": {
                        "lexical": round(lexical, 6),
                        "semantic": round(semantic, 6),
                        "scope": round(scope_score, 6),
                        "kind_prior": round(kind_prior, 6),
                        "truth": round(truth_weight, 6),
                        "utility": round(utility, 6),
                        "recency": round(recency, 6),
                    },
                    "updated_event_id": r["updated_event_id"],
                }
            )

        out.sort(
            key=lambda c: (
                -c["score_total"],
                KIND_PRIORITY.get(c["kind"], 99),
                -c["updated_event_id"],
                c["card_id"],
            )
        )
        return out[:limit]

    def scope_score(
        self, desired_tier: str, desired_scope_id: str, card_tier: str, card_scope_id: str
    ) -> float:
        if desired_tier == card_tier and desired_scope_id == card_scope_id:
            return 1.0
        tier_rank = {"repo": 3, "domain": 2, "global": 1}
        if tier_rank.get(card_tier, 0) > tier_rank.get(desired_tier, 0):
            return 0.2
        if card_tier == desired_tier:
            return 0.8
        if card_tier == "global":
            return 0.6
        if card_tier == "domain":
            return 0.7
        return 0.5

    def kind_prior(self, kind: str) -> float:
        return {
            "constraint": 1.0,
            "commitment": 0.9,
            "preference": 0.8,
            "negative_result": 0.85,
            "tactic": 0.8,
            "fact": 0.75,
        }.get(kind, 0.5)

    def status_weight(self, status: str, mode: str) -> float:
        if mode == "auto_pack":
            return {
                "active": 1.0,
                "needs_recheck": 0.35,
                "deprecated": 0.15,
                "archived": 0.1,
            }.get(status, 0.1)
        return {
            "active": 1.0,
            "needs_recheck": 0.8,
            "deprecated": 0.65,
            "archived": 0.6,
        }.get(status, 0.5)

    def build_pack(
        self,
        episode_id: str,
        query: str,
        channel: str = "auto_pack",
        producer: str = "cli",
    ) -> Dict[str, Any]:
        if channel not in {"auto_pack", "search", "explicit_read", "check"}:
            raise ValueError(f"Invalid channel: {channel}")

        self.archive_hygiene_pass(episode_id, producer=producer)

        ranked = self.retrieve_cards(
            query=query,
            episode_id=episode_id,
            include_archived=(channel != "auto_pack"),
            limit=200,
            mode=channel,
        )

        selected: List[Dict[str, Any]] = []
        topic_counts: Dict[str, int] = defaultdict(int)
        slot_counts = {
            "constraints_commitments": 0,
            "negative_result": 0,
            "tactic": 0,
            "fact": 0,
        }

        def group_for_kind(kind: str) -> str:
            if kind in {"constraint", "commitment", "preference"}:
                return "constraints_commitments"
            if kind == "negative_result":
                return "negative_result"
            if kind == "tactic":
                return "tactic"
            return "fact"

        has_recent_failure = self.has_recent_failure(episode_id)
        if has_recent_failure:
            for cand in ranked:
                if cand["kind"] == "negative_result" and topic_counts[cand["topic_key"]] < PACK_TOPIC_CAP:
                    group = "negative_result"
                    if slot_counts[group] < PACK_SLOT_CAPS[group]:
                        selected.append(cand)
                        slot_counts[group] += 1
                        topic_counts[cand["topic_key"]] += 1
                        break

        for cand in ranked:
            if len(selected) >= PACK_TOTAL_CAP:
                break
            if any(s["card_id"] == cand["card_id"] for s in selected):
                continue
            if topic_counts[cand["topic_key"]] >= PACK_TOPIC_CAP:
                continue

            group = group_for_kind(cand["kind"])
            if slot_counts[group] >= PACK_SLOT_CAPS[group]:
                continue

            selected.append(cand)
            slot_counts[group] += 1
            topic_counts[cand["topic_key"]] += 1

        selected = selected[:PACK_TOTAL_CAP]

        pack_id = f"pack_{uuid.uuid4().hex[:16]}"
        ranked_for_snapshot = [
            {
                "rank": idx + 1,
                "card_id": c["card_id"],
                "kind": c["kind"],
                "score_total": c["score_total"],
                "score_components": c["score_components"],
                "status": c["status"],
                "topic_key": c["topic_key"],
            }
            for idx, c in enumerate(ranked[:100])
        ]
        selected_for_snapshot = [
            {
                "rank": idx + 1,
                "card_id": c["card_id"],
                "kind": c["kind"],
                "score_total": c["score_total"],
                "status": c["status"],
                "topic_key": c["topic_key"],
                "evidence_ref_ids": self.card_evidence_ids(c["card_id"]),
            }
            for idx, c in enumerate(selected)
        ]

        exposures = []
        for idx, c in enumerate(selected):
            exposures.append(
                {
                    "exposure_id": deterministic_id("exp", pack_id, c["card_id"], str(idx + 1)),
                    "card_id": c["card_id"],
                    "channel": channel,
                    "rank_position": idx + 1,
                    "score_total": c["score_total"],
                }
            )

        payload = {
            "schema_version": SCHEMA_VERSION,
            "channel": channel,
            "pack_snapshot": {
                "pack_id": pack_id,
                "channel": channel,
                "query_text": query,
                "policy_version": RULE_VERSION,
                "ranked_candidates": ranked_for_snapshot,
                "selected_cards": selected_for_snapshot,
            },
            "exposures": exposures,
        }

        result = self.append_event(
            episode_id=episode_id,
            event_type="exposure_recorded",
            payload=payload,
            idempotency_key=f"exposure_recorded:{episode_id}:{pack_id}",
            producer=producer,
            rule_version=RULE_VERSION,
            apply=True,
        )

        return {
            "episode_id": episode_id,
            "pack_id": pack_id,
            "channel": channel,
            "event_id": result["event_id"],
            "selected_count": len(selected_for_snapshot),
            "selected_cards": selected_for_snapshot,
            "slot_counts": slot_counts,
        }

    def card_evidence_ids(self, card_id: str) -> List[str]:
        return [
            r["evidence_ref_id"]
            for r in self.conn.execute(
                "SELECT evidence_ref_id FROM card_evidence_refs WHERE card_id = ? ORDER BY evidence_ref_id",
                (card_id,),
            ).fetchall()
        ]

    def has_recent_failure(self, episode_id: str) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM outcomes
            WHERE episode_id = ? AND outcome_type = 'tool_failure'
            ORDER BY event_id DESC
            LIMIT 1
            """,
            (episode_id,),
        ).fetchone()
        return row is not None

    def explain_pack(self, episode_id: str, pack_id: Optional[str] = None) -> Dict[str, Any]:
        if pack_id:
            row = self.conn.execute(
                "SELECT * FROM pack_snapshots WHERE pack_id = ?", (pack_id,)
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT * FROM pack_snapshots
                WHERE episode_id = ?
                ORDER BY created_at DESC, pack_id DESC
                LIMIT 1
                """,
                (episode_id,),
            ).fetchone()
        if not row:
            raise ValueError("Pack snapshot not found")

        return {
            "pack_id": row["pack_id"],
            "episode_id": row["episode_id"],
            "channel": row["channel"],
            "query_text": row["query_text"],
            "policy_version": row["policy_version"],
            "ranked_candidates": json.loads(row["ranked_candidates_json"]),
            "selected_cards": json.loads(row["selected_cards_json"]),
        }

    def explain_consolidation(self, episode_id: str) -> Dict[str, Any]:
        rows = self.conn.execute(
            """
            SELECT action, reason_code, details_json, created_at
            FROM consolidation_decisions
            WHERE episode_id = ?
            ORDER BY decision_id
            """,
            (episode_id,),
        ).fetchall()
        decisions = []
        for r in rows:
            decisions.append(
                {
                    "action": r["action"],
                    "reason_code": r["reason_code"],
                    "details": json.loads(r["details_json"]),
                    "created_at": r["created_at"],
                }
            )
        ledger = self.conn.execute(
            "SELECT * FROM consolidation_ledger WHERE episode_id = ?", (episode_id,)
        ).fetchone()
        return {
            "episode_id": episode_id,
            "ledger": dict(ledger) if ledger else {},
            "decisions": decisions,
        }

    # ----------------------------
    # Phase 4: dispute/lifecycle + utility
    # ----------------------------

    def record_dispute(
        self,
        episode_id: str,
        card_id: str,
        evidence_ref_id: str,
        producer: str = "cli",
    ) -> Dict[str, Any]:
        ref = self.conn.execute(
            "SELECT ref_kind FROM evidence_refs WHERE evidence_ref_id = ?",
            (evidence_ref_id,),
        ).fetchone()
        if not ref:
            raise ValueError(f"Evidence ref not found: {evidence_ref_id}")
        weight = DISPUTE_WEIGHTS.get(ref["ref_kind"], 0.0)
        dispute_id = deterministic_id("disp", card_id, evidence_ref_id)

        self.append_event(
            episode_id=episode_id,
            event_type="dispute_recorded",
            payload={
                "schema_version": SCHEMA_VERSION,
                "dispute_id": dispute_id,
                "card_id": card_id,
                "evidence_ref_id": evidence_ref_id,
                "weight": weight,
            },
            idempotency_key=f"dispute_recorded:{card_id}:{evidence_ref_id}",
            producer=producer,
            rule_version=RULE_VERSION,
            apply=True,
        )

        card = self.conn.execute(
            "SELECT scope_tier, status FROM cards WHERE card_id = ?", (card_id,)
        ).fetchone()
        if not card:
            return {"dispute_id": dispute_id, "status_changed": False}

        mass_row = self.conn.execute(
            "SELECT COALESCE(SUM(weight), 0.0) AS mass FROM disputes WHERE card_id = ?",
            (card_id,),
        ).fetchone()
        mass = float(mass_row["mass"])
        threshold = DISPUTE_THRESHOLDS.get(card["scope_tier"], 4.0)
        changed = False
        if mass >= threshold and card["status"] == "active":
            changed = True
            self.append_event(
                episode_id=episode_id,
                event_type="card_status_changed",
                payload={
                    "schema_version": SCHEMA_VERSION,
                    "card_id": card_id,
                    "from_status": "active",
                    "to_status": "needs_recheck",
                    "reason_code": "dispute_threshold_exceeded",
                    "dispute_mass": mass,
                    "threshold": threshold,
                },
                idempotency_key=f"card_status_changed:{card_id}:needs_recheck:{threshold}",
                producer=producer,
                rule_version=RULE_VERSION,
                apply=True,
            )

        return {
            "dispute_id": dispute_id,
            "weight": weight,
            "dispute_mass": mass,
            "threshold": threshold,
            "status_changed": changed,
        }

    def record_outcome(
        self,
        episode_id: str,
        outcome_type: str,
        evidence_ref_ids: List[str],
        metadata: Optional[Dict[str, Any]] = None,
        producer: str = "cli",
    ) -> Dict[str, Any]:
        if outcome_type not in TERMINAL_OUTCOMES:
            raise ValueError(f"Invalid outcome type: {outcome_type}")

        metadata = metadata or {}
        key_payload = canonical_json(
            {
                "episode_id": episode_id,
                "outcome_type": outcome_type,
                "evidence_ref_ids": sorted(evidence_ref_ids),
                "metadata": metadata,
            }
        )
        idem = f"outcome_recorded:{sha256_text(key_payload)[:24]}"

        result = self.append_event(
            episode_id=episode_id,
            event_type="outcome_recorded",
            payload={
                "schema_version": SCHEMA_VERSION,
                "outcome_type": outcome_type,
                "evidence_ref_ids": evidence_ref_ids,
                "metadata_json": metadata,
            },
            idempotency_key=idem,
            producer=producer,
            rule_version=RULE_VERSION,
            apply=True,
        )
        return result

    def recompute_utility_projection(self) -> None:
        self.conn.execute("DELETE FROM utility_stats")

        # Reuse from exposures across all channels.
        reuse_rows = self.conn.execute(
            """
            SELECT e.card_id, COUNT(*) AS reuse, MAX(e.source_event_id) AS last_event
            FROM exposures e
            JOIN cards c ON c.card_id = e.card_id
            WHERE c.kind = 'tactic'
            GROUP BY e.card_id
            """
        ).fetchall()
        stats: Dict[str, Dict[str, int]] = {}
        updated_event: Dict[str, int] = {}
        for r in reuse_rows:
            cid = r["card_id"]
            stats[cid] = {"wins": 0, "losses": 0, "reuse": int(r["reuse"])}
            updated_event[cid] = int(r["last_event"] or 0)

        # Episode-level wins/losses attribution.
        episodes = [r["episode_id"] for r in self.conn.execute("SELECT DISTINCT episode_id FROM outcomes").fetchall()]
        for episode_id in episodes:
            outcome_rows = self.conn.execute(
                """
                SELECT o.event_id, o.outcome_type, o.evidence_ref_ids_json, me.seq_no
                FROM outcomes o
                JOIN memory_events me ON me.event_id = o.event_id
                WHERE o.episode_id = ?
                ORDER BY me.seq_no ASC
                """,
                (episode_id,),
            ).fetchall()
            if not outcome_rows:
                continue

            anchored_present = False
            success_signal = False
            failure_signal = False
            first_terminal_seq = None
            first_terminal_event = 0

            for row in outcome_rows:
                evidence_ids = json.loads(row["evidence_ref_ids_json"])
                if evidence_ids:
                    anchored_present = True
                if row["outcome_type"] in {"tool_success", "user_confirmed_helpful"}:
                    success_signal = True
                if row["outcome_type"] in {"tool_failure", "user_corrected"}:
                    failure_signal = True
                if row["outcome_type"] in TERMINAL_OUTCOMES and first_terminal_seq is None:
                    first_terminal_seq = int(row["seq_no"])
                    first_terminal_event = int(row["event_id"])

            if not anchored_present or first_terminal_seq is None:
                continue

            exp_rows = self.conn.execute(
                """
                SELECT e.card_id, e.rank_position, e.score_total, me.seq_no
                FROM exposures e
                JOIN cards c ON c.card_id = e.card_id
                JOIN memory_events me ON me.event_id = e.source_event_id
                WHERE e.episode_id = ? AND e.channel = 'auto_pack' AND c.kind = 'tactic'
                  AND me.seq_no < ?
                ORDER BY e.rank_position ASC, e.score_total DESC, e.card_id ASC
                """,
                (episode_id, first_terminal_seq),
            ).fetchall()
            eligible = exp_rows[:2]

            for ex in eligible:
                cid = ex["card_id"]
                if cid not in stats:
                    stats[cid] = {"wins": 0, "losses": 0, "reuse": 0}
                    updated_event[cid] = 0
                if success_signal:
                    stats[cid]["wins"] += 1
                if failure_signal:
                    stats[cid]["losses"] += 1
                updated_event[cid] = max(updated_event[cid], first_terminal_event)

        for cid, val in stats.items():
            self.conn.execute(
                """
                INSERT OR REPLACE INTO utility_stats (card_id, wins, losses, reuse, updated_event_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cid, val["wins"], val["losses"], val["reuse"], updated_event.get(cid, 0)),
            )

    # ----------------------------
    # Phase 5 operations/hardening
    # ----------------------------

    def snapshot_projection_counts(self) -> Dict[str, int]:
        tables = [
            "cards",
            "card_evidence_refs",
            "consolidation_decisions",
            "consolidation_ledger",
            "cards_fts",
            "card_embeddings",
            "pack_snapshots",
            "exposures",
            "disputes",
            "card_status_history",
            "outcomes",
            "utility_stats",
        ]
        out: Dict[str, int] = {}
        for table in tables:
            row = self.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            out[table] = int(row["n"])
        return out

    def projection_digest(self) -> str:
        projection_tables = {
            "cards": "card_id",
            "card_evidence_refs": "card_id, evidence_ref_id",
            "consolidation_decisions": "decision_id",
            "consolidation_ledger": "episode_id",
            "card_embeddings": "card_id",
            "pack_snapshots": "pack_id",
            "exposures": "exposure_id",
            "disputes": "dispute_id",
            "card_status_history": "card_id, event_id",
            "outcomes": "event_id",
            "utility_stats": "card_id",
        }
        unstable_columns = {
            "consolidation_decisions": {"decision_id"},
        }
        payload: Dict[str, Any] = {}
        for table, order_by in projection_tables.items():
            rows = self.conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
            cleaned: List[Dict[str, Any]] = []
            for row in rows:
                data = dict(row)
                for col in unstable_columns.get(table, set()):
                    data.pop(col, None)
                cleaned.append(data)
            payload[table] = cleaned
        return sha256_text(canonical_json(payload))

    def _seq_integrity_issues(self) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        episodes = [r["episode_id"] for r in self.conn.execute("SELECT episode_id FROM episodes").fetchall()]
        for episode_id in episodes:
            seqs = [
                int(r["seq_no"])
                for r in self.conn.execute(
                    "SELECT seq_no FROM memory_events WHERE episode_id = ? ORDER BY seq_no",
                    (episode_id,),
                ).fetchall()
            ]
            expected = list(range(1, len(seqs) + 1))
            if seqs != expected:
                issues.append(
                    {
                        "episode_id": episode_id,
                        "expected_prefix": expected[:10],
                        "actual_prefix": seqs[:10],
                        "total_events": len(seqs),
                    }
                )
        return issues

    def check_store_health(self) -> Dict[str, Any]:
        seq_issues = self._seq_integrity_issues()
        dup_idem = self.conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM (
              SELECT idempotency_key, COUNT(*) AS c
              FROM memory_events
              GROUP BY idempotency_key
              HAVING c > 1
            )
            """
        ).fetchone()["n"]
        cards_without_embedding = self.conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM cards c
            LEFT JOIN card_embeddings ce ON ce.card_id = c.card_id
            WHERE ce.card_id IS NULL
            """
        ).fetchone()["n"]
        exposures_without_pack = self.conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM exposures
            WHERE pack_id IS NULL OR pack_id = ''
            """
        ).fetchone()["n"]
        outcomes_without_event = self.conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM outcomes o
            LEFT JOIN memory_events me ON me.event_id = o.event_id
            WHERE me.event_id IS NULL
            """
        ).fetchone()["n"]

        issues = []
        if seq_issues:
            issues.append({"type": "seq_integrity", "details": seq_issues})
        if dup_idem:
            issues.append({"type": "duplicate_idempotency_keys", "count": int(dup_idem)})
        if cards_without_embedding:
            issues.append({"type": "cards_without_embedding", "count": int(cards_without_embedding)})
        if exposures_without_pack:
            issues.append({"type": "exposures_without_pack", "count": int(exposures_without_pack)})
        if outcomes_without_event:
            issues.append({"type": "outcomes_without_event", "count": int(outcomes_without_event)})

        return {
            "healthy": len(issues) == 0,
            "issue_count": len(issues),
            "issues": issues,
        }

    def consolidation_trend(self, days: int = DEFAULT_TREND_DAYS) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT substr(created_at, 1, 10) AS day,
                   SUM(CASE WHEN event_type = 'candidate_proposed' THEN 1 ELSE 0 END) AS proposed,
                   SUM(CASE WHEN event_type = 'card_admitted' THEN 1 ELSE 0 END) AS admitted,
                   SUM(CASE WHEN event_type = 'card_rejected' THEN 1 ELSE 0 END) AS rejected,
                   SUM(CASE WHEN event_type = 'card_merged' THEN 1 ELSE 0 END) AS merged,
                   SUM(CASE WHEN event_type = 'card_superseded' THEN 1 ELSE 0 END) AS superseded,
                   SUM(CASE WHEN event_type = 'card_archived' THEN 1 ELSE 0 END) AS archived
            FROM memory_events
            WHERE event_type IN (
                'candidate_proposed', 'card_admitted', 'card_rejected',
                'card_merged', 'card_superseded', 'card_archived'
            )
              AND created_at >= datetime('now', ?)
            GROUP BY day
            ORDER BY day
            """,
            (f"-{int(days)} days",),
        ).fetchall()
        out = []
        for r in rows:
            proposed = int(r["proposed"] or 0)
            admitted = int(r["admitted"] or 0)
            out.append(
                {
                    "day": r["day"],
                    "proposed": proposed,
                    "admitted": admitted,
                    "rejected": int(r["rejected"] or 0),
                    "merged": int(r["merged"] or 0),
                    "superseded": int(r["superseded"] or 0),
                    "archived": int(r["archived"] or 0),
                    "acceptance_rate": round(admitted / proposed, 4) if proposed else None,
                }
            )
        return out

    def retrieval_window_metrics(self, days: int = DEFAULT_TREND_DAYS) -> Dict[str, Any]:
        episode_rows = self.conn.execute(
            """
            WITH auto_pack_eps AS (
              SELECT DISTINCT episode_id
              FROM exposures
              WHERE channel = 'auto_pack'
                AND created_at >= datetime('now', ?)
            ),
            outcomes_by_episode AS (
              SELECT episode_id,
                     MAX(CASE WHEN outcome_type IN ('tool_success','user_confirmed_helpful') THEN 1 ELSE 0 END) AS has_positive,
                     MAX(CASE WHEN outcome_type IN ('tool_failure','user_corrected') THEN 1 ELSE 0 END) AS has_negative
              FROM outcomes
              WHERE created_at >= datetime('now', ?)
              GROUP BY episode_id
            )
            SELECT COUNT(*) AS auto_pack_episodes,
                   SUM(COALESCE(o.has_positive, 0)) AS positive_episode_count,
                   SUM(COALESCE(o.has_negative, 0)) AS negative_episode_count,
                   SUM(CASE WHEN o.has_positive = 1 OR o.has_negative = 1 THEN 1 ELSE 0 END) AS episodes_with_terminal_outcomes
            FROM auto_pack_eps a
            LEFT JOIN outcomes_by_episode o ON o.episode_id = a.episode_id
            """,
            (f"-{int(days)} days", f"-{int(days)} days"),
        ).fetchone()

        outcomes_row = self.conn.execute(
            """
            SELECT COUNT(*) AS terminal_outcomes,
                   SUM(CASE WHEN outcome_type = 'user_corrected' THEN 1 ELSE 0 END) AS user_corrected_events
            FROM outcomes
            WHERE created_at >= datetime('now', ?)
              AND outcome_type IN ('tool_success','tool_failure','user_confirmed_helpful','user_corrected')
            """,
            (f"-{int(days)} days",),
        ).fetchone()

        auto_pack_eps = int(episode_rows["auto_pack_episodes"] or 0)
        pos_eps = int(episode_rows["positive_episode_count"] or 0)
        neg_eps = int(episode_rows["negative_episode_count"] or 0)
        eval_eps = int(episode_rows["episodes_with_terminal_outcomes"] or 0)
        terminal_outcomes = int(outcomes_row["terminal_outcomes"] or 0)
        corrected = int(outcomes_row["user_corrected_events"] or 0)

        return {
            "window_days": int(days),
            "auto_pack_episodes": auto_pack_eps,
            "episodes_with_terminal_outcomes": eval_eps,
            "positive_episode_count": pos_eps,
            "negative_episode_count": neg_eps,
            "precision_proxy": round(pos_eps / eval_eps, 4) if eval_eps else None,
            "terminal_outcomes": terminal_outcomes,
            "user_corrected_events": corrected,
            "correction_rate": round(corrected / terminal_outcomes, 4) if terminal_outcomes else None,
        }

    def retrieval_daily_trend(self, days: int = DEFAULT_TREND_DAYS) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            WITH auto_pack_daily AS (
              SELECT substr(created_at, 1, 10) AS day, episode_id
              FROM exposures
              WHERE channel = 'auto_pack'
                AND created_at >= datetime('now', ?)
              GROUP BY day, episode_id
            ),
            outcome_daily AS (
              SELECT substr(created_at, 1, 10) AS day, episode_id,
                     MAX(CASE WHEN outcome_type IN ('tool_success','user_confirmed_helpful') THEN 1 ELSE 0 END) AS has_positive,
                     MAX(CASE WHEN outcome_type IN ('tool_failure','user_corrected') THEN 1 ELSE 0 END) AS has_negative,
                     SUM(CASE WHEN outcome_type = 'user_corrected' THEN 1 ELSE 0 END) AS corrected,
                     COUNT(*) AS terminal_count
              FROM outcomes
              WHERE created_at >= datetime('now', ?)
                AND outcome_type IN ('tool_success','tool_failure','user_confirmed_helpful','user_corrected')
              GROUP BY day, episode_id
            )
            SELECT a.day AS day,
                   COUNT(*) AS auto_pack_episodes,
                   SUM(COALESCE(o.has_positive, 0)) AS positive_episode_count,
                   SUM(COALESCE(o.has_negative, 0)) AS negative_episode_count,
                   SUM(COALESCE(o.corrected, 0)) AS corrected_events,
                   SUM(COALESCE(o.terminal_count, 0)) AS terminal_events
            FROM auto_pack_daily a
            LEFT JOIN outcome_daily o ON o.episode_id = a.episode_id AND o.day = a.day
            GROUP BY a.day
            ORDER BY a.day
            """,
            (f"-{int(days)} days", f"-{int(days)} days"),
        ).fetchall()

        out = []
        for r in rows:
            positive = int(r["positive_episode_count"] or 0)
            negative = int(r["negative_episode_count"] or 0)
            evaluated = positive + negative
            terminal = int(r["terminal_events"] or 0)
            corrected = int(r["corrected_events"] or 0)
            out.append(
                {
                    "day": r["day"],
                    "auto_pack_episodes": int(r["auto_pack_episodes"] or 0),
                    "positive_episode_count": positive,
                    "negative_episode_count": negative,
                    "precision_proxy": round(positive / evaluated, 4) if evaluated else None,
                    "terminal_events": terminal,
                    "corrected_events": corrected,
                    "correction_rate": round(corrected / terminal, 4) if terminal else None,
                }
            )
        return out

    def utility_summary(self) -> Dict[str, Any]:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS tactic_cards,
                   COALESCE(SUM(wins), 0) AS wins,
                   COALESCE(SUM(losses), 0) AS losses,
                   COALESCE(SUM(reuse), 0) AS reuse
            FROM utility_stats
            """
        ).fetchone()
        wins = int(row["wins"] or 0)
        losses = int(row["losses"] or 0)
        total = wins + losses
        return {
            "tactic_cards": int(row["tactic_cards"] or 0),
            "wins": wins,
            "losses": losses,
            "reuse": int(row["reuse"] or 0),
            "win_rate": round(wins / total, 4) if total else None,
        }

    def status_report(self, days: int = DEFAULT_TREND_DAYS) -> Dict[str, Any]:
        table_names = [
            "episodes",
            "artifacts",
            "evidence_refs",
            "memory_events",
            "cards",
            "exposures",
            "outcomes",
            "pack_snapshots",
            "disputes",
            "utility_stats",
        ]
        counts = {}
        for t in table_names:
            counts[t] = int(self.conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"])

        cards_by_kind = [
            dict(r)
            for r in self.conn.execute(
                "SELECT kind, COUNT(*) AS count FROM cards GROUP BY kind ORDER BY kind"
            ).fetchall()
        ]
        cards_by_status = [
            dict(r)
            for r in self.conn.execute(
                "SELECT status, COUNT(*) AS count FROM cards GROUP BY status ORDER BY status"
            ).fetchall()
        ]
        cards_by_scope = [
            dict(r)
            for r in self.conn.execute(
                "SELECT scope_tier, COUNT(*) AS count FROM cards GROUP BY scope_tier ORDER BY scope_tier"
            ).fetchall()
        ]

        return {
            "db_path": self.db_path,
            "generated_at": now_iso(),
            "projection_digest": self.projection_digest(),
            "health": self.check_store_health(),
            "counts": counts,
            "cards_breakdown": {
                "by_kind": cards_by_kind,
                "by_status": cards_by_status,
                "by_scope_tier": cards_by_scope,
            },
            "consolidation_trend": self.consolidation_trend(days=days),
            "retrieval_window": self.retrieval_window_metrics(days=days),
            "retrieval_daily": self.retrieval_daily_trend(days=days),
            "utility_summary": self.utility_summary(),
        }

    def recover_partial_writes(
        self, producer: str = "recovery", run_missing_consolidation: bool = True
    ) -> Dict[str, Any]:
        repaired = {
            "episode_recorded_events": 0,
            "artifact_recorded_events": 0,
            "evidence_ref_recorded_events": 0,
            "consolidation_triggered_events": 0,
            "consolidation_runs": 0,
        }

        ev_rows = self.conn.execute(
            """
            SELECT episode_id, event_type, payload_json
            FROM memory_events
            WHERE event_type IN (
              'episode_recorded', 'artifact_recorded', 'evidence_ref_recorded',
              'consolidation_triggered', 'candidate_proposed'
            )
            """
        ).fetchall()

        episode_recorded = set()
        artifact_recorded = set()
        evidence_recorded = set()
        consolidation_triggered = set()
        consolidated = set()
        for row in ev_rows:
            payload = json.loads(row["payload_json"])
            et = row["event_type"]
            if et == "episode_recorded":
                episode_recorded.add(row["episode_id"])
            elif et == "artifact_recorded":
                aid = payload.get("artifact_id")
                if aid:
                    artifact_recorded.add(aid)
            elif et == "evidence_ref_recorded":
                eid = payload.get("evidence_ref_id")
                if eid:
                    evidence_recorded.add(eid)
            elif et == "consolidation_triggered":
                consolidation_triggered.add(row["episode_id"])
            elif et == "candidate_proposed":
                consolidated.add(row["episode_id"])

        episodes = self.conn.execute(
            "SELECT episode_id, payload_hash FROM episodes ORDER BY episode_id"
        ).fetchall()
        for ep in episodes:
            episode_id = ep["episode_id"]
            if episode_id not in episode_recorded:
                res = self.append_event(
                    episode_id=episode_id,
                    event_type="episode_recorded",
                    payload={
                        "schema_version": SCHEMA_VERSION,
                        "episode_id": episode_id,
                        "payload_hash": ep["payload_hash"],
                    },
                    idempotency_key=f"episode_recorded:{episode_id}:{ep['payload_hash']}",
                    producer=producer,
                    rule_version=RULE_VERSION,
                    apply=True,
                )
                if res["inserted"]:
                    repaired["episode_recorded_events"] += 1

            if episode_id not in consolidation_triggered:
                res = self.append_event(
                    episode_id=episode_id,
                    event_type="consolidation_triggered",
                    payload={
                        "schema_version": SCHEMA_VERSION,
                        "episode_id": episode_id,
                        "trigger": "recovery_missing_trigger",
                    },
                    idempotency_key=f"consolidation_triggered:{episode_id}",
                    producer=producer,
                    rule_version=RULE_VERSION,
                    apply=True,
                )
                if res["inserted"]:
                    repaired["consolidation_triggered_events"] += 1

        artifacts = self.conn.execute(
            "SELECT artifact_id, episode_id, artifact_kind, content_hash FROM artifacts ORDER BY artifact_id"
        ).fetchall()
        for art in artifacts:
            if art["artifact_id"] in artifact_recorded:
                continue
            res = self.append_event(
                episode_id=art["episode_id"],
                event_type="artifact_recorded",
                payload={
                    "schema_version": SCHEMA_VERSION,
                    "artifact_id": art["artifact_id"],
                    "artifact_kind": art["artifact_kind"],
                    "content_hash": art["content_hash"],
                },
                idempotency_key=(
                    f"artifact_recorded:{art['episode_id']}:{art['artifact_id']}:{art['content_hash']}"
                ),
                producer=producer,
                rule_version=RULE_VERSION,
                apply=True,
            )
            if res["inserted"]:
                repaired["artifact_recorded_events"] += 1

        evidence = self.conn.execute(
            "SELECT evidence_ref_id, episode_id, ref_kind, ref_hash FROM evidence_refs ORDER BY evidence_ref_id"
        ).fetchall()
        for ev in evidence:
            if ev["evidence_ref_id"] in evidence_recorded:
                continue
            res = self.append_event(
                episode_id=ev["episode_id"],
                event_type="evidence_ref_recorded",
                payload={
                    "schema_version": SCHEMA_VERSION,
                    "evidence_ref_id": ev["evidence_ref_id"],
                    "ref_kind": ev["ref_kind"],
                    "ref_hash": ev["ref_hash"],
                },
                idempotency_key=(
                    f"evidence_ref_recorded:{ev['episode_id']}:{ev['evidence_ref_id']}:{ev['ref_hash']}"
                ),
                producer=producer,
                rule_version=RULE_VERSION,
                apply=True,
            )
            if res["inserted"]:
                repaired["evidence_ref_recorded_events"] += 1

        if run_missing_consolidation:
            for ep in episodes:
                episode_id = ep["episode_id"]
                if episode_id in consolidated:
                    continue
                ev_count = self.conn.execute(
                    "SELECT COUNT(*) AS n FROM evidence_refs WHERE episode_id = ?",
                    (episode_id,),
                ).fetchone()["n"]
                if int(ev_count) == 0:
                    continue
                self.consolidate_episode(episode_id, producer=producer)
                repaired["consolidation_runs"] += 1

        return repaired

    def full_rebuild(self, verify_stability: bool = False) -> Dict[str, Any]:
        before_counts = self.snapshot_projection_counts()
        before_digest = self.projection_digest()
        replay_result = self.replay_reducers()
        after_counts = self.snapshot_projection_counts()
        after_digest = self.projection_digest()

        verification = {
            "verified": None,
            "post_rebuild_digest": after_digest,
            "second_rebuild_digest": None,
        }
        if verify_stability:
            self.replay_reducers()
            second_digest = self.projection_digest()
            verification = {
                "verified": second_digest == after_digest,
                "post_rebuild_digest": after_digest,
                "second_rebuild_digest": second_digest,
            }

        return {
            "replay": replay_result,
            "before_counts": before_counts,
            "after_counts": after_counts,
            "digest_changed": before_digest != after_digest,
            "verification": verification,
        }

    def verify_reducer_idempotency(self, sample_events: int = 100) -> Dict[str, Any]:
        initial_digest = self.projection_digest()
        self.replay_reducers()
        first_digest = self.projection_digest()
        self.replay_reducers()
        second_digest = self.projection_digest()

        sample_rows = self.conn.execute(
            """
            SELECT episode_id, event_type, payload_json, idempotency_key, producer, rule_version
            FROM memory_events
            ORDER BY event_id
            LIMIT ?
            """,
            (int(sample_events),),
        ).fetchall()

        inserted_on_retry = 0
        for row in sample_rows:
            payload = json.loads(row["payload_json"])
            res = self.append_event(
                episode_id=row["episode_id"],
                event_type=row["event_type"],
                payload=payload,
                idempotency_key=row["idempotency_key"],
                producer=row["producer"],
                rule_version=row["rule_version"],
                apply=False,
            )
            if res["inserted"]:
                inserted_on_retry += 1

        seq_issues = self._seq_integrity_issues()
        stable_after_replay = first_digest == second_digest
        return {
            "stable_after_replay": stable_after_replay,
            "initial_digest": initial_digest,
            "first_replay_digest": first_digest,
            "second_replay_digest": second_digest,
            "initial_projection_matched_replay": initial_digest == first_digest,
            "sampled_events": len(sample_rows),
            "inserted_on_retry": inserted_on_retry,
            "seq_integrity_issue_count": len(seq_issues),
            "pass": stable_after_replay and inserted_on_retry == 0 and len(seq_issues) == 0,
        }

    def migrate_embeddings(self, to_model: str, dim: int = 64, from_model: Optional[str] = None) -> Dict[str, Any]:
        if not to_model:
            raise ValueError("to_model is required")

        if from_model:
            rows = self.conn.execute(
                """
                SELECT c.card_id, c.statement, c.updated_event_id
                FROM cards c
                LEFT JOIN card_embeddings ce ON ce.card_id = c.card_id
                WHERE COALESCE(ce.embedding_model, 'pseudo-v1') = ?
                ORDER BY c.card_id
                """,
                (from_model,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT card_id, statement, updated_event_id FROM cards ORDER BY card_id"
            ).fetchall()

        migrated = 0
        for row in rows:
            vec = pseudo_embedding(row["statement"], dim=dim, salt=to_model)
            self.conn.execute(
                """
                INSERT OR REPLACE INTO card_embeddings (card_id, embedding_model, embedding_vector, updated_event_id)
                VALUES (?, ?, ?, ?)
                """,
                (row["card_id"], to_model, canonical_json(vec), row["updated_event_id"]),
            )
            migrated += 1

        return {
            "migrated_cards": migrated,
            "to_model": to_model,
            "from_model": from_model,
            "dim": dim,
        }

    def _outcome_rate_window(self, window_days: int, offset_days: int = 0) -> Dict[str, Any]:
        lower = f"-{int(window_days + offset_days)} days"
        upper = f"-{int(offset_days)} days"
        row = self.conn.execute(
            """
            SELECT SUM(CASE WHEN outcome_type IN ('tool_success','user_confirmed_helpful') THEN 1 ELSE 0 END) AS positive,
                   COUNT(*) AS total
            FROM outcomes
            WHERE created_at >= datetime('now', ?)
              AND created_at < datetime('now', ?)
              AND outcome_type IN ('tool_success','tool_failure','user_confirmed_helpful','user_corrected')
            """,
            (lower, upper),
        ).fetchone()
        total = int(row["total"] or 0)
        positive = int(row["positive"] or 0)
        return {
            "window_days": int(window_days),
            "offset_days": int(offset_days),
            "total": total,
            "positive": positive,
            "success_rate": round(positive / total, 4) if total else None,
        }

    def evaluate_causal_gates(self, days: int = DEFAULT_TREND_DAYS) -> Dict[str, Any]:
        retrieval = self.retrieval_window_metrics(days=days)
        auto_pack_sample = int(retrieval["episodes_with_terminal_outcomes"] or 0)
        precision = retrieval["precision_proxy"]
        correction = retrieval["correction_rate"]

        retrieval_stability = (
            auto_pack_sample >= GATE_MIN_SAMPLE_EPISODES
            and precision is not None
            and precision >= GATE_MIN_PRECISION_PROXY
            and correction is not None
            and correction <= GATE_MAX_CORRECTION_RATE
        )

        active_cards = self.conn.execute(
            "SELECT COUNT(*) AS n FROM cards WHERE status IN ('active', 'needs_recheck')"
        ).fetchone()["n"]
        admitted_7d = self.conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM memory_events
            WHERE event_type = 'card_admitted'
              AND created_at >= datetime('now', '-7 days')
            """
        ).fetchone()["n"]
        retired_7d = self.conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM memory_events
            WHERE event_type IN ('card_archived', 'card_deprecated', 'card_superseded')
              AND created_at >= datetime('now', '-7 days')
            """
        ).fetchone()["n"]
        net_growth_7d = int(admitted_7d or 0) - int(retired_7d or 0)
        allowed_growth = max(5, int((active_cards or 0) * GATE_MAX_BOUNDEDNESS_GROWTH_RATIO))
        store_boundedness = net_growth_7d <= allowed_growth

        half = max(1, int(days // 2))
        recent = self._outcome_rate_window(window_days=half, offset_days=0)
        prior = self._outcome_rate_window(window_days=half, offset_days=half)
        improvement = None
        if recent["success_rate"] is not None and prior["success_rate"] is not None:
            improvement = round(recent["success_rate"] - prior["success_rate"], 4)
        utility_plateau = (
            recent["total"] >= GATE_MIN_SAMPLE_EPISODES
            and prior["total"] >= GATE_MIN_SAMPLE_EPISODES
            and improvement is not None
            and abs(improvement) <= GATE_PLATEAU_DELTA
        )

        events_7d = int(
            self.conn.execute(
                "SELECT COUNT(*) AS n FROM memory_events WHERE created_at >= datetime('now', '-7 days')"
            ).fetchone()["n"]
        )
        event_volume_sufficient = events_7d >= GATE_MIN_EVENTS_7D

        ready = retrieval_stability and store_boundedness and utility_plateau and event_volume_sufficient
        return {
            "window_days": int(days),
            "retrieval_stability": retrieval_stability,
            "store_boundedness": store_boundedness,
            "utility_plateau": utility_plateau,
            "event_volume_sufficient": event_volume_sufficient,
            "ready_for_causal_instrumentation": ready,
            "metrics": {
                "retrieval": retrieval,
                "active_cards": int(active_cards or 0),
                "admitted_7d": int(admitted_7d or 0),
                "retired_7d": int(retired_7d or 0),
                "net_growth_7d": int(net_growth_7d),
                "allowed_growth_7d": int(allowed_growth),
                "success_rate_recent": recent,
                "success_rate_prior": prior,
                "improvement": improvement,
                "events_7d": events_7d,
            },
            "thresholds": {
                "min_sample_episodes": GATE_MIN_SAMPLE_EPISODES,
                "min_precision_proxy": GATE_MIN_PRECISION_PROXY,
                "max_correction_rate": GATE_MAX_CORRECTION_RATE,
                "max_boundedness_growth_ratio": GATE_MAX_BOUNDEDNESS_GROWTH_RATIO,
                "plateau_delta": GATE_PLATEAU_DELTA,
                "min_events_7d": GATE_MIN_EVENTS_7D,
            },
        }

    # ----------------------------
    # Replay + export
    # ----------------------------

    def replay_reducers(self) -> Dict[str, Any]:
        with self.conn:
            self.conn.execute("DELETE FROM exposures")
            self.conn.execute("DELETE FROM pack_snapshots")
            self.conn.execute("DELETE FROM disputes")
            self.conn.execute("DELETE FROM card_status_history")
            self.conn.execute("DELETE FROM utility_stats")
            self.conn.execute("DELETE FROM outcomes")
            self.conn.execute("DELETE FROM card_evidence_refs")
            self.conn.execute("DELETE FROM card_embeddings")
            self.conn.execute("DELETE FROM cards_fts")
            self.conn.execute("DELETE FROM consolidation_decisions")
            self.conn.execute("DELETE FROM consolidation_ledger")
            self.conn.execute("DELETE FROM cards")

            rows = self.conn.execute(
                "SELECT event_id, episode_id, event_type, payload_json, created_at FROM memory_events ORDER BY event_id"
            ).fetchall()
            for row in rows:
                payload = json.loads(row["payload_json"])
                self.apply_event(
                    row["event_id"],
                    row["episode_id"],
                    row["event_type"],
                    payload,
                    event_created_at=row["created_at"],
                )

        return {"events_replayed": len(rows)}

    def export_episode(self, episode_id: str) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT event_id, seq_no, event_type, payload_json, created_at
            FROM memory_events
            WHERE episode_id = ?
            ORDER BY seq_no
            """,
            (episode_id,),
        ).fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "event_id": r["event_id"],
                    "seq_no": r["seq_no"],
                    "event_type": r["event_type"],
                    "payload": json.loads(r["payload_json"]),
                    "created_at": r["created_at"],
                }
            )
        return out


# ----------------------------
# CLI
# ----------------------------


def parse_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Plan C memory system CLI")
    p.add_argument("--db", default=DEFAULT_DB, help=f"SQLite path (default: {DEFAULT_DB})")

    sp = p.add_subparsers(dest="cmd", required=True)

    sp.add_parser("init", help="Initialize database schema")

    rec = sp.add_parser("record-episode", help="Record an episode JSON payload")
    rec.add_argument("--input", required=True)

    app = sp.add_parser("append-event", help="Append a raw memory event")
    app.add_argument("--episode", required=True)
    app.add_argument("--type", required=True)
    app.add_argument("--payload", required=True, help="Path to payload JSON")
    app.add_argument("--idempotency-key", required=True)
    app.add_argument("--producer", default="cli")
    app.add_argument("--rule-version", default=RULE_VERSION)

    cons = sp.add_parser("consolidate", help="Run deterministic consolidation")
    cons.add_argument("--episode", required=True)

    led = sp.add_parser("ledger", help="Show consolidation ledger")
    led.add_argument("--episode", required=True)

    ded = sp.add_parser("dedup", help="Run daily dedup sweep")

    status = sp.add_parser("status", help="Store health, counts, and trend metrics")
    status.add_argument("--days", type=int, default=DEFAULT_TREND_DAYS)

    recover = sp.add_parser("recover", help="Recover missing canonical events and optional consolidation")
    recover.add_argument("--no-consolidation", action="store_true")

    verify = sp.add_parser("verify-idempotency", help="Replay/idempotency consistency checks")
    verify.add_argument("--sample-events", type=int, default=100)

    rebuild = sp.add_parser("full-rebuild", help="Rebuild projections from memory_events")
    rebuild.add_argument("--verify-stability", action="store_true")

    migrate = sp.add_parser("migrate-embeddings", help="Recompute embedding vectors with a new model tag")
    migrate.add_argument("--to-model", required=True)
    migrate.add_argument("--from-model")
    migrate.add_argument("--dim", type=int, default=64)

    gates = sp.add_parser("gates", help="Evaluate go/no-go gates for causal instrumentation")
    gates.add_argument("--days", type=int, default=DEFAULT_TREND_DAYS)

    sea = sp.add_parser("search", help="Search cards")
    sea.add_argument("--query", required=True)
    sea.add_argument("--episode")
    sea.add_argument("--limit", type=int, default=20)
    sea.add_argument("--include-archived", action="store_true")

    pack = sp.add_parser("pack", help="Build deterministic pack and record exposure")
    pack.add_argument("--episode", required=True)
    pack.add_argument("--query", required=True)
    pack.add_argument("--channel", default="auto_pack", choices=["auto_pack", "search", "explicit_read", "check"])

    ep = sp.add_parser("explain-pack", help="Explain pack snapshot")
    ep.add_argument("--episode", required=True)
    ep.add_argument("--pack-id")

    ec = sp.add_parser("explain-consolidation", help="Explain consolidation decisions")
    ec.add_argument("--episode", required=True)

    disp = sp.add_parser("record-dispute", help="Record dispute evidence and status transition")
    disp.add_argument("--episode", required=True)
    disp.add_argument("--card-id", required=True)
    disp.add_argument("--evidence-ref-id", required=True)

    out = sp.add_parser("record-outcome", help="Record terminal outcome")
    out.add_argument("--episode", required=True)
    out.add_argument("--type", required=True, choices=sorted(TERMINAL_OUTCOMES))
    out.add_argument("--evidence-ref-ids", default="")
    out.add_argument("--metadata")

    rep = sp.add_parser("replay", help="Rebuild all projections from memory_events")

    ex = sp.add_parser("export", help="Export episode events as JSONL")
    ex.add_argument("--episode", required=True)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    engine = MemoryEngine(args.db)
    try:
        if args.cmd == "init":
            engine.init_schema()
            print_json({"ok": True, "db": args.db})
            return 0

        engine.init_schema()

        if args.cmd == "record-episode":
            out = engine.record_episode_from_file(args.input)
            print_json(out)
            return 0

        if args.cmd == "append-event":
            payload = parse_json_file(args.payload)
            out = engine.append_event(
                episode_id=args.episode,
                event_type=args.type,
                payload=payload,
                idempotency_key=args.idempotency_key,
                producer=args.producer,
                rule_version=args.rule_version,
                apply=True,
            )
            print_json(out)
            return 0

        if args.cmd == "consolidate":
            out = engine.consolidate_episode(args.episode)
            print_json(out)
            return 0

        if args.cmd == "ledger":
            row = engine.conn.execute(
                "SELECT * FROM consolidation_ledger WHERE episode_id = ?", (args.episode,)
            ).fetchone()
            print_json(dict(row) if row else {})
            return 0

        if args.cmd == "dedup":
            out = engine.run_dedup_daily()
            print_json(out)
            return 0

        if args.cmd == "status":
            out = engine.status_report(days=args.days)
            print_json(out)
            return 0

        if args.cmd == "recover":
            out = engine.recover_partial_writes(run_missing_consolidation=not args.no_consolidation)
            print_json(out)
            return 0

        if args.cmd == "verify-idempotency":
            out = engine.verify_reducer_idempotency(sample_events=args.sample_events)
            print_json(out)
            return 0

        if args.cmd == "full-rebuild":
            out = engine.full_rebuild(verify_stability=args.verify_stability)
            print_json(out)
            return 0

        if args.cmd == "migrate-embeddings":
            out = engine.migrate_embeddings(
                to_model=args.to_model,
                from_model=args.from_model,
                dim=args.dim,
            )
            print_json(out)
            return 0

        if args.cmd == "gates":
            out = engine.evaluate_causal_gates(days=args.days)
            print_json(out)
            return 0

        if args.cmd == "search":
            rows = engine.retrieve_cards(
                query=args.query,
                episode_id=args.episode,
                include_archived=args.include_archived,
                limit=args.limit,
                mode="search",
            )
            print_json({"count": len(rows), "results": rows})
            return 0

        if args.cmd == "pack":
            out = engine.build_pack(args.episode, args.query, channel=args.channel)
            print_json(out)
            return 0

        if args.cmd == "explain-pack":
            out = engine.explain_pack(args.episode, pack_id=args.pack_id)
            print_json(out)
            return 0

        if args.cmd == "explain-consolidation":
            out = engine.explain_consolidation(args.episode)
            print_json(out)
            return 0

        if args.cmd == "record-dispute":
            out = engine.record_dispute(args.episode, args.card_id, args.evidence_ref_id)
            print_json(out)
            return 0

        if args.cmd == "record-outcome":
            ev_ids = [x.strip() for x in args.evidence_ref_ids.split(",") if x.strip()]
            metadata = parse_json_file(args.metadata) if args.metadata else {}
            out = engine.record_outcome(args.episode, args.type, ev_ids, metadata)
            print_json(out)
            return 0

        if args.cmd == "replay":
            out = engine.replay_reducers()
            print_json(out)
            return 0

        if args.cmd == "export":
            events = engine.export_episode(args.episode)
            for event in events:
                print(canonical_json(event))
            return 0

        parser.error(f"Unhandled command: {args.cmd}")
        return 2
    except Exception as exc:
        print_json({"error": str(exc)})
        return 1
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
