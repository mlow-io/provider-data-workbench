# Data Model

Persistence lives in SQLite (`directory.sqlite3` plus optional `source-schema-catalog.sqlite3` managed by `provider-network-intake`) alongside immutable SHA-256 artifact files.

## Core domain separation

Provider directory bugs most often happen when systems collapse three distinct concepts into one flat row:

| Entity | Identity & grain | Why it stays separate |
|---|---|---|
| **Clinician** | `NPI` (`10` digits, CMS Luhn validated) + `provider_name` + NUCC taxonomy | One clinician can practice across multiple clinics and networks with different scheduling lines |
| **Practice location** | Source-native `location_id` + `address` / `suite` / `city` / `state` / `zip` | A clinic phone change at Nashville Midtown must not overwrite Franklin Cool Springs |
| **Network participation** | `organization` + `network` + `listed_status` + `effective_date` | Suppressing a clinician in a public directory (`directory_visible=false`) is not contract termination |

## Key SQLite tables

- `artifact` & `receipt` & `attempt` — Content-addressed raw input files, receipt metadata (`source`, `designation`, `profile`, `scope`), and immutable interpretation attempts (`spec`, `preview`, `state`).
- `observation` & `observation_normalization` — Accepted valid rows linked to their exact source `locator` (`row:2`, `Clinic roster!3`, `$.entry[0].resource`) and normalization provenance. Quarantined rows never enter `observation`.
- `work_case`, `work_evidence`, & `work_event` — Open/resolved discrepancy cases with optimistic `version` locking and SQLite triggers (`work_event_no_update`, `work_event_no_delete`) enforcing an append-only audit trail.
- `feed`, `feed_contract`, `feed_delivery`, `feed_version`, `feed_decision`, & `feed_exception` — Recurring roster ingestion versions where `feed.current_version` changes only after explicit human approval of a non-held candidate.
- `organization`, `network`, `practice_location`, & `identity_binding` — Explicit catalog identities and versioned source-code bindings.

## Quarantine & snapshot safety

- Rows with missing required fields (`npi`, `provider_name`, `address`, `city`, `state`, `zip`, `phone`), malformed phones/ZIPs, or invalid identifiers are isolated in `quarantine` with exact row locators.
- Approved exports (`JSON` and multi-sheet `XLSX`) bind to an explicit `expected_snapshot` token computed from the pinned version state and optional `location_id` office scope so downloaded files always match what the operator previewed.
