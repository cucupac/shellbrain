"""Unify evidence storage behind canonical refs and links."""

from __future__ import annotations

import hashlib
import json

from alembic import op
from sqlalchemy import text

from app.infrastructure.db.runtime.models.views import (
    USAGE_PROBLEM_TOKENS_LEGACY_SQL,
    USAGE_PROBLEM_TOKENS_PRE_UNIFIED_EVIDENCE_LEGACY_SQL,
)


revision = "20260522_0031"
down_revision = "20260522_0030"
branch_labels = None
depends_on = None


_SOURCE_KINDS = (
    "episode_event",
    "anchor",
    "memory",
    "commit",
    "transcript",
    "test",
    "manual",
)
_TARGET_TYPES = (
    "memory",
    "fact_update",
    "association_edge",
    "utility_observation",
    "concept_claim",
    "concept_relation",
    "concept_grounding",
    "concept_memory_link",
    "concept_lifecycle_event",
)
_ROLES = (
    "supports",
    "contradicts",
    "observed_in",
    "created_from",
    "validated_by",
    "invalidated_by",
    "explains",
)
_CONCEPT_KIND_FIELD = {
    "anchor": "anchor_id",
    "memory": "memory_id",
    "commit": "commit_ref",
    "transcript": "transcript_ref",
    "test": "note",
    "manual": "note",
}
_CONCEPT_TARGET_MAP = {
    "relation": "concept_relation",
    "claim": "concept_claim",
    "grounding": "concept_grounding",
    "memory_link": "concept_memory_link",
    "lifecycle_event": "concept_lifecycle_event",
}
_CONCRETE_LEGACY_LINKS = (
    ("memory_evidence", "memory_id", "memory"),
    ("fact_update_evidence", "fact_update_id", "fact_update"),
    ("association_edge_evidence", "edge_id", "association_edge"),
    ("utility_observation_evidence", "observation_id", "utility_observation"),
)


def upgrade() -> None:
    """Create unified evidence storage and backfill legacy evidence rows."""

    bind = op.get_bind()
    _prepare_schema()
    _backfill_existing_refs(bind)
    _create_canonical_indexes_and_links_table()
    expected_sources: set[tuple[str, str]] = _existing_source_keys(bind)
    expected_links: set[tuple[str, str, str, str]] = set()
    _backfill_concrete_links(bind, expected_links=expected_links)
    _backfill_concept_evidence(
        bind, expected_sources=expected_sources, expected_links=expected_links
    )
    _assert_backfill_parity(bind, expected_sources=expected_sources, expected_links=expected_links)
    op.execute(USAGE_PROBLEM_TOKENS_LEGACY_SQL)


def downgrade() -> None:
    """Drop unified storage while preserving legacy evidence tables."""

    op.execute(USAGE_PROBLEM_TOKENS_PRE_UNIFIED_EVIDENCE_LEGACY_SQL)
    op.execute("DROP TABLE IF EXISTS evidence_links;")
    op.execute(
        """
        DELETE FROM evidence_refs
        WHERE kind IS NOT NULL
          AND kind <> 'episode_event';

        ALTER TABLE evidence_refs
          DROP CONSTRAINT IF EXISTS ck_evidence_refs_kind,
          DROP CONSTRAINT IF EXISTS uq_evidence_repo_canonical_hash;

        DROP INDEX IF EXISTS uq_evidence_repo_canonical_hash;
        DROP INDEX IF EXISTS idx_evidence_links_target;
        DROP INDEX IF EXISTS idx_evidence_links_evidence;

        ALTER TABLE evidence_refs
          DROP COLUMN IF EXISTS kind,
          DROP COLUMN IF EXISTS canonical_hash,
          DROP COLUMN IF EXISTS anchor_id,
          DROP COLUMN IF EXISTS memory_id,
          DROP COLUMN IF EXISTS commit_ref,
          DROP COLUMN IF EXISTS transcript_ref,
          DROP COLUMN IF EXISTS note;

        CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_repo_ref
          ON evidence_refs(repo_id, ref);
        """
    )


def _prepare_schema() -> None:
    """Add nullable source columns before data backfill."""

    op.execute(
        """
        DROP INDEX IF EXISTS uq_evidence_repo_ref;
        ALTER TABLE evidence_refs
          DROP CONSTRAINT IF EXISTS uq_evidence_repo_ref,
          ADD COLUMN IF NOT EXISTS kind TEXT,
          ADD COLUMN IF NOT EXISTS canonical_hash TEXT,
          ADD COLUMN IF NOT EXISTS anchor_id TEXT REFERENCES anchors(id) ON DELETE SET NULL,
          ADD COLUMN IF NOT EXISTS memory_id TEXT REFERENCES memories(id) ON DELETE SET NULL,
          ADD COLUMN IF NOT EXISTS commit_ref TEXT,
          ADD COLUMN IF NOT EXISTS transcript_ref TEXT,
          ADD COLUMN IF NOT EXISTS note TEXT;

        ALTER TABLE evidence_refs
          ALTER COLUMN created_at SET DEFAULT NOW();
        """
    )


