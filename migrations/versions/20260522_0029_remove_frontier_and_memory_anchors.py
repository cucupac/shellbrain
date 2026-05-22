"""Remove frontier memories, matures_into edges, and memory anchors."""

from alembic import op


revision = "20260522_0029"
down_revision = "20260520_0028"
branch_labels = None
depends_on = None


def _drop_check_constraint(table_name: str, required_snippets: list[str]) -> None:
    """Drop one CHECK constraint by matching its rendered definition."""

    like_clauses = " AND ".join(
        f"pg_get_constraintdef(con.oid) LIKE '%{snippet}%'" for snippet in required_snippets
    )
    op.execute(
        f"""
        DO $$
        DECLARE constraint_name TEXT;
        BEGIN
          SELECT con.conname
          INTO constraint_name
          FROM pg_constraint con
          JOIN pg_class rel ON rel.oid = con.conrelid
          JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
          WHERE nsp.nspname = current_schema()
            AND rel.relname = '{table_name}'
            AND con.contype = 'c'
            AND {like_clauses}
          LIMIT 1;

          IF constraint_name IS NOT NULL THEN
            EXECUTE format('ALTER TABLE {table_name} DROP CONSTRAINT %I', constraint_name);
          END IF;
        END $$;
        """
    )


def upgrade() -> None:
    """Clean deprecated ontology records and shrink ratified constraints."""

    op.execute(
        """
        CREATE TEMP TABLE _sb_non_frontier_memory_snapshot ON COMMIT DROP AS
        SELECT id, repo_id, scope, kind, text, archived
        FROM memories
        WHERE kind <> 'frontier';
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
          non_frontier_count BIGINT;
          frontier_count BIGINT;
          matures_edge_count BIGINT;
          matures_observation_count BIGINT;
          memory_anchor_count BIGINT;
        BEGIN
          SELECT COUNT(*) INTO non_frontier_count FROM memories WHERE kind <> 'frontier';
          SELECT COUNT(*) INTO frontier_count FROM memories WHERE kind = 'frontier';
          SELECT COUNT(*) INTO matures_edge_count FROM association_edges WHERE relation_type = 'matures_into';
          SELECT COUNT(*) INTO matures_observation_count FROM association_observations WHERE relation_type = 'matures_into';
          SELECT COUNT(*) INTO memory_anchor_count FROM anchors WHERE kind = 'memory';
          RAISE NOTICE
            'Shellbrain ontology cleanup preflight: non_frontier=%, frontier=%, matures_edges=%, matures_observations=%, memory_anchors=%',
            non_frontier_count,
            frontier_count,
            matures_edge_count,
            matures_observation_count,
            memory_anchor_count;
        END $$;
        """
    )
    _convert_memory_anchors()
    _remove_frontier_records()
    _shrink_constraints()
    _assert_cleanup_safety()


def downgrade() -> None:
    """Restore the former allowed ontology values without reconstructing deleted rows."""

    op.execute(
        """
        ALTER TABLE association_observations
        DROP CONSTRAINT IF EXISTS ck_association_observations_relation_type;

        ALTER TABLE association_edges
        DROP CONSTRAINT IF EXISTS ck_association_edges_relation_type;

        ALTER TABLE memories
        DROP CONSTRAINT IF EXISTS ck_memories_kind_ratified;

        ALTER TABLE anchors
        DROP CONSTRAINT IF EXISTS ck_anchors_kind;
        """
    )
    op.execute(
        """
        ALTER TABLE memories
        ADD CONSTRAINT ck_memories_kind_ratified
        CHECK (kind IN ('problem', 'solution', 'failed_tactic', 'fact', 'preference', 'change', 'frontier'));

        ALTER TABLE association_edges
        ADD CONSTRAINT ck_association_edges_relation_type
        CHECK (relation_type IN ('depends_on', 'associated_with', 'matures_into'));

        ALTER TABLE association_observations
        ADD CONSTRAINT ck_association_observations_relation_type
        CHECK (relation_type IN ('depends_on', 'associated_with', 'matures_into'));

        ALTER TABLE anchors
        ADD CONSTRAINT ck_anchors_kind
        CHECK (kind IN ('file', 'symbol', 'line_range', 'api_route', 'db_table', 'schema', 'config_key', 'test', 'metric', 'log', 'doc', 'commit', 'memory'));
        """
    )


