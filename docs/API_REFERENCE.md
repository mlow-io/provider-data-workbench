# API Reference

All routes are served by FastAPI (`provider_directory_truth_layer.intake_api:create_workbench`). Stale optimistic-concurrency writes return `409 Conflict`; invalid inputs return `422 Unprocessable Entity`.

## Operator workbench & schema catalog

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/workbench/overview` | Executive & operations KPIs (`clean_rate_pct`, `open_discrepancies`, `held_deliveries`, `sla_at_risk`, `quarantined_rows`, `schema_variants_count`) |
| `GET` | `/api/workbench/directory` | Deduplicated clinician-location listings (`?search=&location=&network=`), Luhn NPI check status, and open issue counts |
| `GET` | `/api/schema-catalog/status` | Embedded `provider-network-intake` catalog revision and active reviewed schema variants |
| `POST` | `/api/intakes/{receipt_id}/source-schema/inspect` | Inspect CSV headers against scoped `provider-network-intake` variants |
| `POST` | `/api/intakes/{receipt_id}/source-schema/preview` | Preview Luhn NPI checks, transforms, value maps, and findings with pinned `preview_token` |
| `POST` | `/api/intakes/{receipt_id}/source-schema/proposals` | Save a previewed schema variant proposal |
| `POST` | `/api/intakes/{receipt_id}/source-schema/proposals/{proposal_id}/review` | Record human review of a schema variant (separate from row acceptance) |

## Intake, normalization & work queue

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/intakes` | List retained file receipts and current interpretation state |
| `POST` | `/api/intakes/files` | Upload raw CSV/XLSX/JSON (`filename`, `source`, `designation`, `profile`, `completeness`) |
| `GET` | `/api/intakes/{receipt_id}` | Full receipt detail, preview sample, and linked work cases |
| `GET` | `/api/intakes/{receipt_id}/profile` | Column profiling and alias candidates |
| `POST` | `/api/intakes/{receipt_id}/mapping` | Apply explicit column/sheet mapping |
| `POST` | `/api/intakes/{receipt_id}/commit` | Accept `valid_rows` or `reject` receipt (`expected_attempt` required) |
| `GET` | `/api/work` | Filterable discrepancy work queue (`network_id`, `organization_id`, `location_id`) |
| `GET` | `/api/work/{case_id}` | Discrepancy detail, before/after evidence, and append-only `work_event` timeline |
| `POST` | `/api/work/{case_id}/events` | Record `assign`, `outreach`, `triage`, `approve`, `submit`, `verify`, `needs_information`, `defer`, or `resolve` |
| `GET` | `/api/work-export.xlsx` | Export durable work handoff workbook (`.xlsx` or `/api/work-export.json`) |

## Managed feeds & approved exports

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/feeds` | List recurring feeds, contracts, jobs, and versions |
| `GET` | `/api/feed-versions/{version_id}` | Candidate or approved dataset version detail and diff counts |
| `GET` | `/api/feed-versions/{version_id}/quality-report` | Complete unclipped quality & comparison findings JSON |
| `POST` | `/api/feed-versions/{version_id}/exceptions` | Acknowledge or defer a soft quality hold (`expected_report` required) |
| `POST` | `/api/feed-versions/{version_id}/decide` | Approve or reject a dataset version (`expected_report`, `expected_current`, `idempotency_key`) |
| `GET` | `/api/feed-versions/{version_id}/review-preview` | Snapshot-pinned export preview (`location_id` optional for single-office scope) |
| `GET` | `/api/feed-versions/{version_id}/review-export` | Download complete `xlsx` or `json` approved roster (`expected_snapshot` required for `xlsx`) |
