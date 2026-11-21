-- SQLite 3; one row per work_case needing assignment or overdue follow-up.
-- Parameters: :as_of (ISO YYYY-MM-DD local operator date), :include_closed (0 or 1).
-- Null owner means unassigned; a follow_up equal to as_of is due today, not overdue.
WITH classified AS (
  SELECT c.id AS case_id, c.status, c.owner, c.follow_up, c.risk_level,
         c.provider_name, c.field_name,
         CASE WHEN c.owner IS NULL OR trim(c.owner) = '' THEN 1 ELSE 0 END AS unassigned,
         CASE WHEN length(c.follow_up) = 10
           AND c.follow_up GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
           AND date(c.follow_up, '+0 days') = c.follow_up
           AND c.follow_up < :as_of THEN 1 ELSE 0 END AS overdue
  FROM work_case AS c
  WHERE (:include_closed = 1 OR c.status NOT IN ('verified', 'resolved'))
)
SELECT * FROM classified
WHERE unassigned = 1 OR overdue = 1
ORDER BY overdue DESC, unassigned DESC, follow_up, case_id;
