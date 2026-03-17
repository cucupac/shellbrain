"""This module defines view SQL strings used to build derived read-model views."""


CURRENT_FACT_SNAPSHOT_SQL = """
CREATE OR REPLACE VIEW current_fact_snapshot AS
SELECT m.*
FROM memories m
WHERE m.kind = 'fact'
  AND m.archived = FALSE
  AND NOT EXISTS (
    SELECT 1 FROM fact_updates fu WHERE fu.old_fact_id = m.id
  );
"""


GLOBAL_UTILITY_SQL = """
CREATE OR REPLACE VIEW global_utility AS
SELECT memory_id, AVG(vote) AS utility_mean, COUNT(*) AS observations
FROM utility_observations
GROUP BY memory_id;
"""
