"""Migration-local SQL for retired usage proxy view shapes."""

from migrations._usage_view_sql import (
    USAGE_PROBLEM_READ_ROI_SQL,
    USAGE_PROBLEM_TOKENS_SQL,
    USAGE_READ_BEFORE_SOLVE_ROI_SQL,
)


_USAGE_PROBLEM_TOKENS_UNIFIED_EVIDENCE_JOIN_SQL = """  JOIN evidence_links el
    ON el.repo_id = p.repo_id
   AND el.target_type = 'memory'
   AND el.target_id = p.id
   AND el.evidence_role = 'supports'
  JOIN evidence_refs er ON er.id = el.evidence_id"""
_USAGE_PROBLEM_TOKENS_STRUCTURAL_SOLUTION_CANDIDATES_SQL = """solution_candidates AS (
  SELECT
    smr.subject_memory_id AS problem_id,
    s.id AS solution_id,
    s.created_at AS solution_created_at,
    ROW_NUMBER() OVER (
      PARTITION BY smr.subject_memory_id
      ORDER BY s.created_at ASC, s.id ASC
    ) AS first_row_num,
    ROW_NUMBER() OVER (
      PARTITION BY smr.subject_memory_id
      ORDER BY s.created_at DESC, s.id DESC
    ) AS latest_row_num,
    COUNT(*) OVER (
      PARTITION BY smr.subject_memory_id
    )::INTEGER AS solution_count
  FROM structural_memory_relations smr
  JOIN memories s ON s.id = smr.object_memory_id
  WHERE smr.predicate = 'solved_by'
    AND smr.status IN ('active', 'maybe_stale', 'stale')
    AND s.kind = 'solution'
    AND s.status IN ('active', 'maybe_stale', 'stale')
)"""
_USAGE_PROBLEM_TOKENS_COMPAT_SOLUTION_CANDIDATES_SQL = """solution_candidates AS (
  SELECT
    pa.problem_id,
    s.id AS solution_id,
    s.created_at AS solution_created_at,
    ROW_NUMBER() OVER (
      PARTITION BY pa.problem_id
      ORDER BY s.created_at ASC, s.id ASC
    ) AS first_row_num,
    ROW_NUMBER() OVER (
      PARTITION BY pa.problem_id
      ORDER BY s.created_at DESC, s.id DESC
    ) AS latest_row_num,
    COUNT(*) OVER (
      PARTITION BY pa.problem_id
    )::INTEGER AS solution_count
  FROM problem_attempts pa
  JOIN memories s ON s.id = pa.attempt_id
  WHERE pa.role = 'solution'
    AND s.kind = 'solution'
)"""
_USAGE_PROBLEM_TOKENS_MEMORY_EVIDENCE_JOIN_SQL = """  JOIN memory_evidence me ON me.memory_id = p.id
  JOIN evidence_refs er ON er.id = me.evidence_id"""


USAGE_PROBLEM_TOKENS_PRE_STRUCTURAL_SQL = USAGE_PROBLEM_TOKENS_SQL.replace(
    _USAGE_PROBLEM_TOKENS_STRUCTURAL_SOLUTION_CANDIDATES_SQL,
    _USAGE_PROBLEM_TOKENS_COMPAT_SOLUTION_CANDIDATES_SQL,
)
USAGE_PROBLEM_TOKENS_PRE_UNIFIED_EVIDENCE_SQL = (
    USAGE_PROBLEM_TOKENS_PRE_STRUCTURAL_SQL.replace(
        _USAGE_PROBLEM_TOKENS_UNIFIED_EVIDENCE_JOIN_SQL,
        _USAGE_PROBLEM_TOKENS_MEMORY_EVIDENCE_JOIN_SQL,
    )
)
USAGE_PROBLEM_TOKENS_LEGACY_SQL = USAGE_PROBLEM_TOKENS_PRE_STRUCTURAL_SQL.replace(
    "CREATE OR REPLACE VIEW usage_problem_tokens AS",
    "CREATE OR REPLACE VIEW usage_problem_tokens_legacy AS",
)
USAGE_PROBLEM_TOKENS_PRE_UNIFIED_EVIDENCE_LEGACY_SQL = (
    USAGE_PROBLEM_TOKENS_PRE_UNIFIED_EVIDENCE_SQL.replace(
        "CREATE OR REPLACE VIEW usage_problem_tokens AS",
        "CREATE OR REPLACE VIEW usage_problem_tokens_legacy AS",
    )
)
USAGE_PROBLEM_READ_ROI_LEGACY_SQL = USAGE_PROBLEM_READ_ROI_SQL.replace(
    "CREATE OR REPLACE VIEW usage_problem_read_roi AS",
    "CREATE OR REPLACE VIEW usage_problem_read_roi_legacy AS",
).replace("FROM usage_problem_tokens upt", "FROM usage_problem_tokens_legacy upt")
USAGE_READ_BEFORE_SOLVE_ROI_LEGACY_SQL = USAGE_READ_BEFORE_SOLVE_ROI_SQL.replace(
    "CREATE OR REPLACE VIEW usage_read_before_solve_roi AS",
    "CREATE OR REPLACE VIEW usage_read_before_solve_roi_legacy AS",
).replace("FROM usage_problem_read_roi", "FROM usage_problem_read_roi_legacy")
