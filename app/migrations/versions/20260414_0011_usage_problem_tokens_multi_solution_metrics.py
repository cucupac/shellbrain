"""Expand usage_problem_tokens with latest-solution metrics."""

from alembic import op

from app.periphery.db.models.views import USAGE_PROBLEM_TOKENS_SQL

revision = "20260414_0011"
down_revision = "20260414_0010"
branch_labels = None
depends_on = None


PREVIOUS_USAGE_PROBLEM_TOKENS_SQL = """
CREATE OR REPLACE VIEW usage_problem_tokens AS
WITH session_quality AS (
  SELECT
    repo_id,
    host_app,
    host_session_key,
    BOOL_OR(capture_quality = 'exact') AS has_exact_rows,
    BOOL_OR(
      capture_quality = 'exact'
      AND (
        COALESCE(input_tokens, 0) > 0
        OR COALESCE(output_tokens, 0) > 0
        OR COALESCE(cached_input_tokens_total, 0) > 0
        OR COALESCE(reasoning_output_tokens, 0) > 0
      )
    ) AS has_nonzero_exact_rows,
    BOOL_OR(capture_quality = 'estimated') AS has_estimated_rows
  FROM model_usage
  GROUP BY repo_id, host_app, host_session_key
),
preferred_rows AS (
  SELECT mu.*
  FROM model_usage mu
  JOIN session_quality sq
    ON sq.repo_id = mu.repo_id
   AND sq.host_app = mu.host_app
   AND sq.host_session_key = mu.host_session_key
  WHERE (
    sq.has_nonzero_exact_rows
    AND mu.capture_quality = 'exact'
  ) OR (
    NOT sq.has_nonzero_exact_rows
    AND mu.capture_quality = 'estimated'
  ) OR (
    NOT sq.has_nonzero_exact_rows
    AND NOT sq.has_estimated_rows
    AND sq.has_exact_rows
    AND mu.capture_quality = 'exact'
  )
),
problem_threads AS (
  SELECT
    p.id AS problem_id,
    p.repo_id,
    p.created_at AS problem_created_at,
    (
      ARRAY_AGG(ep.thread_id ORDER BY ee.created_at ASC, ee.seq ASC)
      FILTER (WHERE ep.thread_id IS NOT NULL)
    )[1] AS thread_id
  FROM memories p
  JOIN memory_evidence me ON me.memory_id = p.id
  JOIN evidence_refs er ON er.id = me.evidence_id
  JOIN episode_events ee ON ee.id = COALESCE(er.episode_event_id, er.ref)
  JOIN episodes ep ON ep.id = ee.episode_id
  WHERE p.kind = 'problem'
  GROUP BY p.id, p.repo_id, p.created_at
),
first_solutions AS (
  SELECT
    pa.problem_id,
    s.id AS solution_id,
    s.created_at AS solution_created_at,
    ROW_NUMBER() OVER (
      PARTITION BY pa.problem_id
      ORDER BY s.created_at ASC, s.id ASC
    ) AS row_num
  FROM problem_attempts pa
  JOIN memories s ON s.id = pa.attempt_id
  WHERE pa.role = 'solution'
    AND s.kind = 'solution'
),
problem_windows AS (
  SELECT
    pt.repo_id,
    pt.problem_id,
    pt.thread_id,
    pt.problem_created_at,
    fs.solution_id,
    fs.solution_created_at
  FROM problem_threads pt
  JOIN first_solutions fs
    ON fs.problem_id = pt.problem_id
   AND fs.row_num = 1
  WHERE pt.thread_id IS NOT NULL
)
SELECT
  pw.repo_id,
  pw.problem_id,
  pw.solution_id,
  pw.thread_id,
  pw.problem_created_at,
  pw.solution_created_at,
  COUNT(pr.id)::INTEGER AS usage_row_count,
  COALESCE(SUM(pr.input_tokens), 0)::BIGINT AS input_tokens,
  COALESCE(SUM(pr.output_tokens), 0)::BIGINT AS output_tokens,
  COALESCE(SUM(pr.reasoning_output_tokens), 0)::BIGINT AS reasoning_output_tokens,
  COALESCE(SUM(pr.cached_input_tokens_total), 0)::BIGINT AS cached_input_tokens_total,
  COALESCE(SUM(pr.cache_read_input_tokens), 0)::BIGINT AS cache_read_input_tokens,
  COALESCE(SUM(pr.cache_creation_input_tokens), 0)::BIGINT AS cache_creation_input_tokens,
  (
    COALESCE(SUM(pr.input_tokens), 0)
    + COALESCE(SUM(pr.output_tokens), 0)
  )::BIGINT AS fresh_work_tokens,
  (
    COALESCE(SUM(pr.input_tokens), 0)
    + COALESCE(SUM(pr.cached_input_tokens_total), 0)
    + COALESCE(SUM(pr.output_tokens), 0)
  )::BIGINT AS all_tokens_including_cache
FROM problem_windows pw
LEFT JOIN preferred_rows pr
  ON pr.repo_id = pw.repo_id
 AND pr.thread_id = pw.thread_id
 AND pr.occurred_at >= pw.problem_created_at
 AND pr.occurred_at <= pw.solution_created_at
GROUP BY
  pw.repo_id,
  pw.problem_id,
  pw.solution_id,
  pw.thread_id,
  pw.problem_created_at,
  pw.solution_created_at;
"""


def upgrade() -> None:
    """Replace usage_problem_tokens with first- and latest-solution metrics."""

    op.execute(USAGE_PROBLEM_TOKENS_SQL)


def downgrade() -> None:
    """Restore the prior usage_problem_tokens definition."""

    op.execute(PREVIOUS_USAGE_PROBLEM_TOKENS_SQL)
