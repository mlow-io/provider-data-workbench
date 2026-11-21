# D1.2 headless native intake evidence — 2026-11-14

Public-ancestry baseline `760acde`, uncommitted implementation on `feat/provider-data-operations-plan`. [File hashes](files.json) identify the checked working tree. This is a headless service/API qualification; no native GUI, browser usability, live payer endpoint or full standards conformance is claimed.

## Implemented

The `fhir-plannet-r4` upload profile uses the existing receipt/artifact/attempt ledger with a profile-specific interpreter and native preview envelope. Eligible resource acceptance writes schema-11 observations with nullable provider/location projections and a receipt-scoped idempotent decision. It bypasses clinic case/participation/feed generation. Identical uncertain retries recover the original attempt; altered intent, terminal conflicts and fresh stale requests fail atomically. Repeated deliveries keep new receipts/decisions while reusing original accepted observations.

Comparison records retain Practitioner and role/location anchors with exact supporting references. Field options/decisions, impact targets and follow-up carry those references. Selected JSON/XLSX source context includes contributing native resources while excluding SOUTH as selected NORTH evidence. Original Bundle context remains retained separately. Interactive previews are sampled with complete counts; evidence packet downloads remain complete. Clinic `/dataset` export rejects native resources to avoid labeling reference evidence as a validated clinic dataset.

The integration review found a parser structural-check defect: DomainResource narrative `text` was treated like scalar HumanName text. The check now distinguishes narratives and has a regression using the zero-error Location specimen. Nested identifier-only References no longer acquire a false array-shape error.

## Verification and inspected outputs

Focused command `.venv/bin/python -m pytest -q tests/test_fhir_store.py` passed 20 cases. Combined parser/native-service command passed 98 cases after the narrative correction. The tests use owned temporary databases and fixtures.

The integrated case uploads native evidence plus a clinic row, explicitly accepts resources, approves clinician and NORTH-location links, selects the native phone, exports JSON, opens XLSX and reconstructs its chunked payload to assert exact equality. The selected native context contains practitioner, clinic, network, NORTH location and NORTH role locators; SOUTH location/role are excluded. Native impact targets preserve supporting references. Reinterpretation makes the old export snapshot stale.

Other checked boundaries include a Location without NPI, eight accepted resources without automatic cases/bindings/feed versions, restart, conflicting/identical request retries, separate duplicate receipts, source isolation, malformed/empty/rejected evidence, invalid actor/request shapes, mapping rejection, HTTP stale conflicts, bounded 80-resource previews with full packet counts, concurrent identical acceptance and a trigger-induced mid-insert failure with complete rollback and successful retry.

A populated managed clinic feed was approved before native intake. Its approved-version export was compared as exact canonical JSON before/after native acceptance; the current version and work-event history were unchanged. SQLite integrity was `ok` and foreign-key violations were zero.

`PATH="$PWD/.venv/bin:$PATH" make validate` passed 682 tests and pipeline validation before the final narrative regression was added. Pipeline output retained 12 records, 11 findings and six discrepancies in invocation-owned storage. After the narrative correction, the final `.venv/bin/python -m pytest -q` passed 683 tests in 24.89 seconds. No test failure occurred in these invocations; the existing Starlette TestClient deprecation warning remains.

## Open gates

Native upload/acceptance/reconciliation/export are implemented headlessly. D1.3 GUI integration and browser qualification remain open, as does complete offline terminology validation from D1.1. No source-native graph or acceptance decision establishes reviewed identity, external participation, correction verification or a payer update. The broader D2–D4/H1/H2 work remains active.
