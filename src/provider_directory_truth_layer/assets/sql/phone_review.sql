-- SQLite 3.25+; one row per open work_case with field_name = 'phone'.
-- Parameters: :as_of (operator calendar date), :overdue_only (0 or 1).
-- Evidence counts cover work_evidence observation links, not all possible evidence.
WITH latest AS (
  SELECT e.case_id, e.action, e.occurred_at,
         row_number() OVER (PARTITION BY e.case_id ORDER BY e.occurred_at DESC, e.id DESC) AS position
  FROM work_event AS e
), evidence AS (
  SELECT case_id, count(*) AS observation_links
  FROM work_evidence
  GROUP BY case_id
), cases AS (
  SELECT c.id AS case_id, c.provider_name, c.location_id, c.issue, c.status,
         c.owner, c.follow_up, c.risk_level,
         CASE WHEN c.owner IS NULL OR trim(c.owner) = '' THEN 1 ELSE 0 END AS unassigned,
         CASE
           WHEN c.follow_up IS NULL OR trim(c.follow_up) = '' THEN 'unscheduled'
           WHEN length(c.follow_up) != 10
             OR c.follow_up NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
             OR date(c.follow_up, '+0 days') IS NULL
             OR date(c.follow_up, '+0 days') != c.follow_up THEN 'invalid_date'
           WHEN c.follow_up < :as_of THEN 'overdue'
           WHEN c.follow_up = :as_of THEN 'due_today'
           ELSE 'upcoming'
         END AS timing,
         coalesce(ev.observation_links, 0) AS linked_observation_count,
         l.action AS latest_action, l.occurred_at AS latest_event_at
  FROM work_case AS c
  LEFT JOIN evidence AS ev ON ev.case_id = c.id
  LEFT JOIN latest AS l ON l.case_id = c.id AND l.position = 1
  WHERE c.field_name = 'phone' AND c.status NOT IN ('resolved', 'verified')
)
SELECT * FROM cases
WHERE :overdue_only = 0 OR timing = 'overdue'
ORDER BY CASE timing WHEN 'overdue' THEN 0 WHEN 'due_today' THEN 1
         WHEN 'upcoming' THEN 2 WHEN 'unscheduled' THEN 3 ELSE 4 END,
         follow_up, case_id;
