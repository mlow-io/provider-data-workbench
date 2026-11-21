# API reference: unified intake workbench and compatibility routes

Updated 2026-10-26. Start the unified application with `PYTHONPATH=src python3 -m provider_directory_truth_layer.intake_api`. It serves intake, durable work and compatibility review/remediation routes on port 8000. The standalone remediation module can still run on 8001 for compatibility.

The unified application reads durable intake/work and legacy generated SQLite evidence; standalone compatibility services retain their separate workflow tables. They do not authenticate operators, certify provider truth, contact payers, or alter normalized provider evidence. Pydantic validates declared types/constraints; models do not enable strict mode or forbid extra fields. Append-only history describes application behavior, not database tamper protection.


## Intake and durable work

The saved native FHIR profile is implemented as described in [Native FHIR reference intake](#native-fhir-reference-intake). It has its own acceptance policy and does not use clinic recipe/dataset semantics.

All paths below use the same configured database/artifact root. There is no authentication; actor names are local assertions. JSON errors use `detail`; missing objects return 404, invalid inputs 422, and stale attempt/case versions 409. Multipart uploads are not used: send raw bytes with filename/source/designation/profile query parameters. Limit 10 MiB per artifact, 20,000 tabular rows; CSV/XLSX require explicitly mapped identity/address/phone fields. Validation/quarantine counts cover the full bounded artifact.

| Method | Path | Input / result |
| --- | --- | --- |
| GET | `/api/demo/samples` | Fixed synthetic sample catalog; empty items unless `PDTL_DEMO=1` (explicitly set by offline launcher). |
| POST | `/api/demo/samples/{sample_id}` | Allowed fixture only: `clinic-workbook`, `clinic-csv`, `clinic-changed`, `nppes`, `cms`. Normal retained intake receipt, always source `synthetic-demo`/designation `synthetic`. Disabled/unknown: 404. No file/URL parameter; no acceptance or verification. |
| GET | `/api/work-export.xlsx` | Read-only XLSX for all durable work, or exactly `?case_id=ID` (404 if absent). All-work ignores UI filters. Full linked evidence/events, related receipt attempts/repeats and payloads from one SQLite snapshot; no 50/200 UI cap. |
| POST | `/api/intakes/files` | Raw file body; query `filename`, `source=clinic`, `designation=synthetic|public|local`, `profile=flat|nppes|cms|fhir-plannet-r4`. Retains receipt and preview, including visible parse failures. |
| GET | `/api/intakes` | `{items:[receipt summaries]}` newest first. |
| GET | `/api/intakes/{id}` | Receipt, metadata, attempts, preview, observations and linked cases. Optional `attempt_id=ID` selects an exact retained interpretation belonging to this receipt. Explicit reads add `latest_attempt_id`/`is_current_attempt`; unknown, empty or cross-receipt attempts return 404. Without the parameter the latest-attempt response is unchanged. Samples cap at 50; counts remain complete. |
| POST | `/api/intakes/{id}/mapping` | `{mapping:{canonical:original_header},sheet,header_row,encoding,delimiter}`; new attempt, including after an earlier commitment. |
| POST | `/api/intakes/{id}/commit` | `{expected_attempt,policy:"valid_rows"|"reject",actor,reason}`. Atomic acceptance; duplicate delivery reuses prior interpretation; stale attempt conflicts. |
| GET | `/api/intakes/{id}/artifact` | Exact retained original bytes. Reference-only links have none. |
| GET | `/api/intakes/{id}/quarantine` | Full CSV with locator, problems and original row JSON. |
| GET | `/api/intakes/{id}/packet` | Full JSON receipt/attempt/original/observation/case/history packet. |
| POST | `/api/intakes/lookups` | `{source:"nppes"|"cms",query:{number,city,state,limit,skip,offset},refresh:false}`. Connector-specific supported fields only; fifteen-minute retained-response reuse unless refresh requested. Failed responses remain receipts and HTTP 422 errors. |
| POST | `/api/intakes/links` | `{url,title,source,observed_at}`; asserted, unfetched reference receipt. |
| GET | `/api/sources` | Source health, bounded scope, metadata, last success/failure. |
| GET | `/api/work` | `{items:[work summaries]}` risk/overdue/age/ID order. UI filters over summaries and renders first 200 matches. |
| GET | `/api/work/{id}` | Immutable initial evidence, current projection/version, later observations, history. |
| POST | `/api/work/{id}/events` | Expected-version accountable event; returns updated detail. |
| POST | `/api/relationships` | `{observation_id,provider_id,location_id,actor,reason,location_index?}`; exact observed `NPI:...`; multi-address native records require a selected practice location index. |

The workbook sample selects header row 2 and provides `metadata.suggested_mapping`; loading suggested columns only edits the form. Save mapping and explicitly accept after review. Repeated samples retain byte identity across restart and reuse a previously committed interpretation through normal intake rules. Ordinary uploads remain available with demo mode disabled.

The XLSX [data contract](DATA_DICTIONARY.md#durable-work-handoff-workbook) defines sheet grains, shared-receipt context, snapshot consistency, literal-text safety, nulls and complete chunked payloads. Download filename is `durable-work-handoff.xlsx`; no case mutation occurs.

Mapping supports `npi`, `provider_name`, `address`, `city`, `state`, `zip`, `phone` (required) and optional `record_id`, `location_id`, `listing_id`, `reference_phone`, `specialty`, `status`, `source_updated_at`. An unmapped source-native ID remains unresolved. String-safe CSV and simple zero-formatted XLSX identifiers retain leading zeroes; formulas quarantine the row.

Work actions: `assign` requires owner; `needs_information` records a reason and optional follow-up; `triage` starts/resumes review; correction-only `approve` requires ten-digit phone proposal, `submit` requires simulated submission reference, `verify` requires observed phone and verification note. A match verifies; mismatch reopens. `defer` records deferral; QA-only `resolve` records disposition. All actions require nonblank actor/reason and exact `expected_version`; follow-up is YYYY-MM-DD. Blank optional inputs should be omitted to preserve the current projection.

Example correction event (substitute an actual case and version):

```json
{"action":"approve","expected_version":1,"actor":"demo-reviewer","reason":"Reviewed the synthetic clinic request at NORTH","proposal":"6175550199"}
```

Original source evidence is not updated by these routes. Relationship events append a crosswalk; they do not merge entities. No external correction occurs.

## Compatibility boundary

The sections below describe earlier generated-batch QA and payer-precedence APIs. They retain their original request/response contracts and IDs. New intake evidence and expected-version work use `/api/work`; compatibility QA remains current-batch and standalone compatibility transitions do not gain the new version protocol.

## Review service

Default origin: `http://127.0.0.1:8000`. Source: `src/provider_directory_truth_layer/review_api.py`.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/health` | `{"status":"ok"}`; liveness only, not database readiness. |
| GET | `/api/batches/current` | `BatchSummary`. |
| GET | `/api/cases` | `CasePage`; all matching current-batch cases, no pagination. |
| GET | `/api/cases/{case_id}` | `CaseDetail`. |
| POST | `/api/cases/{case_id}/transitions` | `TransitionInput` -> `{case,event}`. |
| GET | `/api/exports/cases.csv` | Current filtered/sorted case-state CSV. |
| GET | `/api/exports/batch.csv` | One-row batch-summary CSV. |

List and case-export query parameters:

- `search`: case-insensitive substring in provider name, record ID, or issue code.
- `severity`, `issue_code`, `status`: exact filters. Unmatched strings yield no matching rows; these are not enum-validated query fields.
- `sort`: `priority` (default), `provider`, `issue_code`, `severity`, `status`, `owner`, `updated`.
- `direction`: `asc` (default), `desc`. Unsupported sort/direction returns 422.

There is no review `source`, `limit`, or `offset` filter. Current issue codes use lower snake case, for example `missing_required_field` and `possible_duplicate_provider_location`; see the [dictionary](DATA_DICTIONARY.md).

### Response shapes

`CasePage`: `items: CaseListItem[]`, `total: integer`.

`CaseListItem`: `case_id`, `record_id`, `provider_name`, `issue_code`, `severity`, `field_name`, `source`, `review_status`, nullable `assigned_to`, `updated_at`.

`BatchSummary`: `batch_id`, `source_label`, `record_count`, `exception_count`, `records_with_issues`, `issue_counts`, `severity_mix`, `source_summary`, `data_notice`, `limitations`. Batch IDs are `qa-` plus an evidence fingerprint; the current label is a static synthetic-sample label. Source-summary counts describe exception rows, not all provider records.

`CaseDetail` fields:

- `case`: `CaseListItem`.
- `exception`: `{values: {...}}`.
- `normalized_records`: array of `{values: {...}}`.
- `recommendation`, `explanation`, nullable `notes`.
- `history`: chronological `HistoryEvent[]`.
- `duplicate`: nullable `{candidate, records, warning}`, where candidate/records use the same values wrappers.

QA detail relies on source exceptions in the current generated batch. Preserved review events do not guarantee access to old source evidence after a changed pipeline output.

### Record a review action

Example body, sent to a case ID returned by the list endpoint:

```json
{
  "action": "assign",
  "assignee": "demo-reviewer",
  "reason": "Route to source confirmation",
  "note": "Confirm the clinic phone."
}
```

Declared inputs: required `action`, required `reason` length 3–500, optional `assignee` maximum 120, optional singular `note` maximum 2,000. There is no recorded actor or controlled reason code. QA checks truthiness for required assignee/note and does not consistently trim/reject whitespace.

| Action | Allowed current states | Next state |
| --- | --- | --- |
| `assign` | `new`, `assigned`, `in_review`, `deferred` | `assigned`; requires assignee. |
| `start_review` | `new`, `assigned`, `deferred`, `resolved` | `in_review`. |
| `resolve` | `in_review` | `resolved`. |
| `defer` | `new`, `assigned`, `in_review` | `deferred`. |
| `add_note` | All defined QA states | Same state; requires note. |

Response: `{case: CaseListItem, event: HistoryEvent}`. A history event has `event_id`, `event_type`, nullable `from_status`, nullable `to_status`, nullable `assigned_to`, `reason`, nullable `note`, and `occurred_at`.

Case CSV columns: `case_id,record_id,provider_name,issue_code,severity,status,assignee,updated_at`.

Batch CSV columns: `batch_id,source_label,record_count,exception_count,records_with_issues,data_notice,limitations`.

Neither CSV exports event history. `/api/export` is not an implemented endpoint.

## Remediation service

Default origin: `http://127.0.0.1:8001`. Source: `src/provider_directory_truth_layer/remediation_api.py`.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/remediation/health` | Liveness response; does not validate evidence storage. |
| GET | `/api/remediation/cases` | `{items: RemediationCaseItem[], total: integer}`. |
| GET | `/api/remediation/cases/{case_id}` | `{case,evidence,history}`. |
| GET | `/api/remediation/cases/{case_id}/history` | Chronological `RemediationEvent[]`. |
| POST | `/api/remediation/cases/{case_id}/transitions` | `{case,event}`. |

List filters: optional `status`, `risk_level`, `listing_id`, `field_name`. `limit` defaults to 100, range 1–100; `offset` defaults to 0, minimum 0. Results order by case ID; total counts matching cases before pagination. Unsupported nonblank status/risk returns 422. Listing/field filters are exact strings.

`RemediationCaseItem`: `case_id`, `listing_id`, `reference_provider_key`, `field_name`, `status`, `risk_level`, nullable `active_proposed_correction_value`, `updated_at`.

Detail contains `case: RemediationCaseItem`, `evidence: {values: {...}}`, and `history`. Evidence includes the initial discrepancy, selected source/record, comparison values, risk, and precedence. Legacy snapshots can identify unavailable original evidence with `snapshot_status=legacy_evidence_unavailable_when_snapshot_migrated`.

### Record a remediation action

Example approval body after triage:

```json
{
  "action": "approve",
  "actor": "demo-reviewer",
  "reason": "Synthetic clinic evidence supports this phone correction",
  "proposed_correction_value": "615-555-0101"
}
```

Required common fields: `action`, `actor` (1–120), `reason` (1–500). Actor/reason must remain nonblank after trimming. Optional action-specific fields are `proposed_correction_value` (maximum 2,000), `submission_reference` (500), `observed_payer_value` (2,000), and `verification_evidence_note` (2,000).

| Action | Allowed current states | Required extra fields / next state |
| --- | --- | --- |
| `triage` | `new`, `reopened`, `deferred` | `triaged`. |
| `approve` | `triaged` | Proposal -> `approved`. |
| `submit` | `approved` | Submission reference -> `pending_verification`. Records evidence; sends nothing externally. |
| `verify` | `pending_verification` | Observed value and verification note -> `verified` on normalized proposal match, otherwise `reopened`. |
| `defer` | `new`, `triaged`, `reopened` | `deferred`. |

`reopen` is the event produced by failed verification, not an accepted action. Verification compares with the active approved proposal, not automatically the original reference. Each case keeps its initial evidence even after later comparison outputs change.

`RemediationEvent`: `event_id`, `case_id`, `event_type`, `from_status`, `to_status`, `actor`, `reason`, `proposed_correction_value`, `original_payer_value`, `reference_value`, `submission_reference`, `submitted_at`, `observed_payer_value`, `verification_evidence_note`, `occurred_at`. Action-specific evidence fields can be null.

## Errors and verification limits

Explicit application errors use FastAPI's `{"detail":"..."}`; request-validation errors use a `detail` array. RFC 7807 conformance is not implemented.

- 422: invalid request values, required action evidence, or unsupported validated filters/sort.
- 409: disallowed state transition, invalid stored remediation snapshot, or missing active proposal for verification.
- 404: absent case or a QA case whose source exception is not in current output.
- 503: missing/incomplete prerequisite evidence where handled by the service.

Not every storage failure has a custom response. Health endpoints establish liveness only. Compatibility case transitions do not include expected-version concurrency control; durable `/api/work` does. See [2.0 execution gates](INTAKE_2_0_EXECUTION.md) for the original implementation contract and review (historical reference retained separately) for baseline evidence.

## Recurring file intake (schema v3)

`GET /api/intakes/{receipt_id}/saved-mappings` lists immutable reviewed revisions for that receipt's source/profile/declared scope. `POST` to the same path requires `name`, `actor`, `reason`, and `expected_attempt`; it saves the current ready mapped tabular preview, including parsing settings and selected required headers. It does not accept any rows. Each returned revision has an opaque `id`, source/profile/scope, settings, required headers and accountable creation fields. Revisions cannot be edited or deleted.

Apply with `POST /api/intakes/{receipt_id}/mapping` and `{"mapping_revision_id":"ID"}`. Settings cannot override a saved revision; review manual columns and save another revision instead. Reordered columns and extra unmapped headers are permitted. Missing selected headers yields `needs_mapping` with an explained error and blocks acceptance. The original always retains unknown columns. Source/profile/scope mismatches return 422.

Tabular previews now pin a single latest committed delivery for the same source/profile/declared scope. `preview.comparison.baseline` gives its attempt/receipt/label/acceptance time/mapping revision, or null. Comparison includes raw-row and unique-identity counts and new/changed/unchanged/unresolved/blocked-invalid/missing counts, plus entries with old/new fields and both row locators. Duplicate record/location keys quarantine every copy. Known-key invalid rows block a baseline key; unresolved rows cannot conceal absence. New/changed/unchanged describes valid unique rows only. Mapping reinterpretation is labeled separately.

The commit endpoint still requires `expected_attempt`, actor/reason and explicit valid-row/reject policy. Under the acceptance transaction it rechecks the pinned baseline; an intervening committed delivery returns 409 (`Accepted baseline changed...`). Refresh mapping/comparison and review before retrying. A duplicate delivery reuses the earlier accepted interpretation and does not advance the baseline. Later source evidence never changes human review status. Interactive rows/comparison entries are bounded to 50 with `entry_count`; downloaded evidence packets retain all entries/attempts. Native public JSON comparisons retain their earlier reference-evidence semantics.

## Organization/network intake (schema v4)

`GET /api/catalog` returns organizations, networks, locations and all reviewed source bindings, including which revision is current. `POST /api/catalog/organizations` requires label, kind (`payer`, `clinic`, `group`, `health_system`, `other`), actor/reason; optional identifiers are a list of issuing namespace/text value objects. Network creation (`POST /api/catalog/networks`) accepts label, optional payer organization ID, identifiers and actor/reason. Practice-location creation (`POST /api/catalog/locations`) accepts label, optional organization ID and actor/reason. IDs are opaque; equal labels create distinct records. Missing owners remain null; a network owner must be an explicitly selected payer. These operations neither import nor accept data.

`POST /api/catalog/bindings` requires source, kind (`network`, `organization`, `location`), exact source_key, existing target_id, actor/reason and expected_binding_id (null for a first binding). Replacing a binding appends a revision; stale expected IDs return 409. Earlier revisions and target references remain immutable. No provider/location/network identity is inferred from a display label.

Existing file upload optionally accepts `dataset_scope`, `completeness` (`unknown`, `bounded`, `full`) and `as_of` (YYYY-MM-DD). These remain receipt metadata; declared completeness and as-of dates never prove termination or effective dates.

For mapped network files, existing mapping POST additionally accepts roster_kind=`network`, typed `bindings` maps (`network`, `location`, `organization`, each exact source code → reviewed binding ID), and optional fixed_network_binding_id for an explicitly declared single-network scope. Mapping fields add network_code, organization_code, network_label, organization_label, participation_status, effective_date and end_date. The service stores a binding snapshot in the attempt specification/fingerprint. Saving a mapping revision retains this configuration; applying it remains revision-ID-only.

Every row needs a source-native participation key, provider NPI, explicit practice-location binding and network binding. A supplied organization code also requires a binding; absent organization stays unknown. Unbound identities, conflicting row/default networks, invalid dates and end-before-effective dates quarantine the row. Source-listed status is an assertion, separate from human review status. Contradictory fixed-network codes cannot hide a missing baseline record. Acceptance rechecks baseline and current binding revisions atomically; older bindings require renewed mapping review.

Comparison scope includes source/profile/declared dataset, roster kind and the explicitly configured local network set. Clinic and network deliveries, or different network sets, never share a baseline. Network identity includes native key, provider, practice location and network. Same bytes interpreted with changed reviewed bindings cannot silently reuse a different interpretation.

## Scoped network review and handoff

`GET /api/work` accepts exact optional network_id, organization_id and location_id filters. Items add network/organization/practice-location IDs and catalog labels; existing clinic items retain null network scope. `GET /api/work/{case_id}` adds the explicit scope and append-only participation_review evidence. These source comparisons are distinct from the human event history.

Accepted network deliveries retain missing/known-invalid comparison work as QA cases (`participation_missing` and `participation_validation`). Quarantined rows never become accepted participation observations. Unbound identities remain receipt quarantine without invented membership. Later evidence does not modify initial snapshots, owner, human status, version or events. Repeated interpretations do not duplicate this work. An explicitly full empty network snapshot with a prior accepted baseline can be accepted as absence evidence; an all-invalid nonempty file remains blocked. Absence never terminates participation.

`GET /api/work-export.xlsx` and `GET /api/work-export.json` export all durable work when unfiltered. Optional case_id or network_id selects one explicit scope; supplying both returns 422, unknown IDs return 404. The all-work download continues to ignore UI filters. JSON includes format_version=2 and an explicit scope/context notice. XLSX format 2 adds network columns and, when network work is included, Participations, Review evidence, Catalog and Bindings sheets. Operational rows and bindings/catalog references belong only to selected cases/network. Complete related receipt/attempt payloads are visibly labeled shared context and may contain other rows or interpretations; different declared datasets are not treated as repeats.

Both formats read one pinned read-only SQLite transaction without initializing/migrating a store or mutating artifacts/work. XLSX IDs, dates and formula-like values remain literal text; complete payloads use numbered JSON chunks. Effective/end/as-of dates, declared completeness, source status and human decisions retain their separate meanings. Full snapshots are independent of UI sample/render limits.

## Explicit synthetic network preparation

In demo mode only, `POST /api/demo/network-setup` explicitly prepares the versioned synthetic catalog and reviewed codebook. It returns notice/source/settings/catalog and creates no receipt, observation, work decision or payer update. Stable fixture IDs ensure idempotent preparation; reviewed replacement bindings produce 409 without overwriting them. Ordinary startup returns 404.

The sample picker adds network-baseline, network-changed and network-header-drift under source `synthetic-network-demo`, dataset `synthetic-network-roster-v1`. Loading retains the original through the normal receipt/attempt service. It never prepares the catalog, saves a mapping or accepts data. Network samples require explicit network scope review before acceptance; prepared codebook settings are suggestions that fill the form only. Header recovery requires a newly reviewed revision. Source field differences are displayed separately from generated binding metadata, which remains complete in old/new payloads and interpretation snapshots.

## Source profiling and normalization recipes

All routes below use retained receipt IDs. Invalid inputs return 422; unknown IDs return 404; stale expected attempts return 409. Recipe previews and row examples are bounded, explicitly mark truncated values, and retain full counts. Original/dataset downloads preserve complete evidence.

| Method and route | Input and result |
| --- | --- |
| GET `/api/intakes/{id}/profile` | `offset` and `limit` 1–100; complete row/column counts, bounded examples, editable alias suggestions and current attempt ID. |
| POST `/api/intakes/{id}/normalization/preview` | `definition`, `expected_attempt`, optional `offset`/`limit`; read-only transformation/validation preview with locators and provenance. |
| GET `/api/intakes/{id}/recipes` | Compatible immutable proposed/approved revisions for exact source/profile/dataset scope. |
| POST `/api/intakes/{id}/recipes` | `definition`, `name`, `actor`, `reason`, `expected_attempt`, optional `parent_id`; creates an immutable proposal. |
| POST `/api/intakes/{id}/recipes/{revision}/approve` | `actor`, `reason`, `expected_attempt`; current-receipt proposal becomes a separate approved revision. Repeated approval returns the existing approval. |
| POST `/api/intakes/{id}/recipes/{revision}/apply` | `expected_attempt`; creates a new interpretation from an approved compatible revision, preserving parsing choices. Does not accept data. |
| GET `/api/intakes/{id}/dataset` | Accepted current interpretation only; full records, transformation lineage, original artifact reference and quarantine. Repeated deliveries resolve reused accepted observations. |

Existing `POST /api/intakes/{id}/commit` remains the distinct acceptance boundary. Recipes cannot weaken application-required fields or duplicate-key quarantine. Native adapters/network bindings retain their existing behavior. See [the recipe contract and MCP setup](SOURCE_ONBOARDING.md).

## Retained comparison (schema 6)

`GET /api/intakes/{id}/comparison-profile` requires `expected_attempt`; optional `entity_kind` is unknown, clinician or organization. Returns complete quality counts and bounded evidence with original/comparison values and transformations. `offset`/`limit` page results.

`POST /api/reconciliation/runs` accepts 2–6 explicit `inputs` (`receipt_id`, `attempt_id`, optional `entity_kind`), `actor` and `reason`. It persists immutable inputs, baseline snapshots, rule version, records and typed candidates; it accepts no source observations and creates no links/work. Limits: 5,000 address references and 10,000 candidates; excess is rejected rather than truncated.

`GET /api/reconciliation/runs` lists history; `GET /api/reconciliation/runs/{id}` returns metadata/freshness. `/candidates` supports `kind`, `eligible`, `offset` and `limit`; `/export` returns complete pinned JSON evidence as an attachment. Rank is not a probability and eligibility does not establish identity. Changed selected interpretation or accepted scoped baseline makes a run visibly stale. Historical evidence remains readable. Reviewed links and field decisions are not yet available.

## Reviewed identity crosswalk (schema 7)

`GET /api/reconciliation/runs/{run_id}/candidates/{candidate_id}/review` returns candidate evidence, current typed links, latest pair decision, review snapshot, input freshness, `approval_allowed`/`approval_blockers`, target suggestions and paginated history (`offset`, `limit`, `history_total`, `history_next_offset`). Suggestions are capped at 100 per kind with `target_counts`. `GET /api/reconciliation/targets/{kind}` searches all clinician/location labels or an exact ID, using `search`, `offset`, `limit`; returns `items`, `total`, `next_offset`.

`POST /api/reconciliation/links` accepts `run_id`, `candidate_id`, `decision` (approve/reject/defer), unique `request_id`, `expected_snapshot`, exact `expected_revisions` object keyed by both candidate references (revision ID or null), `expected_decision` (prior pair decision ID or null), `actor` and `reason`. Approval additionally requires exactly one of existing `target_id` or explicit `new_label`. The identity and both link revisions are written atomically. Reject/defer must omit targets and do not remove previous links. Unknown fields/types are rejected. Identical full-content retries return the original `{decision,links}` even after later changes; a changed request with the same ID conflicts. Stale input/rule/link/pair snapshots return409. A later rejection of a selected attempt also invalidates review. Approval requires explicitly typed clinicians or practice addresses; unknown/incompatible types return422 without creating a target.

`GET /api/reconciliation/identities/{kind}/{id}` returns separately retained source assertions for current approved links, source freshness and prior link history. `offset`/`limit` page assertions and `history_offset` pages history; complete totals/next offsets are explicit. Record samples are bounded and labeled; original retained inputs remain accessible through their receipts. This is a reviewed crosswalk, not a preferred-value or verified-provider view. Approving it neither accepts quarantined observations nor changes existing network/case/source identities. MCP remains proposal-only; no identity approval tool is exposed.

## Field-level reconciliation (schema 8)

`GET /api/reconciliation/fields/{clinician_id}` returns clinician-scoped `provider_name`/`npi` assertions. Optional explicit `location_id` selects location-scoped `phone`/`address` instead. Location assertions require the intersection of current clinician links and address-specific links to that location. Each option retains source, exact reference, reviewed link IDs, network ID/label when known, original value, comparison value, findings and provenance. `offset`/`limit` page options/records, `history_offset` pages field history; full counts and next offsets remain explicit. Preview values are bounded and labeled. `scope_problems` explains conflicting run declarations; these block new preferences.

`POST /api/reconciliation/field-decisions` requires `clinician_id`, `field`, `decision` (`select` or `conflict`), `expected_snapshot`, `expected_decision` (prior ID or null), `request_id`, `actor`, `reason`; selection also requires `selected_ref`. Optional `location_id` selects location scope; omitted/null selects clinician-only scope. Conflict omits it or uses null. An existing reference must belong to this exact reviewed scope and pass field validation. Missing/null/blank values remain separately retained evidence; an explicit selection of absence records that preference without asserting a known phone/NPI. Arbitrary constructed values/component mixtures are not accepted. Phone and extension are one value; address components are one source block.

Evidence snapshots pin current source state/baselines, rules and relevant reviewed links. View snapshots additionally pin latest field-decision IDs for safe writes/downloads. Saving another field does not mark a previous preference stale; changed source/link/rule evidence does. Stale or conflicting views block writes, while identical full-content retries return their saved decision. All decisions append immutable history. Actor identities remain local assertions. Source values are selected as retained assertions; standardized comparison values remain visible separately and are not silently substituted.

`GET /api/reconciliation/identities/clinician/{id}/export?expected_snapshot=HASH&format=json|xlsx` accepts the same optional `location_id`. A changed snapshot returns409. Read-only exports include complete selected records/options, current and historical field decisions, approved link chains/creating decisions, and exact source-row context with provenance roles. Original multi-address rows may include other offices as explicitly labeled shared context; scoped records/options remain the authoritative selected scope. Historical stale decisions retain their evidence but provide no current preferred value.

XLSX has readable Field decisions/Source assertions sheets and a complete authoritative JSON Payload split into numbered text chunks. Reconstruct chunks in numeric part order. All populated cells are text; formulas are disabled, control characters are escaped for display, and large display cells explicitly point to the full Payload. JSON preserves types, nulls, empty strings, identifiers and full values. Exports create no work and do not verify or update providers. MCP exposes no field-decision mutation.

## Typed change proposals and read-only impact (schema9)

`POST /api/reconciliation/change-proposals` accepts `clinician_id`, optional/null `location_id`, `field`, `proposed_value`, explicit1–6 `inputs` (receipt/attempt IDs and optional source entity-kind declaration), `expected_snapshot` from the current R4 field view, `request_id`, `actor`, `reason`, optional distinct `network_ids` and optional `previous_id`. The field must already have a current selection/conflict decision. Name/NPI are clinician-scoped; phone/address require location scope. Phone target is `{number,extension}` with substantive ten-digit canonical number and optional digit extension; address is one `{line1,line2,suite,city,state,zip}` block using explicit state abbreviation/ZIP rules. Name/NPI are strings. Source originals and canonical proposed values remain separate.

Creation pins full retained evidence and baselines under an immediate transaction. Exact-content retries return the saved proposal even after later changes. Revisions retain clinician/location/field scope and cannot branch from an already superseded parent. `GET /api/reconciliation/change-proposals` supports exact clinician/location scope and offset/limit history; `GET /api/reconciliation/change-proposals/{id}` returns bounded prior-evidence summaries with complete counts and sampling flags. Large retained rows are not hydrated for list pages.

`POST /api/reconciliation/impact-preview` accepts only `proposal_id`, optional `offset`, `limit` (1..100) and independent `work_offset`. Returns stable `snapshot`, `inputs_fresh`, `stale_reasons`, listing `counts`, independent `work_counts`, paginated `targets`/`existing_work` and complete totals/next offsets. Clinician target refs use clinician-row grain; location targets use exact address refs. Source/network/observed/comparison/link evidence stays distinct. Optional network filters do not declare excluded/unknown networks unaffected; those remain not assessed. New accepted inputs, rejection, relevant source/rule/link/field/work changes and proposal revision affect freshness/snapshot.

Existing work matches exact accepted observation provenance; duplicate-delivery reuse chains resolve the original evidence attempt without merging the selected receipt identity. Targets expose `attempt_id` and `evidence_attempt_id`; work exposes the supporting evidence attempt IDs. Native-address work without an exact selector stays unassessed. Preview is read-only and creates no assessment, case, event or source row. It tracks only selected known dependencies, not external directories or prior downloaded copies. Explicit I2 confirmation is a separate operation below.

`GET /api/intakes` retains its legacy no-query complete `items` response. Providing `offset` or `limit` opts into bounded `items`, complete `total` and `next_offset`; missing page parameters default to0/20. This supports explicit assessment-source selection without changing older workbench clients.

## Confirmed follow-up and acknowledgement (schema10)

`POST /api/reconciliation/follow-up-preview` takes `proposal_id`, optional `case_choices` (`target_key: case_id` or `new`), `offset` and `limit`. Returns impact/plan snapshots, source freshness, action counts, blocked count, paginated actions and next offset. Planning is read-only. Only affected listings become targets; valid source-native identities group within exact typed/network/source-location scope, otherwise exact retained references apply. A single eligible open case is reused; ambiguous open matches require explicit choice. New work cannot bypass an eligible open case; closed cases are not reopened.

`POST /api/reconciliation/follow-up` requires `proposal_id`, `expected_snapshot` (impact), `expected_plan`, `case_choices`, `request_id`, `actor`, `reason`, `confirm:true`. One immediate transaction rechecks freshness/versions and freezes the full assessment/plan, then creates QA cases or associates existing work without rewriting its state/history. Stale/blocked/altered retry409; invalid input422. Exact request retry or identical confirmation intent with a new request ID returns the original immutable result. One confirmation per proposal; changed intent requires a revised proposal.

`GET /api/reconciliation/follow-up?proposal_id=&offset=&limit=` lists saved summaries. `GET /api/reconciliation/follow-up/{id}?offset=&limit=` returns current case summaries/versions, saved target actions, latest acknowledgement/count, source freshness and a current receipt snapshot. Frozen confirmation evidence remains distinct from later case/source state.

`POST /api/reconciliation/follow-up/{id}/acknowledge` requires `association_id`, `expected_ack_id` (explicit null for first), `expected_case_version` (integer), unique `request_id`, `actor` and `reason`. It appends an immutable acknowledgement with exact retry behavior; it changes no case status, owner, version or events. `GET .../{id}/acknowledgements?association_id=&offset=&limit=` pages history.

`GET .../{id}/export?expected_snapshot=HASH&format=json|xlsx` reads one pinned snapshot; changed source/case/acknowledgement returns409. It includes complete original/canonical proposal, frozen assessment/action plan, associations, current cases/evidence/events, all acknowledgements and full source context with explicit assessment/prior-field/historical-decision/initial-work roles. XLSX has Read me, Plan, Work history, Acknowledgements, Assessment and authoritative literal-text JSON Payload sheets. Export does not mutate storage.

Work/case responses add `follow_up_scopes` separately from source participation `scope`. Exact network/organization/location filters may match one complete follow-up association; attributes from different associations cannot be combined to create a false match. Selected-network/case exports include relevant follow-up intent/associations/history without inventing participation or projecting unrelated operational networks.


## Managed recurring feed (schema 11)

These local endpoints share the intake database. Inputs remain bounded to clinic CSV, 10 MiB and 20,000 rows. Reviewer/owner identities are local assertions. No worker, agent or discovery call approves data.

| Method/path | Behavior |
| --- | --- |
| GET `/api/feeds` | Registry and retained feed state; GET `/api/feeds/{id}` selects one. |
| GET `/api/feeds/recipes` | Approved clinic recipes, including exact decoded source scope. |
| POST `/api/feeds` | Register disabled feed: `name`, `source`, nonempty string/object `scope`, existing absolute `inbox`, `owner`, optional `start_date`, `actor`, `reason`. |
| POST `/api/feeds/{id}/contracts` | Propose `definition` with approved `recipe_revision_id`, `required_headers`, optional encoding/delimiter/row_change_fraction, plus actor/reason. Headers cover the recipe and native record/location keys. |
| POST `/api/feeds/{id}/contracts/{contract_id}/approve` | Actor/reason creates a separate immutable approved contract ID. |
| POST `/api/feeds/{id}/configure` | `expected_revision`, `config` changes (enabled, contract_id, owner, inbox, start_date), actor/reason; immutable configuration history. |
| POST `/api/feeds/{id}/tick` | Explicitly discover and process at most one job. Returns feed detail; a running worker owns the same execution lane. No acceptance. |
| GET `/api/feed-versions/{id}` | Candidate/decision, full quality counts, report hash, current-approved ID, manifest, bounded row/comparison samples and exception history. |
| POST `/api/feed-versions/{id}/exceptions` | `expected_report`, finding `code`, `disposition` acknowledged/deferred, actor/reason. Soft holds only; decided versions reject later review. |
| POST `/api/feed-versions/{id}/decide` | `expected_report`, explicit nullable `expected_current`, approved/rejected `decision`, unique `idempotency_key`, actor/reason. Exact replay returns the same decision; changed intent conflicts. |
| GET `/api/feeds/{id}/current` | Approved `version_id`, stale flag and notice; 404 before first approval. |
| GET `/api/feed-versions/{id}/export` | Complete approved version JSON attachment. Candidates/rejections return 422. |
| POST `/api/feed-jobs/{id}/retry` | Attributed retry of failed/cancelled job with its pinned inputs. |
| POST `/api/feed-jobs/{id}/cancel` | Attributed cancellation fences later publication; retains evidence. |
| POST `/api/feed-jobs/{id}/reprocess` | Attributed new job against current approved contract/config/baseline after prior execution stops. Existing equivalent pinned job conflicts. |

All attributed actions require nonblank actor/reason. Stale expected versions, conflicting decision replay and obsolete processing inputs return 409. Invalid configuration/quality holds return 422; missing IDs return 404. A processing hold is a successful job with an unapproved candidate. Job failures/errors remain visible. Disable stops new discovery without silently cancelling retained jobs.

Approved export content is immutable across later promotions/restarts. The quality baseline is the previous approved feed version, not an unrelated latest intake acceptance. Dataset approval transaction rechecks the report, current pointer, config/contract, hard blockers/soft dispositions, conflicting source delivery IDs, source ordering and retained artifact hash. No manual receipt commit or remapping can bypass it.


## Connected operator navigation

The web entry without a valid explicit `view` opens Managed feeds. Explicit legacy views remain supported. Query parameters identify `feed`, `version`, `receipt`, `attempt`, `run`, `clinician`, `location`, `proposal`, and `followup`; work uses `case`. They are selections, not authorization or saved decisions.

Feed/version pairs are validated against the selected feed's retained versions. Preparing reconciliation validates approved state and exact feed/receipt/attempt identity through existing read endpoints. Unknown or incompatible references show a recoverable error without choosing a different version. Clinician/location scope is checked against selected proposals, and saved follow-up receipts must belong to the selected proposal. Existing mutation APIs retain all actor/reason, expected-snapshot, stale-input and idempotency requirements.

Pinned receipt views use `attempt_id` and are read-only, even when that interpretation is still current. The original download retains the receipt's bytes; complete attempt history stays available. A newer interpretation is explicitly flagged rather than substituted. URLs carry selection identifiers and filter criteria; records and decisions remain in SQLite. No new table, schema migration or automatic workflow transition is introduced.

## Evidence-reason candidate triage

`GET /api/reconciliation/runs/{id}/candidates` accepts optional `reason` alongside existing `kind`, `eligible`, `offset` and `limit`. The reason is a bound lowercase ASCII identifier (`[a-z][a-z0-9_]{0,79}`); malformed values return 422. A well-formed unknown code returns zero pairs. It matches any recorded agreement, contradiction or missing-evidence code. One candidate appears once even if the code is repeated.

The additive `reason_counts` map counts distinct pairs for every reason across the complete selected kind/eligibility subset, before the selected reason and pagination. `unfiltered_total` is that subset's pair count. Existing `total`, `items` and `next_offset` describe the reason-filtered set and its current page. Counts can overlap across codes and are not additive. Stored candidate IDs/order/eligibility and complete exports are unchanged; no mutation or new schema is involved.

Web bookmarks carry `candidate_kind`, `eligibility` and `evidence_reason` alongside `run`. Changing type/eligibility clears the selected reason and resets paging. Work-case return links preserve these selections. The filter does not resolve contradictions or authorize identity decisions.


## Search and filtered candidate handoff

Saved-run candidate reads accept optional `search` (1–100 characters after trimming, with at least one non-whitespace character). A case-insensitive literal substring is compared against the normalized provider name, NPI and source-native ID on either retained record. Search is applied across the complete run before paging. `reason_counts` and `unfiltered_total` cover the selected kind, eligibility and search before the reason filter. A nonmatching search produces an empty result; missing candidates are not evidence of non-identity.

`GET /api/reconciliation/runs/{id}/candidates/export` accepts the same `kind`, `eligible`, `reason` and `search` filters and downloads all matching candidate pairs with complete retained comparison records, the run metadata, selected scope and total. It is not page-limited. Clinician pairs include retained address records for their clinician references; location pairs include the selected location references. Identity decision history is separate. The existing `/export` route still downloads the complete run. Both reads preserve state and can return historical stale-run evidence, whose freshness is reported in run metadata.

Search is submitted explicitly in the interface and is not placed in workspace bookmarks. The term is sent as a local request parameter and recorded in the filtered export's scope; local server or browser download history may retain it. The downloaded evidence may contain the selected source data and should be handled accordingly.

## Structured outreach and investigation handoff

The existing POST /api/work/{case_id}/events also accepts action outreach. Required: actor, reason, expected_version, contact_at (ISO timestamp with timezone), method (phone/email/portal/other), outcome (no_answer/message_left/response_received/unable_to_contact). Optional contact_target, respondent_role, response_summary, reported_phone. A response_received outcome requires response_summary. reported_phone is permitted only for response_received and must normalize to ten digits. Outreach rejects owner, follow_up and correction fields; use a separate assignment/scheduling or correction action. A stale version returns 409; invalid data returns 422. Recording appends history and increments version atomically without changing case status or correction values.

Work-export JSON retains format_version 2 and adds investigations, one summary per scoped case. XLSX adds Investigation and Outreach sheets. Existing decision history and complete scoped evidence remain. Contact timestamps and reported phones are local assertions; no communication or external update occurs.

## Native FHIR reference intake

Implemented headlessly in D1.2, 2026-11-14. `POST /api/intakes/files?filename=directory.json&source=synthetic-fhir&profile=fhir-plannet-r4` receives raw saved searchset bytes under the existing 10 MiB artifact limit. Parser limit is 1,000 entries; no URL is fetched and no endpoint provenance is inferred. `completeness=full` is rejected. Failed interpretation retains original bytes and a failed attempt.

Detail uses the existing receipt, attempt and observation envelope. Native previews add `native` with parser/version, resources, references, assertions, findings, coverage and validation states. Interactive native arrays cap at 50, include exact `*_count` fields and explicit sample truncation; source text samples are bounded. `/artifact` returns exact bytes; `/packet` returns full retained attempts/native data and observations. Empty searchsets are successful empty previews, eligible for rejection but not resource acceptance.

Explicit acceptance uses the existing commit endpoint with native policy:

```json
{"expected_attempt":"ATTEMPT_ID","policy":"reference_resources","actor":"Synthetic analyst","reason":"Reviewed bounded reference resources","request_id":"native-review-1"}
```

All four text fields are required, nonblank strings of at most 2,000 characters. Unknown fields and clinic `valid_rows` policy are rejected (422). `reject` is also supported. Current-attempt checking, observations and terminal decision commit in one transaction. Request IDs are receipt-scoped: identical retries recover the original attempt result, even after reprocessing; changed content under that request ID, a new request against an already decided attempt or a fresh stale-attempt request returns 409. Repeat deliveries preserve separate receipts/decisions and reuse eligible original observations by source/profile/scope/artifact/parser fingerprint.

Resource observations have nullable provider/location projections. Acceptance creates no clinic cases, reviewed identity, network binding or dataset promotion. Profile/terminology statuses remain `not_run`; accepted reference evidence is not certified conformance. Clinic mappings and recipes are unsupported for this profile. `/dataset` rejects native resources with guidance to use `/packet` so reference evidence is not labeled a validated clinic dataset.

Existing comparison-profile/run APIs consume conservative native role/location assertions and retain `supporting_refs` with exact attempt/resource/field paths. Field options, decisions, impact targets and follow-up retain these references. Reconciled JSON/XLSX exports include every contributing retained resource row for selected scope; complete receipt/Bundle data remains shared context. The native GUI is implemented and headlessly verified in D1.3; full terminology coverage and human usefulness remain separate gates.

## Durable FHIR acquisition (schema 12)

Implemented in D2.1 with Sources-workspace controls. Source key `hap` selects the fixed public HAP origin; payloads cannot supply arbitrary URLs, hosts, headers or credentials. Location and PractitionerRole searches accept count 1–20. Source-advertised and parser-target Plan-Net versions are retained separately and are not a conformance assertion.

| Method/path | Contract |
|---|---|
| GET `/api/fhir-acquisitions` | Configured source key/base, advertised/parser versions, limits/spacing and `source.next_request_at` (future source-wide cooldown or null), plus latest 100 operation summaries with ID/revision/state/next retry/result receipt. |
| POST `/api/fhir-acquisitions` | `request_id`, `actor`, `reason`, optional `source=hap`, `resource_type=Location|PractitionerRole`, `count=1..20`, optional `resource_id` (1–64 letters/digits/hyphens/periods, not a URL). The filter becomes one `_id` parameter. Creates queued operation; performs no network request or acceptance. Same exact request ID/intent recovers the existing operation; changed intent returns 409. |
| GET `/api/fhir-acquisitions/{id}` | Configuration, revision/state, durable checkpoint, partial flag and append-only events. Event bodies are referenced by artifact hash, not embedded. |
| POST `/api/fhir-acquisitions/{id}/run-once` | No payload required. Performs at most one network response or atomic final publication. Future operation or source-wide cooldown returns without fetching; a new waiting intent records `source_wait` without consuming request budget. Cancellation, completion and terminal retry failure do not clear the configured source's wait. Local final publication needs no source request and is exempt. A busy shared worker returns current operation data with `busy=true`. Terminal operations remain unchanged. |
| POST `/api/fhir-acquisitions/{id}/cancel` | `expected_revision` (integer), actor and reason. Revision-checked cancellation; concurrent in-flight responses are retained as discarded evidence but cannot advance the operation. Terminal/stale cancellation returns 409. |
| GET `/api/fhir-acquisitions/{id}/events/{seq}/artifact` | Exact capped retained response/error body belonging to that event and acquisition. Unknown/bodyless event returns 404. Truncation and byte count are in event metadata. |

Example creation:

```json
{"request_id":"directory-sample-1","actor":"Local analyst","reason":"Review a bounded provider-directory sample","source":"hap","resource_type":"PractitionerRole","count":1}
```

States: queued, running, retry_wait, failed, cancelled, complete. Request stages and checkpoints survive process death; explicit later worker calls resume under one shared local OS lock. No scheduler, background daemon or autonomous retry loop is installed. Partial/failed/cancelled acquisitions have no ready intake receipt. Complete capture atomically creates an explicitly derived searchset receipt and preview, still requiring separate `reference_resources` acceptance. An empty completed capture is not an accepted dataset.

The source contract owns page/reference/request/byte/time/retry limits, the fixed HAP alias-to-published-origin routing rule and bounded `_pretty=true|false` formatting. No alternate host is fetched. Routed requests retain `source_url`; actual HTTP URLs remain in request and resource-origin provenance. Filtered receipts add `metadata.query={resource_type,count,resource_id}` and include the ID in their scope digest. Old unfiltered scope hashes and metadata remain unchanged. Relative references use their declared REST base; direct routed references retain advertised identity in the derived `fullUrl`.

Original response artifacts remain distinct from the derived artifact; `receipt.metadata.resource_origins` and comparison `supporting_refs.source_pages` connect assembled resource/field paths to exact response hashes, URLs, original locators and retrieval times. Finishing selected query pages never establishes full-directory completeness.

## Optional model mapping runs (schema 13)

Implemented in `mapping_assistant.py`, `mapping_model.py` and the optional normalization panel. Actual model quality/access remains separately unverified. One experimental configured OpenAI Responses client creates only recipe proposals; manual and deterministic operation remain available. The [source-onboarding contract](SOURCE_ONBOARDING.md#d30-selected-model-invocation-contract) owns permission, sample, model/rate assumptions and budgets.

| Method/path | Behavior |
|---|---|
| GET `/api/intakes/{receipt}/assistant-runs` | Current public configuration/availability, source-processing permission, reserved local allowance and latest 100 run summaries. No invocation. |
| POST `/api/intakes/{receipt}/assistant-runs` | Exact fields: request_id, expected_attempt, actor, reason, external_processing=true. Pins the bounded sample and queues, or records unavailable if disabled/unconfigured. Same ID/intent recovers the run; changed content returns 409. Unknown endpoint/model/header fields are rejected. |
| GET `/api/intakes/{receipt}/assistant-runs/{id}` | Retained configuration/context, request/response hashes, state/revision, reservation, result/proposal pointer and append-only history. Receipt ownership is checked. |
| POST `/api/intakes/{receipt}/assistant-runs/{id}/run-once` | One explicit invocation or local retained-response publication, with no automatic retry. Busy lock returns busy=true/current data. Interrupted running becomes failed/unknown-outcome, preserving its reservation; response_ready resumes without another call. Terminal runs are unchanged. |
| POST `/api/intakes/{receipt}/assistant-runs/{id}/cancel` | expected_revision, actor and reason. Cancels queued/running/response_ready intent; concurrent late response remains discarded evidence and cannot publish a proposal. Stale/terminal returns 409. |
| GET `/api/intakes/{receipt}/assistant-runs/{id}/artifacts/{request\|response}` | Exact retained body download with digest verification. Missing or out-of-scope artifacts return 404. Authentication-error bodies are deliberately not retained. |

States: queued, running, response_ready, succeeded, failed, cancelled, unavailable. Succeeded means a validated proposed recipe was saved, never approval, application or accepted data. The existing recipe list includes `assistant_run` attribution; evidence packets include all receipt-scoped run packets when present. Accepted observations and validated datasets carry model/prompt/schema, run/proposal IDs, input/sample references, request/response hashes, reported usage and conservative cost estimate through `normalization.assistant`. Non-model dataset shape remains unchanged.

`provider-truth-layer evaluate-mapping --root NEW_DIRECTORY` runs the frozen alias-only baseline without model requests. Add `--invoke-model` to explicitly request one configured call per synthetic held-out case; disabled/missing configuration records unavailable, not a simulated result. The new owned root retains its database, artifacts and evaluation.json and refuses overwrite. Actual outcomes, semantic disagreements and validation failures remain separate from controlled-provider engineering tests.

## Approved contact consumer and operations rehearsal

D4 adds CLI consumers of existing service/export contracts; it adds no HTTP endpoint or schema migration.

`provider-truth-layer consume-approved EXPORT --expected-version ID [--expected-feed ID] [--sha256 HEX] [--report NEW_FILE]` reads at most 10 MiB from a supplied managed-feed schema-1 JSON export. It requires an approved matching version, consistent report/record digests and counts, no hard blocker, acknowledged holds, distinct native contact keys and canonical contact values. It opens no application storage and performs no network request. Success writes consumer schema 1 with pinned version/feed/input digests, approval context and sorted contacts to stdout or a new report file. Invalid input, missing files, wrong pins or existing reports exit 2. Approval and hashes do not establish authenticity or freshness. [The reader contract](OPERATIONS_DEMO.md#small-approved-data-consumer) specifies representation and bounds.

`provider-truth-layer rehearse-operations --root NEW_DIRECTORY` prepares and checks one synthetic mixed-source journey using actual shared services and an owned loopback HTTP source. Its parent must exist; an existing path or symlink is refused. Success retains storage, inputs, exports, stopped backup/restore and `operations-rehearsal.json`; a failed invariant exits 2 and preserves the partial root. It deliberately disables model calls. [Run instructions](OPERATIONS_DEMO.md#run-and-inspect) identify the report and scopes. This rehearsal is automated engineering evidence, not an observed human task.

## Filtered search response checks (R1)

Newly completed native-ID-filtered acquisitions add immutable `receipt.metadata.query_validation` and the same publication-event payload: `version=1`, requested `resource_type`/`resource_id`, `matched_entries`, `implicit_match_entries`, `included_entries`, `outcome_entries`, `scope=captured_search_pages`. Counts describe raw retained page entries rather than deduplicated resources or server totals. Missing mode is counted as an implicit match only when its type/ID satisfies the request. Explicit includes remain distinct context. Warning/information outcomes remain retained; source error/fatal or malformed outcomes fail.

Each page is checked before advancement and retained pages are rechecked before local publication, including queued checkpoints from the preceding implementation. Include-only results cannot publish without a matching entry across the complete captured page set. Empty results can complete but create no accepted reference observations or termination claim. A scope failure returns a normal failed acquisition envelope, preserves HTTP status/body/hash/history, and has `receipt_id=null`; no intake review or promotion occurs. Existing completed receipts and unfiltered metadata stay unchanged. Native review states when an older filtered receipt lacks the report. See [the frozen policy](PUBLIC_DATA_SOURCES.md#filtered-response-integrity-r1) for the conservative rule and its standards boundary.

## Native interpretation revision R2

Native parser `fhir-plannet-r4-v2` recognizes the bare Plan-Net Network canonical and exact `|1.2.0` version-qualified form; other explicit suffixes remain unresolved. `meta.versionId` is a separate resource version. A role with more than one Network-reference extension retains its resources/references and receives `unresolved_network_scope` explaining the count/maximum; it has no office assertion. Other eligible roles remain independently available. Existing attempt envelopes/acceptance endpoints are unchanged. Reprocessing is explicit and append-only; no startup migration rewrites old v1 evidence. [Qualification](evidence/canonical/provider-graph-2026-11-14/README.md) covers selected export/restart and actual-source limits.

## Retained FHIR JSON consistency (R4)

Acquisition applies the same strict bounded UTF-8 decoder to search and standalone-reference bodies, before requested identity checks or assembly. Duplicate properties, nonfinite numbers, excessive depth/nodes or bytes fail visibly with the exact original response retained. Publication also re-decodes digest-verified retained bodies, including queued pre-fix references; old completed receipts remain unchanged. UTF-8 BOM remains accepted. No response/acceptance schema or native parser-v2 projection changes. See [the source contract](PUBLIC_DATA_SOURCES.md#strict-retained-json-consistency-r4).
