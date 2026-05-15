"""Add scenario-record support for knowledge-builder problem runs."""

from alembic import op

revision = "20260515_0019"
down_revision = "20260513_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Extend problem runs with event evidence and builder actor support."""

    op.execute(
        """
        ALTER TABLE problem_runs
          ADD COLUMN opened_event_id TEXT REFERENCES episode_events(id) ON DELETE SET NULL,
          ADD COLUMN closed_event_id TEXT REFERENCES episode_events(id) ON DELETE SET NULL;

        CREATE INDEX idx_problem_runs_opened_event
          ON problem_runs(opened_event_id);
        CREATE INDEX idx_problem_runs_closed_event
          ON problem_runs(closed_event_id);
        CREATE UNIQUE INDEX uq_problem_runs_scenario_natural_key
          ON problem_runs(repo_id, episode_id, problem_memory_id, opened_event_id)
          WHERE opened_event_id IS NOT NULL;

        ALTER TABLE problem_runs DROP CONSTRAINT ck_problem_runs_opened_by;
        ALTER TABLE problem_runs
          ADD CONSTRAINT ck_problem_runs_opened_by
          CHECK (opened_by IN (
            'worker', 'librarian', 'manual', 'system', 'build_knowledge'
          ));

        ALTER TABLE problem_runs DROP CONSTRAINT ck_problem_runs_closed_by;
        ALTER TABLE problem_runs
          ADD CONSTRAINT ck_problem_runs_closed_by
          CHECK (
            closed_by IS NULL
            OR closed_by IN (
              'worker', 'librarian', 'manual', 'system', 'build_knowledge'
            )
          );

        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
              FROM pg_constraint con
              JOIN pg_class rel ON rel.oid = con.conrelid
              JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
             WHERE nsp.nspname = current_schema()
               AND rel.relname = 'operation_invocations'
               AND con.contype = 'c'
               AND con.conname = 'ck_operation_invocations_command'
          ) THEN
            ALTER TABLE operation_invocations
              DROP CONSTRAINT ck_operation_invocations_command;
            ALTER TABLE operation_invocations
              ADD CONSTRAINT ck_operation_invocations_command
              CHECK (command IN (
                'read',
                'create',
                'update',
                'events',
                'concept',
                'concept.add',
                'concept.show',
                'concept.update',
                'recall',
                'scenario.record'
              ));
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Remove scenario-record columns and restore prior command checks."""

    op.execute(
        """
        DROP INDEX IF EXISTS uq_problem_runs_scenario_natural_key;
        DROP INDEX IF EXISTS idx_problem_runs_closed_event;
        DROP INDEX IF EXISTS idx_problem_runs_opened_event;

        ALTER TABLE problem_runs DROP CONSTRAINT ck_problem_runs_opened_by;
        ALTER TABLE problem_runs
          ADD CONSTRAINT ck_problem_runs_opened_by
          CHECK (opened_by IN ('worker', 'librarian', 'manual', 'system'));

        ALTER TABLE problem_runs DROP CONSTRAINT ck_problem_runs_closed_by;
        ALTER TABLE problem_runs
          ADD CONSTRAINT ck_problem_runs_closed_by
          CHECK (
            closed_by IS NULL
            OR closed_by IN ('worker', 'librarian', 'manual', 'system')
          );

        ALTER TABLE problem_runs
          DROP COLUMN IF EXISTS closed_event_id,
          DROP COLUMN IF EXISTS opened_event_id;

        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
              FROM pg_constraint con
              JOIN pg_class rel ON rel.oid = con.conrelid
              JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
             WHERE nsp.nspname = current_schema()
               AND rel.relname = 'operation_invocations'
               AND con.contype = 'c'
               AND con.conname = 'ck_operation_invocations_command'
          ) THEN
            ALTER TABLE operation_invocations
              DROP CONSTRAINT ck_operation_invocations_command;
            ALTER TABLE operation_invocations
              ADD CONSTRAINT ck_operation_invocations_command
              CHECK (command IN (
                'read',
                'create',
                'update',
                'events',
                'concept',
                'recall'
              ));
          END IF;
        END $$;
        """
    )