def _backfill_existing_refs(bind) -> None:
    """Mark existing concrete evidence refs as episode-event evidence."""

    rows = bind.execute(
        text("SELECT id, ref, episode_event_id FROM evidence_refs")
    ).mappings()
    for row in rows:
        identity = str(row["episode_event_id"] or row["ref"])
        bind.execute(
            text(
                """
                UPDATE evidence_refs
                SET kind = 'episode_event',
                    canonical_hash = :canonical_hash
                WHERE id = :id
                """
            ),
            {"id": row["id"], "canonical_hash": _canonical_hash("episode_event", identity)},
        )
    op.execute(
        """
        ALTER TABLE evidence_refs
          ALTER COLUMN kind SET NOT NULL,
          ALTER COLUMN canonical_hash SET NOT NULL;
        """
    )


def _create_canonical_indexes_and_links_table() -> None:
    """Create unified evidence-link storage and constraints."""

    op.execute(
        f"""
        ALTER TABLE evidence_refs
          DROP CONSTRAINT IF EXISTS ck_evidence_refs_kind;

        ALTER TABLE evidence_refs
          ADD CONSTRAINT ck_evidence_refs_kind
          CHECK (kind IN ({_quoted(_SOURCE_KINDS)}));

        CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_repo_canonical_hash
          ON evidence_refs(repo_id, canonical_hash);

        CREATE TABLE IF NOT EXISTS evidence_links (
          id TEXT PRIMARY KEY,
          repo_id TEXT NOT NULL,
          target_type TEXT NOT NULL,
          target_id TEXT NOT NULL,
          evidence_id TEXT NOT NULL REFERENCES evidence_refs(id) ON DELETE CASCADE,
          evidence_role TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_evidence_links_target_type
            CHECK (target_type IN ({_quoted(_TARGET_TYPES)})),
          CONSTRAINT ck_evidence_links_role
            CHECK (evidence_role IN ({_quoted(_ROLES)})),
          CONSTRAINT uq_evidence_links_target_evidence_role
            UNIQUE (repo_id, target_type, target_id, evidence_id, evidence_role)
        );

        CREATE INDEX IF NOT EXISTS idx_evidence_links_target
          ON evidence_links(repo_id, target_type, target_id);

        CREATE INDEX IF NOT EXISTS idx_evidence_links_evidence
          ON evidence_links(evidence_id);
        """
    )


def _existing_source_keys(bind) -> set[tuple[str, str]]:
    rows = bind.execute(
        text("SELECT kind, canonical_hash FROM evidence_refs")
    ).mappings()
    return {(str(row["kind"]), str(row["canonical_hash"])) for row in rows}


def _backfill_concrete_links(
    bind, *, expected_links: set[tuple[str, str, str, str]]
) -> None:
    """Backfill legacy concrete evidence joins into evidence_links."""

    for table_name, target_column, target_type in _CONCRETE_LEGACY_LINKS:
        rows = bind.execute(
            text(
                f"""
                SELECT er.repo_id, legacy.{target_column} AS target_id, legacy.evidence_id
                FROM {table_name} legacy
                JOIN evidence_refs er ON er.id = legacy.evidence_id
                """
            )
        ).mappings()
        for row in rows:
            _insert_link(
                bind,
                repo_id=str(row["repo_id"]),
                target_type=target_type,
                target_id=str(row["target_id"]),
                evidence_id=str(row["evidence_id"]),
                role="supports",
            )
            expected_links.add(
                (target_type, str(row["target_id"]), str(row["evidence_id"]), "supports")
            )


def _backfill_concept_evidence(
    bind,
    *,
    expected_sources: set[tuple[str, str]],
    expected_links: set[tuple[str, str, str, str]],
) -> None:
    """Backfill concept_evidence rows into canonical refs and links."""

    rows = bind.execute(text("SELECT * FROM concept_evidence")).mappings().all()
    malformed: list[str] = []
    for row in rows:
        try:
            source = _concept_source(row)
            target_type = _CONCEPT_TARGET_MAP[str(row["target_type"])]
        except (KeyError, ValueError) as exc:
            malformed.append(f"{row['id']}: {exc}")
            continue
        evidence_id = _upsert_evidence_ref(
            bind,
            repo_id=str(row["repo_id"]),
            source=source,
            created_at=row["created_at"],
        )
        _insert_link(
            bind,
            repo_id=str(row["repo_id"]),
            target_type=target_type,
            target_id=str(row["target_id"]),
            evidence_id=evidence_id,
            role="supports",
            created_at=row["created_at"],
        )
        expected_sources.add((source["kind"], source["canonical_hash"]))
        expected_links.add(
            (target_type, str(row["target_id"]), evidence_id, "supports")
        )
    if malformed:
        sample = "; ".join(malformed[:20])
        raise RuntimeError(
            f"Malformed concept_evidence rows block evidence backfill: {sample}"
        )


