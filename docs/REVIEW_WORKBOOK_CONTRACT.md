# Approved directory review workbook contract

Implemented review-export format 1, selected under the owner's session authorization to implement the integrated release. This adds a review deliverable over the existing explicitly approved managed-feed dataset. It does not change acceptance, dataset approval, field-decision propagation, source evidence, or storage schema.

## HTTP and selection

`GET /api/feed-versions/{version_id}/review-export` returns JSON. Optional `location_id` selects the exact source-native office ID in that version; absent selects every row of that version. The version must have an explicit approved dataset decision. Candidate/rejected versions return 422, missing versions/offices return 404. There is no implicit current-version lookup, UI search filter, or 50-row preview cap.

JSON contains `format_version`, `version_id`, `scope`, `snapshot_id`, `snapshot_at`, `counts`, `directory`, `unresolved_issues`, `sources`, `manifest`, `approval`, `report_hash`, and `scope_notice`. `scope` contains `feed_id`, nullable `location_id`, and `kind` (`approved_feed` or `approved_feed_office`). Counts are actual array populations: `directory`, `unresolved_issues`, `sources`, plus selected `quarantined_rows` and the distinct `excluded_cross_scope_cases` count. The latter counts linked cases omitted because their initial evidence belongs to a different dataset scope; it is not included in `unresolved_issues`. This JSON is both an inspectable preview and a machine-readable companion to the workbook; existing approved-dataset and durable-work JSON exports remain available.

Download with the same selection and `format=xlsx&expected_snapshot={snapshot_id}`. Missing preview token returns 422. A changed selected snapshot returns 409 and requires refreshing the preview. Unknown format returns 422. The response is an XLSX attachment named `reviewed-directory-{version_id}.xlsx`. JSON may also take `expected_snapshot` to validate an existing preview.

All reads occur inside one read-only SQLite transaction pinned by the first SELECT. Rendering starts after data has been materialized and the read transaction released. The token hashes the actual exported material, scope, manifest, approval, and report hash; it excludes the descriptive generation timestamp. An unrelated feed/case update does not invalidate it. Immutable Directory values remain pinned to the requested version; unresolved operator work is current as of the export's database snapshot. A later pending delivery does not replace or enter this Directory. No workflow writes or storage initialization occur during export.

## Worksheet columns and grain

All columns are nullable literal text in Excel; numeric counts/version fields remain numbers in JSON. Dates retain their persisted ISO 8601 representation; `snapshot_at` is UTC with an explicit offset. Source `as_of` is an ISO calendar date, distinct from retrieval and human verification. Blank cells represent null/absent values, while two double quotes represent a present empty string. JSON preserves that distinction and exact control characters. Workbook scalar display escapes XML control characters. Every populated cell is explicitly a string, including formula-like `=`, `+`, `-`, and `@` prefixes and leading-zero identifiers/ZIP codes. There are no formulas, hyperlinks, or external workbook links. A display cell exceeding Excel's 32,767 UTF-16-unit capacity fails explicitly rather than silently truncating; JSON remains available.

### Directory

One row per valid native record/office pair in the selected approved source snapshot, ordered lexically by retained row locator. Quarantined rows are excluded. The exact ordered columns are:

`directory_row_id`, `source_record_key`, `office_key`, `version_id`, `record_id`, `npi`, `provider_name`, `location_id`, `address`, `address_line2`, `suite`, `city`, `state`, `zip`, `phone`, `specialty`, `status`, `source_updated_at`, `source_ref`.

`directory_row_id` hashes feed ID plus native record and office, so the same native pair retains its identifier across feed versions. `source_record_key` hashes feed ID plus native record ID; `office_key` hashes feed ID plus native office ID. These are feed-scoped cross-sheet join keys, not reviewed canonical identity links. A native record ID can identify a provider-office row rather than a clinician; this contract therefore does not infer or emit a clinician identity key. One NPI across two office records may have distinct source record keys. Separate organization/dataset feeds do not share office keys merely because their source and office labels match. NPI alone does not establish an office or participation. Unsupported fields remain blank. Pending proposals, locally recorded responses and observed values do not replace approved source values.

### Unresolved issues

One row per open work case linked by retained `work_evidence` to an observation in the selected version **and whose initial evidence receipt has the same dataset scope**, per selected quarantined row, and per selected version's hard/hold quality finding. Cases with `resolved` or `verified` status are excluded. `new`, triaged, approved, deferred, pending-verification and reopened cases remain unresolved. Existing generic accepted-observation review cases are included, rather than silently treated as verified. An acknowledged quality hold remains visible because acknowledgement permits approval without asserting that its underlying coverage issue was fixed. Warnings are not unresolved issues. Ordering is lexical `issue_id`.