def _convert_memory_anchors() -> None:
    """Convert memory anchors into first-class concept-memory links."""

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM anchors
            WHERE kind = 'memory'
              AND (
                locator_json IS NULL
                OR jsonb_typeof(locator_json) <> 'object'
                OR NOT (locator_json ? 'memory_id')
                OR btrim(locator_json ->> 'memory_id') = ''
              )
          ) THEN
            RAISE EXCEPTION 'Cannot convert memory anchors with missing locator_json.memory_id.';
          END IF;

          IF EXISTS (
            SELECT 1
            FROM anchors a
            LEFT JOIN memories m ON m.id = a.locator_json ->> 'memory_id'
            WHERE a.kind = 'memory'
              AND m.id IS NULL
          ) THEN
            RAISE EXCEPTION 'Cannot convert memory anchors that reference missing memories.';
          END IF;

          IF EXISTS (
            SELECT 1
            FROM anchors a
            JOIN memories m ON m.id = a.locator_json ->> 'memory_id'
            WHERE a.kind = 'memory'
              AND a.repo_id <> m.repo_id
          ) THEN
            RAISE EXCEPTION 'Cannot convert memory anchors whose repo_id disagrees with the referenced memory.';
          END IF;

          IF EXISTS (
            SELECT 1
            FROM concept_evidence ce
            JOIN anchors a ON a.id = ce.anchor_id
            WHERE a.kind = 'memory'
              AND ce.evidence_kind <> 'anchor'
          ) THEN
            RAISE EXCEPTION 'Cannot convert concept evidence with a memory anchor stored under a non-anchor evidence kind.';
          END IF;

          IF EXISTS (
            SELECT 1
            FROM concept_groundings g
            JOIN anchors a ON a.id = g.anchor_id
            WHERE a.kind = 'memory'
              AND g.superseded_by_id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1
                FROM concept_groundings sg
                JOIN anchors sa ON sa.id = sg.anchor_id
                WHERE sg.id = g.superseded_by_id
                  AND sa.kind = 'memory'
              )
          ) THEN
            RAISE EXCEPTION 'Cannot convert memory-anchor groundings superseded by non-memory-anchor groundings.';
          END IF;
        END $$;
        """
    )
    op.execute(
        """
        WITH memory_anchor_groundings AS (
          SELECT
            g.*,
            a.locator_json ->> 'memory_id' AS anchored_memory_id,
            m.kind AS memory_kind
          FROM concept_groundings g
          JOIN anchors a ON a.id = g.anchor_id
          JOIN memories m ON m.id = a.locator_json ->> 'memory_id'
          WHERE a.kind = 'memory'
        ),
        link_targets AS (
          SELECT
            mag.*,
            CASE
              WHEN mag.memory_kind = 'solution' THEN 'solution_for'
              WHEN mag.memory_kind = 'failed_tactic' THEN 'failed_tactic_for'
              ELSE 'example_of'
            END AS link_role
          FROM memory_anchor_groundings mag
        ),
        resolved_links AS (
          SELECT
            lt.*,
            COALESCE(
              existing.id,
              'converted-memory-anchor-link:' ||
              md5(lt.repo_id || ':' || lt.concept_id || ':' || lt.link_role || ':' || lt.anchored_memory_id)
            ) AS memory_link_id,
            existing.id IS NULL AS needs_insert
          FROM link_targets lt
          LEFT JOIN concept_memory_links existing
            ON existing.repo_id = lt.repo_id
           AND existing.concept_id = lt.concept_id
           AND existing.role = lt.link_role
           AND existing.memory_id = lt.anchored_memory_id
           AND existing.status = 'active'
        )
        INSERT INTO concept_memory_links (
          id,
          repo_id,
          concept_id,
          role,
          memory_id,
          status,
          confidence,
          observed_at,
          validated_at,
          source_kind,
          source_ref,
          superseded_by_id,
          created_by,
          created_at,
          updated_at
        )
        SELECT
          resolved_links.memory_link_id,
          resolved_links.repo_id,
          resolved_links.concept_id,
          resolved_links.link_role,
          resolved_links.anchored_memory_id,
          resolved_links.status,
          resolved_links.confidence,
          resolved_links.observed_at,
          resolved_links.validated_at,
          resolved_links.source_kind,
          resolved_links.source_ref,
          superseding.memory_link_id,
          resolved_links.created_by,
          resolved_links.created_at,
          resolved_links.updated_at
        FROM resolved_links
        LEFT JOIN resolved_links superseding
          ON superseding.id = resolved_links.superseded_by_id
        WHERE resolved_links.needs_insert
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        WITH memory_anchor_groundings AS (
          SELECT
            g.*,
            a.id AS memory_anchor_id,
            a.locator_json ->> 'memory_id' AS anchored_memory_id,
            m.kind AS memory_kind
          FROM concept_groundings g
          JOIN anchors a ON a.id = g.anchor_id
          JOIN memories m ON m.id = a.locator_json ->> 'memory_id'
          WHERE a.kind = 'memory'
        ),
        link_targets AS (
          SELECT
            mag.*,
            CASE
              WHEN mag.memory_kind = 'solution' THEN 'solution_for'
              WHEN mag.memory_kind = 'failed_tactic' THEN 'failed_tactic_for'
              ELSE 'example_of'
            END AS link_role
          FROM memory_anchor_groundings mag
        ),
        resolved_links AS (
          SELECT
            lt.*,
            COALESCE(
              existing.id,
              'converted-memory-anchor-link:' ||
              md5(lt.repo_id || ':' || lt.concept_id || ':' || lt.link_role || ':' || lt.anchored_memory_id)
            ) AS memory_link_id
          FROM link_targets lt
          LEFT JOIN concept_memory_links existing
            ON existing.repo_id = lt.repo_id
           AND existing.concept_id = lt.concept_id
           AND existing.role = lt.link_role
           AND existing.memory_id = lt.anchored_memory_id
           AND existing.status = 'active'
        )
        INSERT INTO concept_evidence (
          id,
          repo_id,
          target_type,
          target_id,
          evidence_kind,
          anchor_id,
          memory_id,
          commit_ref,
          transcript_ref,
          note,
          created_at
        )
        SELECT
          'converted-memory-anchor-evidence:' || ce.id,
          ce.repo_id,
          'memory_link',
          rl.memory_link_id,
          CASE
            WHEN ce.evidence_kind = 'anchor' AND ce.anchor_id = rl.memory_anchor_id
              THEN 'memory'
            ELSE ce.evidence_kind
          END,
          CASE
            WHEN ce.evidence_kind = 'anchor' AND ce.anchor_id = rl.memory_anchor_id
              THEN NULL
            ELSE ce.anchor_id
          END,
          CASE
            WHEN ce.evidence_kind = 'anchor' AND ce.anchor_id = rl.memory_anchor_id
              THEN rl.anchored_memory_id
            ELSE ce.memory_id
          END,
          ce.commit_ref,
          ce.transcript_ref,
          ce.note,
          ce.created_at
        FROM concept_evidence ce
        JOIN resolved_links rl
          ON ce.target_type = 'grounding'
         AND ce.target_id = rl.id
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        WITH memory_anchors AS (
          SELECT id, locator_json ->> 'memory_id' AS anchored_memory_id
          FROM anchors
          WHERE kind = 'memory'
        )
        UPDATE concept_evidence ce
        SET
          evidence_kind = 'memory',
          memory_id = ma.anchored_memory_id,
          anchor_id = NULL
        FROM memory_anchors ma
        WHERE ce.anchor_id = ma.id
          AND ce.evidence_kind = 'anchor';
        """
    )
    op.execute(
        """
        DELETE FROM concept_evidence ce
        USING concept_groundings g
        JOIN anchors a ON a.id = g.anchor_id
        WHERE ce.target_type = 'grounding'
          AND ce.target_id = g.id
          AND a.kind = 'memory';

        DELETE FROM concept_groundings g
        USING anchors a
        WHERE g.anchor_id = a.id
          AND a.kind = 'memory';
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM concept_evidence ce
            JOIN anchors a ON a.id = ce.anchor_id
            WHERE a.kind = 'memory'
          ) THEN
            RAISE EXCEPTION 'Cannot delete memory anchors while concept evidence still references them.';
          END IF;
        END $$;

        DELETE FROM anchors
        WHERE kind = 'memory';
        """
    )


def _remove_frontier_records() -> None:
    """Delete deprecated frontier rows and direct matures_into remnants."""

    op.execute(
        """
        DELETE FROM association_observations
        WHERE relation_type = 'matures_into';

        DELETE FROM association_edges
        WHERE relation_type = 'matures_into';

        DELETE FROM memories
        WHERE kind = 'frontier';

        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM association_edges WHERE relation_type = 'matures_into') THEN
            RAISE EXCEPTION 'matures_into association edges remain after cleanup.';
          END IF;
          IF EXISTS (SELECT 1 FROM association_observations WHERE relation_type = 'matures_into') THEN
            RAISE EXCEPTION 'matures_into association observations remain after cleanup.';
          END IF;
        END $$;
        """
    )


def _shrink_constraints() -> None:
    """Replace widened ontology constraints with the cleaned value sets."""

    _drop_check_constraint("memories", ["kind", "frontier"])
    _drop_check_constraint("association_edges", ["relation_type", "matures_into"])
    _drop_check_constraint("association_observations", ["relation_type", "matures_into"])
    _drop_check_constraint("anchors", ["kind", "memory"])
    op.execute(
        """
        ALTER TABLE memories
        ADD CONSTRAINT ck_memories_kind_ratified
        CHECK (kind IN ('problem', 'solution', 'failed_tactic', 'fact', 'preference', 'change'));

        ALTER TABLE association_edges
        ADD CONSTRAINT ck_association_edges_relation_type
        CHECK (relation_type IN ('depends_on', 'associated_with'));

        ALTER TABLE association_observations
        ADD CONSTRAINT ck_association_observations_relation_type
        CHECK (relation_type IN ('depends_on', 'associated_with'));

        ALTER TABLE anchors
        ADD CONSTRAINT ck_anchors_kind
        CHECK (kind IN ('file', 'symbol', 'line_range', 'api_route', 'db_table', 'schema', 'config_key', 'test', 'metric', 'log', 'doc', 'commit'));
        """
    )


def _assert_cleanup_safety() -> None:
    """Fail the migration if cleanup touched anything beyond the deprecated surface."""

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM memories WHERE kind = 'frontier') THEN
            RAISE EXCEPTION 'frontier memories remain after ontology cleanup.';
          END IF;
          IF EXISTS (SELECT 1 FROM anchors WHERE kind = 'memory') THEN
            RAISE EXCEPTION 'memory anchors remain after ontology cleanup.';
          END IF;
          IF EXISTS (
            SELECT 1
            FROM _sb_non_frontier_memory_snapshot s
            LEFT JOIN memories m ON m.id = s.id
            WHERE m.id IS NULL
               OR m.repo_id IS DISTINCT FROM s.repo_id
               OR m.scope IS DISTINCT FROM s.scope
               OR m.kind IS DISTINCT FROM s.kind
               OR m.text IS DISTINCT FROM s.text
               OR m.archived IS DISTINCT FROM s.archived
          ) THEN
            RAISE EXCEPTION 'Non-frontier memory rows changed during ontology cleanup.';
          END IF;
        END $$;
        """
    )