def _concept_source(row) -> dict[str, str | None]:
    kind = str(row["evidence_kind"])
    if kind not in _CONCEPT_KIND_FIELD:
        raise ValueError(f"unsupported evidence_kind {kind!r}")
    required_field = _CONCEPT_KIND_FIELD[kind]
    fields = ("anchor_id", "memory_id", "commit_ref", "transcript_ref", "note")
    present = {
        field
        for field in fields
        if row[field] is not None and str(row[field]).strip()
    }
    if present != {required_field}:
        raise ValueError(
            f"{kind} evidence requires only {required_field}; present={sorted(present)}"
        )
    identity = str(row[required_field]).strip()
    source: dict[str, str | None] = {
        "kind": kind,
        "ref": identity,
        "canonical_hash": _canonical_hash(kind, identity),
        "episode_event_id": None,
        "anchor_id": None,
        "memory_id": None,
        "commit_ref": None,
        "transcript_ref": None,
        "note": None,
    }
    source[required_field] = identity
    return source


def _upsert_evidence_ref(
    bind, *, repo_id: str, source: dict[str, str | None], created_at
) -> str:
    row = bind.execute(
        text(
            """
            SELECT id FROM evidence_refs
            WHERE repo_id = :repo_id AND canonical_hash = :canonical_hash
            """
        ),
        {"repo_id": repo_id, "canonical_hash": source["canonical_hash"]},
    ).mappings().first()
    if row is not None:
        return str(row["id"])
    evidence_id = _deterministic_id(
        "evidence-ref", repo_id, str(source["canonical_hash"])
    )
    bind.execute(
        text(
            """
            INSERT INTO evidence_refs (
              id, repo_id, kind, ref, canonical_hash, episode_event_id,
              anchor_id, memory_id, commit_ref, transcript_ref, note, created_at
            )
            VALUES (
              :id, :repo_id, :kind, :ref, :canonical_hash, :episode_event_id,
              :anchor_id, :memory_id, :commit_ref, :transcript_ref, :note,
              COALESCE(:created_at, NOW())
            )
            ON CONFLICT (repo_id, canonical_hash) DO NOTHING
            """
        ),
        {"id": evidence_id, "repo_id": repo_id, "created_at": created_at, **source},
    )
    return str(
        bind.execute(
            text(
                """
                SELECT id FROM evidence_refs
                WHERE repo_id = :repo_id AND canonical_hash = :canonical_hash
                """
            ),
            {"repo_id": repo_id, "canonical_hash": source["canonical_hash"]},
        ).scalar_one()
    )


def _insert_link(
    bind,
    *,
    repo_id: str,
    target_type: str,
    target_id: str,
    evidence_id: str,
    role: str,
    created_at=None,
) -> None:
    link_id = _deterministic_id(
        "evidence-link", repo_id, target_type, target_id, evidence_id, role
    )
    bind.execute(
        text(
            """
            INSERT INTO evidence_links (
              id, repo_id, target_type, target_id, evidence_id, evidence_role, created_at
            )
            VALUES (
              :id, :repo_id, :target_type, :target_id, :evidence_id, :role,
              COALESCE(:created_at, NOW())
            )
            ON CONFLICT (repo_id, target_type, target_id, evidence_id, evidence_role)
            DO NOTHING
            """
        ),
        {
            "id": link_id,
            "repo_id": repo_id,
            "target_type": target_type,
            "target_id": target_id,
            "evidence_id": evidence_id,
            "role": role,
            "created_at": created_at,
        },
    )


def _assert_backfill_parity(
    bind,
    *,
    expected_sources: set[tuple[str, str]],
    expected_links: set[tuple[str, str, str, str]],
) -> None:
    actual_sources = {
        (str(row["kind"]), str(row["canonical_hash"]))
        for row in bind.execute(
            text("SELECT kind, canonical_hash FROM evidence_refs")
        ).mappings()
    }
    if expected_sources != actual_sources:
        raise RuntimeError(
            "Unified evidence source parity failed: "
            f"expected={len(expected_sources)} actual={len(actual_sources)}"
        )

    actual_links = {
        (
            str(row["target_type"]),
            str(row["target_id"]),
            str(row["evidence_id"]),
            str(row["evidence_role"]),
        )
        for row in bind.execute(
            text(
                """
                SELECT target_type, target_id, evidence_id, evidence_role
                FROM evidence_links
                """
            )
        ).mappings()
    }
    if expected_links != actual_links:
        raise RuntimeError(
            "Unified evidence link parity failed: "
            f"expected={len(expected_links)} actual={len(actual_links)}"
        )


def _canonical_hash(kind: str, identity: str) -> str:
    serialized = json.dumps(
        {"kind": kind, "identity": identity},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _deterministic_id(prefix: str, *parts: str) -> str:
    serialized = json.dumps(list(parts), separators=(",", ":"), ensure_ascii=False)
    return prefix + ":" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)