Exact ordered columns:

`issue_id`, `directory_row_id`, `source_record_key`, `office_key`, `version_id`, `kind`, `status`, `field`, `issue`, `listed_value`, `proposed_value`, `observed_value`, `case_version`, `source_ref`.

Case `issue_id` is the durable work-case ID; quarantine and quality IDs hash version and locator/code. Quarantines have blank `directory_row_id` because they are excluded from Directory; their feed-scoped source record/office keys are retained when known. Dataset quality findings have blank row/identity/source keys because they concern the entire version, including when an office subset is selected. Such rows do not assert an office-specific defect. Case values are initial listed assertion, current local proposal, and locally asserted observed value; these remain separate. Their `source_ref` resolves the case's initial evidence rather than misattributing it to a later delivery.

Scope equality uses parsed receipt metadata serialized with the shared canonical JSON serializer; dictionary key order does not create a different scope.

Historical limitation: durable-work keys created before the dataset-scope correction used source/native provider/office/record identity without dataset scope. Separate organization feeds could therefore link observations to the same older case. New work keys include non-null dataset scope, and legacy keys are reused only when their initial evidence scope matches canonically. Null scope retains the legacy key shape unless a differently scoped historical case already occupies it; that collision uses an explicit null-scope key instead. This export excludes that case from a different initial-evidence scope, reports the distinct omitted-case count, and includes `scope_notice` in JSON and workbook metadata. A nonzero count means the unresolved list is incomplete for that feed because inherited cases cannot be safely attributed. Original cases and evidence are preserved; no migration or retroactive identity rewrite occurs.

The scope deliberately excludes unrelated cases, records absent from the selected approved version, later unapproved deliveries and their findings. This is not a feed-wide backlog export. Absence from a later delivery is not interpreted as office closure. Full source/attempt evidence remains in the existing evidence exports.

### Sources and export details

Exact ordered columns:

`entry_type`, `detail_key`, `detail_value`, `source_ref`, `version_id`, `source`, `designation`, `receipt_id`, `attempt_id`, `artifact_sha256`, `row_locator`, `recipe_revision_id`, `contract_id`, `source_as_of`, `received_at`.

`entry_type=detail` rows describe version, snapshot, scope, counts, approval, manifest, report hash and limitations. `entry_type=source` rows resolve each selected Directory/quarantine row and any additional initial case evidence. References hash version, receipt and locator; every populated Directory/issue `source_ref` has exactly one source row. An identical repeated delivery retains its own selected receipt reference while open cases can reference the earlier canonical receipt/observation. Missing recipe/contract values on extra historical case references are unknown, not inferred from the selected delivery.

Resolve original bytes through `GET /api/intakes/{receipt_id}/artifact`, validate the retained SHA256, then locate the native row identified by `row_locator`. Receipt details and the approved dataset's manifest retain interpretation/recipe provenance. Local approval and synthetic/public/local designations do not certify current contact details, externally verified participation, or a payer update.

## Requirement-to-check map

`tests/test_review_workbook.py` independently loads the produced XLSX and inspects actual cells and worksheet populations:

- AI-08: approved-only output, selected NORTH scope, pinned phone while a pending proposal differs, stable Directory/issue/source references, later pending delivery exclusion, exact preview/download counts, no export writes.
- AI-08: candidate/missing selections rejected, stale preview conflict, actual ZIP/leading-zero strings, formula-like values, XML controls, explicit overflow failure and no workbook links.
- AI-08 / AI-04: canonical observation reuse for identical repeated deliveries, original case evidence references, stable native record/office row identifiers across versions, two office records for one NPI without inferred clinician identity, and separate feed/org namespaces for identical native office labels, and exclusion of another organization's historical case proposal with an explicit omitted-case count/notice. `tests/test_work_scope.py` separately checks new scope isolation and matching legacy-case reuse without history rewrites.
- AI-08: quarantined rows excluded from Directory but present as unresolved with retained source; acknowledged hold remains explicit; 65 actual rows exported beyond the existing preview limit.
- AI-08: concurrent WAL writer between first read and work-case reads proves one consistent database snapshot rather than a mixture of old and new work state.

Remaining scope: adaptive one-off imports do not acquire dataset approval through this endpoint; managed-feed approval is the existing consumable boundary. Field-reconciliation decisions are not automatically promoted into a candidate dataset. Recipient-specific upload templates and FHIR export are deferred. AI-09 requires separate populated UI/browser evidence and owner review.
