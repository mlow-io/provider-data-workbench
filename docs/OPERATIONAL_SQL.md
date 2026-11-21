# Operational SQL questions

This source-checkout tool reads an existing durable intake SQLite database. It does not initialize `IntakeStore`, run migrations, import files, or change workflow state. Use a fixture-owned database when practicing. The questions live in [`sql/operations/`](../sql/operations/) and declare their row grain and parameters in their opening comments.

Run from the repository root with an editable install, or set `PYTHONPATH=src`:

```sh
PYTHONPATH=src python3 -m provider_directory_truth_layer.operations_sql --help
PYTHONPATH=src python3 -m provider_directory_truth_layer.operations_sql --db /path/to/intake.sqlite3 follow-up --as-of 2026-02-01
PYTHONPATH=src python3 -m provider_directory_truth_layer.operations_sql --db /path/to/intake.sqlite3 phone-review --as-of 2026-02-01 --overdue-only
PYTHONPATH=src python3 -m provider_directory_truth_layer.operations_sql --db /path/to/intake.sqlite3 lineage --case-id CASE_ID
PYTHONPATH=src python3 -m provider_directory_truth_layer.operations_sql --db /path/to/intake.sqlite3 latest-event
PYTHONPATH=src python3 -m provider_directory_truth_layer.operations_sql --db /path/to/intake.sqlite3 compare --left-attempt ACCEPTED_A --right-attempt ACCEPTED_B
```

Results are JSON arrays. Exact IDs come from the selected database; no sample ID is inferred by the runner.

### Reproduce the phone-review exercise

After installing the project dependencies, create a new synthetic root beneath a directory you own. The script refuses to reuse an existing root and leaves its new database and retained source artifacts for inspection:

```sh
PYTHONPATH=src python3 scripts/prepare_phone_review_demo.py --root /path/to/new-phone-demo
PYTHONPATH=src python3 -m provider_directory_truth_layer.operations_sql --db /path/to/new-phone-demo/directory.sqlite3 phone-review --as-of 2026-02-01
PYTHONPATH=src python3 -m provider_directory_truth_layer.operations_sql --db /path/to/new-phone-demo/directory.sqlite3 phone-review --as-of 2026-02-01 --overdue-only
PYTHONPATH=src python3 -m provider_directory_truth_layer.operations_sql --db /path/to/new-phone-demo/directory.sqlite3 lineage --case-id CASE_ID
```

The script prints the generated NORTH case ID. At the fixed exercise date, NORTH is overdue and SOUTH is due today. Each case has two linked observations from distinct retained synthetic deliveries, but each appears once in the report. Follow NORTH's ID with `lineage` to inspect both source rows. The example includes synthetic names and data only; its dates are chosen for reproducibility, not to describe current operations. If preparation is interrupted, inspect the created root and choose another new path for a retry.

| Question | One result row means | Parameters | Synthetic fixture expectation |
| --- | --- | --- | --- |
| `follow-up` | One work case needing assignment or overdue follow-up, excluding resolved/verified cases by default. | `--as-of YYYY-MM-DD` (default today); `--include-closed` includes resolved/verified cases. | At `2026-02-01`, `c1`, overdue deferred `c4`, and unassigned due-today `c7` are returned. |
| `phone-review` | One open phone work case, including its timing, locally asserted owner, latest event and count of linked observations. | `--as-of YYYY-MM-DD` (default local date); `--overdue-only` restricts to dates strictly before it. | On the test fixture at `2026-02-01`, the overdue set is `c1` and `c4`; `c1` has three linked observations but appears once. |
| `lineage` | One work-case/linked-observation pair, including original and normalized row payload, locator, attempt, receipt, and artifact hash. | `--case-id` exact case ID. | `c1` has three rows, `o1`–`o3`; `c2` has one row with null observation and receipt fields. |
| `latest-event` | One work case and its latest event, or null event fields if it has no events. | None. | Seven case rows; `c1` selects action `note` over `assign` at the same timestamp using higher event ID. |
| `compare` | One source-native identity present in either selected accepted delivery, with old/new normalized JSON and row locators. | Two explicit attempt IDs. | `a1` versus `a2`: `native-a` changed, `native-b` missing from right, `native-c` new. |

All queries use SQLite syntax and bound parameters. `latest-event` requires window-function support (SQLite 3.25+); `compare` requires JSON1. The runner opens `mode=ro` and enables `query_only`. `follow-up` treats null/blank owner as unassigned, null follow-up as not overdue, and a date equal to `as_of` as due today. `lineage` preserves cases without links through left joins. The latest-event query ranks events before joining them to cases, so a case with several evidence links cannot multiply its result.

`phone-review` answers: **which open phone cases need attention, and where can I investigate the evidence?** Without `--overdue-only`, timing is `overdue`, `due_today`, `upcoming`, `unscheduled`, or `invalid_date`. The report counts `work_evidence` observation links, not all forms of source or review evidence; zero links does not mean no evidence exists. Use the returned case ID with `lineage` to inspect retained observation details and available network review evidence. Multiple observations and events are aggregated or ranked before joining to cases, keeping one row per case. A latest event is not proof of external verification. The report is a current local snapshot, not an as-of historical reconstruction, and local owner names are assertions. Results may contain provider details; choose an appropriate private destination before saving them.

For `follow-up`, malformed or blank follow-up dates are not treated as overdue; unassigned cases still appear. For `phone-review`, malformed dates are explicitly `invalid_date`. The UI overdue filter uses the operator's local calendar date; specify `--as-of` explicitly when reproducing a report on another machine. Neither date filtering nor a completed export changes any case.

Comparison selects two **accepted attempts**. A `duplicate_delivery` attempt is accepted but has no new observations: its recorded `preview.reuses_attempt` must point to a committed attempt of the same source, profile, and scope. Selecting two attempts that resolve to the same committed interpretation is rejected. Different source, profile, or declared `metadata.scope` values are rejected. The key is `native_id` plus normalized `location_id` within that source/scope; null and empty location IDs share the empty key. A missing/blank native ID or duplicate key makes that selected comparison ambiguous, so the runner rejects it. Rows with null *field values* remain comparable, and JSON null differs from an absent field or empty string. `missing_from_right` means absent from this bounded delivery, **not** terminated or removed. This tool compares accepted rows only and does not alter the application's current preview comparison semantics or claim a complete source history.

Fixture regression: `pytest -q tests/test_operations_sql.py`. The test hashes the SQLite file and an original artifact before/after the read-only questions; it also verifies the durable database and WAL bytes with a live WAL writer. SQLite may update transient `-shm` reader-lock bytes while answering a read query.

For schema v4 network deliveries, `compare` also checks roster kind and the explicitly configured local network set. Its key includes native ID plus bound network, provider and practice-location IDs; equal native keys across networks remain separate rows. It rejects clinic-versus-network and unrelated network-set selections. `lineage` includes missing/blocked source-comparison rows from `lineage_review.sql` when available, with null accepted observation IDs and an explicit comparison status. It still retains a null lineage row for a case with no evidence of either kind.
