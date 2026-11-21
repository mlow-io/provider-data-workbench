# Operations Workflow

This document explains the bounded healthcare data-cleanup workflow.

The durable 2.0 operator journey is documented in the [five-minute procedure](operations_governance/sop_provider_remediation.md): receive CSV/XLSX/JSON or a bounded public response, map and quarantine, explicitly accept, review scoped identities, then approve/submit/verify corrections with retained evidence. The sections below document the preserved legacy CSV/current-batch pipeline and its payer-precedence comparison boundary. See the [API](API_REFERENCE.md) and [data dictionary](DATA_DICTIONARY.md) for the distinct durable intake contract.

## Scenario

A small healthcare operations firm receives provider directory exports from several sources:

- an NPPES-like public export,
- a payer directory,
- a clinic directory,
- a health-system roster.

The client wants to know which records are trustworthy enough for downstream reporting and which records need human review.

## Input

The input is a CSV with fields such as:

- record ID,
- NPI,
- provider name,
- specialty,
- address,
- city,
- state,
- ZIP,
- phone,
- accepting-new-patients status,
- source,
- active/inactive status,
- last verified date.

## Normalize

The pipeline standardizes:

- column names,
- phone digits,
- provider names,
- addresses,
- city names,
- state values,
- ZIP codes,
- dates.

Normalization does not mean the record is correct. It only means the fields are shaped consistently enough to compare and validate.

## Validate

The rules in `config/qa_rules.yml` check:

- missing required fields,
- invalid or missing phone number,
- inactive or unknown status,
- missing verification date,
- stale verification date,
- invalid accepting-new-patients value.

Each failed rule becomes an exception row.

## Detect Duplicate Candidates

Duplicate candidates are grouped by normalized provider name, normalized address, normalized city, and state. This is intentionally conservative. It is good enough to identify suspicious duplicates, but final merge decisions should be made by a reviewer.

## Verify Synthetic Payer Listings (Phase 1)

The loop runs only when a payer-listing CSV is explicitly supplied. `make demo` supplies the committed, clearly labeled synthetic payer-directory listing file; custom and public-NPI runs remain QA-only unless the caller supplies a payer file. It does not alter the source export or normalized provider records.

For each payer listing field, the pipeline:

1. uses the payer listing's explicit `reference_provider_key` crosswalk to locate source evidence, independently of the payer-published NPI;
2. records one high-risk listing-identity finding if that key is unmatched, without emitting field comparisons for that listing;
3. selects the first nonblank field value using configured, field-specific source precedence for matched listings;
4. compares normalized payer and reference values so harmless phone or address formatting differences do not become discrepancies; and
5. labels a mismatch or missing payer value as high, medium, or low risk while preserving individual `reference_unavailable` fields as evidence only.

The precedence has deliberately different semantics by field. NPPES-like data is preferred for NPI and provider legal identity. Clinic and health-system sources are preferred for operating location, phone, availability, status, and specialty because they are closer to active operations; payer data is a lower-priority fallback. Verification date remains a QA freshness control and is not compared in this Phase 1 loop because source-specific verification semantics have not yet been defined.

The result is a deterministic verification queue. It does not correct a field, publish a listing, or change a source, normalized, or payer record.

## Remediate Matched Field Discrepancies (Phase 2)

The local remediation API creates one workflow case for each row in `payer_directory_discrepancies`; unmatched listing identities remain a separate identity finding and do not become correction cases. The deterministic case identifier is derived only from the stable listing ID, reference-provider key, and field name. Synchronization inserts newly detected cases but never removes workflow state, appends duplicate cases, or changes event history.

`remediation_case` is the current-state projection and `remediation_event` is the append-only audit record. Each transition requires a nonblank human reason and an explicit actor value. The actor value documents who asserted the action in this local demo; it is not an authentication claim. The only transitions are:

1. `new → triaged → approved → pending_verification → verified`;
2. `pending_verification → reopened → triaged` when verification still observes a mismatch; and
3. `new`, `triaged`, or `reopened → deferred → triaged`.

When first inserted, each case snapshots the complete discrepancy evidence required for review; details and approvals use that immutable snapshot rather than a later mutable Phase 1 output row. Approval records a proposed correction plus the payer and selected-reference values from the snapshot, and stores the proposal as the case's active value. Submission requires a payer submission reference and receives a server timestamp. Verification requires the observed payer value and an evidence note, then compares normalized values to the active approved proposal—not automatically to the original reference. A normalized observed proposal match verifies the case; a mismatch appends a `reopen` event and preserves the observed mismatch. Reapproval updates only the current projection while every earlier proposal remains append-only event history. Existing cases therefore remain inspectable through changed, removed, or QA-only pipeline outputs. Phase 3 presents this same bounded workflow in the local console, separating stored evidence, human judgment, and observed payer verification. It remains human-controlled: there is no automatic correction, payer writeback, bulk action, FHIR exchange, or authentication.

## Export

The pipeline writes:

- normalized provider records,
- provider directory exceptions,
- duplicate candidates,
- quality summary,
- Excel review workbook,
- operations review memo,
- SQLite review database,
- payer listings, source-precedence, reference-value, comparison, discrepancy, and risk-summary artifacts.

## Review

An operations reviewer would use the exception report to:

1. Fix high-severity missing fields.
2. Review duplicate candidates.
3. Re-verify stale records.
4. Identify source systems producing recurring issues.
5. Track cleanup status over time.

The exception report includes workflow fields:

- `review_status` starts as `new`.
- `assigned_to` starts as `unassigned`.
- `recommended_action` tells the reviewer what kind of follow-up is likely needed.
- `priority_rank` lets the reviewer sort the queue.

## Operational Rationale

Many healthcare data jobs do not begin with advanced modeling. They begin with:

- messy exports,
- missing fields,
- inconsistent source systems,
- stakeholder questions,
- manual cleanup,
- exception reports,
- repeatable weekly/monthly workflows.

The pipeline implements that operational layer directly.

## Current operational boundaries

The legacy pipeline receives several synthetic sources in one harmonized CSV. Its generated evidence is replaced on rerun; compatibility QA detail relies on the current batch. The durable Intake Workbench separately provides receipts, original artifacts, mapping/acceptance and later observations. Its synthetic sample picker uses that same intake service. Payer remediation and durable work preserve their own initial evidence and human history.

The October missing-NPI/leading-zero ZIP and source-update-as-verification defects now have fixes and regression tests. Normalization still does not establish the accuracy of source evidence. The dated review (historical reference retained separately) preserves the original reproduction, with current dispositions and qualification linked separately.

Validation and browser runs own separate fixture roots; API startup never reseeds evidence. Preserve a working database and its matching artifact root together. Durable work exports use a read-only SQLite snapshot and include all or one selected case; the all-work workbook ignores UI filters. Exports do not accept, resolve, verify or change work. See the [workbook contract](DATA_DICTIONARY.md#durable-work-handoff-workbook).

## Recurring clinic deliveries

After reviewing a ready file preview, save its mapping revision with a name/reviewer/reason. On a new file in the same source scope, select that revision and apply it; acceptance remains a separate decision. Reordered columns are safe, extra source columns stay retained, and missing selected headers require renewed review.

Expand the accepted-delivery comparison to see the exact baseline, raw/unique counts and filterable old/new fields with locators. Inspect blocked/quarantined and unresolved rows separately. Missing means absent only. If acceptance reports a changed baseline, refresh comparison, review the new previous values and retry with an explanation. Original observations, ownership and human verification history remain intact through repeats/restarts. The [SQL selected-delivery tool](OPERATIONAL_SQL.md) still asks the operator to choose its two accepted attempts explicitly.

## Network source setup and receipt interpretation

Expand organization/network setup before receiving a new network feed. Create or explicitly choose the payer, networks, clinic and practice locations; equal labels are not automatic matches. Review exact source-code bindings with actor/reason. Source keys belong to their namespace and kind. A replacement binding retains the older revision and requires the current ID.

Upload under a deliberate source/dataset scope, retaining declared completeness and as-of metadata. In column mapping choose network roster kind, map source network/location/organization codes and select only the reviewed bindings for that delivery scope. An explicitly fixed network is available for a true single-network feed; conflicting row codes require review. Reprocess, inspect valid versus quarantined rows, optionally save the reviewed configuration as a mapping revision, and accept explicitly. Network source assertions create scoped QA review work; they do not verify human decisions.

The source NPI identifies a provider only. Location/network bindings and native participation keys establish the other parts of row identity. Reported effective/end dates remain separate from receipt, retrieval and verification dates. Unknown identities remain original evidence rather than fabricated memberships. Scoped work/export and the final recurring network demonstration follow this storage slice.

## Recurring network review and scoped handoff

Apply the saved network mapping to a later delivery in the same declared dataset/network scope. Read one named accepted baseline, valid old/new changes, blocked-invalid identities, unresolved quarantine and missing records. Accepting valid rows records source assertions and separate QA comparison work for known invalid/missing keys; it neither accepts bad rows nor terminates membership. A full empty snapshot needs explicit acceptance as absence evidence.

Filter the Work queue by exact network, organization and practice-location IDs. Open the case scope and source-comparison evidence, assign follow-up and record an accountable QA disposition. Later deliveries retain ownership/history and never perform human verification. Download the explicitly selected network or case as XLSX/JSON. The all-work XLSX continues to ignore queue filters. Scoped operational sheets contain only selected relationships; full source receipt/attempt payloads are shared context and are labeled accordingly.

## Retained cross-source identity review

In Reconcile, select explicit source deliveries/types and inspect comparison quality. Save a candidate run, expand clinician or location evidence, then open its link review. Inspect both source assertions, contradictions, missing evidence and current links. Choose approve/reject/defer, record reviewer/reason and acknowledge review. Approval explicitly selects an existing typed target or creates a labeled one; clinician and location decisions are independent. Unknown person type or address purpose must be resolved before approval.

Reject/defer records pair history and keeps existing approved links. A competing review409 requires refreshing the snapshot and reviewing the evidence again. On an uncertain network failure, retry the exact pending request; do not alter it under the same request ID. Historical links/decisions remain visible after reload or later superseding approval. Acceptance and verified facts remain separate; this crosswalk never updates source records or creates network/case work.

## Field reconciliation and handoff

Open Reconciled field evidence within Reconcile and explicitly choose a reviewed clinician. Add a reviewed practice location for phone/address scope; leave it off for name/NPI scope. Inspect every retained source assertion and any network attribution, then select one coherent source value or explicitly retain the conflict. Record reviewer/reason and acknowledge the evidence. No source is selected automatically.

Changed links, source state/baselines or comparison rules make old preferences visibly stale. Refresh and review before writing again; another field's decision does not invalidate unchanged evidence. Download JSON/XLSX from the displayed snapshot. Readable workbook sheets summarize decisions/assertions; Payload chunks preserve complete types and long originals. Original multi-address rows remain labeled shared context; scoped records/options exclude unselected offices. Preferences do not update sources, certify provider facts or create follow-up tasks.

## Proposed change and read-only impact

With a current reviewed field selection/conflict, enter a typed proposed value and explicitly select the retained deliveries to assess. Save actor/reason and the proposal, then run impact preview as a separate action. Review both listing and existing-work coverage. Different known office/clinician or already-equal values are unaffected only within the selected scope; missing/ambiguous/stale links and unknown/excluded network scope remain unassessed. No external copies or payer systems are traversed.

If sources, fields or links change, refresh and review the current evidence and create a renewed proposal; inspect/reselect stale assessment inputs rather than assuming they carried forward. Duplicate deliveries keep their receipt identity while existing work follows exact reused observation provenance. Preview never changes owners/status/history, creates follow-up or verifies data. Explicit confirmation and plan export are described below.

## Confirmed follow-up and receipt acknowledgement

In Bounded follow-up plan, inspect all affected target actions and their source/network/clinician/location context. A single eligible open case is reused; multiple open cases require an explicit selection. Closed cases stay closed and require a new QA review. New QA scope is separately displayed in Work, including cases whose retained source has not been accepted. It does not create source participation. Unique source-native IDs can group repeated deliveries within exact scope; missing/duplicate IDs and CMS fallback remain retained-reference scoped.

Review the expected impact/plan, enter actor/reason and explicitly confirm. Refresh stale/competing plans before trying again. For an uncertain response, retry the unchanged pending request. An immutable proposal has one confirmed plan; a changed intent needs a revised proposal. Reused owners/status/proposals/initial evidence/history are preserved.

The saved receipt shows frozen confirmation intent alongside current cases and source freshness. Record acknowledgement against the displayed case version and prior acknowledgement; it records receipt only. Assign, investigate and verify through the normal case workflow. Download JSON/XLSX using the current receipt snapshot. Full assessment inputs, prior fields, initial work context, events and acknowledgement histories are included with explicit roles; shared original rows can contain other offices. A changed case/source/acknowledgement requires refreshing before export. No source, external directory or old downloaded copy is updated.


## Managed weekly clinic feed

Open **Managed feeds**. Start with an approved clinic normalization recipe in the exact source/dataset scope. Register an existing absolute local inbox and owner; inspect the proposed contract, approve it separately and explicitly enable that approved revision. The cadence is Monday 09:00 UTC with 24-hour arrival grace.

A producer writes the CSV completely, then atomically renames its `.manifest.json` last. Required manifest fields: `delivery_id`, Monday `period`, `as_of` (YYYY-MM-DD), `snapshot: full`, direct-inbox CSV `filename`, and `sha256`. An optional `supersedes` records corrected-source lineage. Do not reuse a delivery ID for corrected bytes. Unknown fields, traversal/symlink/nonregular files, hash errors and conflicting IDs appear as discovery issues.

Run the local worker against the initialized database/artifact root, or choose **Check deliveries and process one job**. Processing retains source assertions without accepting them. Inspect job errors, expected late windows, quality counts, quarantine and old/new/missing evidence. Required headers/empty snapshots are hard blockers. Any quarantine, missing prior key or raw-count change above the contract threshold (default 20%) holds approval. Extra columns remain retained warnings. First delivery baseline-dependent checks are explicitly unassessed.

Acknowledge acceptable soft risk with reviewer/reason or defer it. Only valid rows can be included; hard blockers require corrected source/contract and reprocessing. Explicitly approve or reject the exact candidate. A stale config/current pointer requires **Reprocess with current contract**, inspect its new report and decide again. Approval is distinct from contract approval, exception acknowledgement and provider verification.

Consumers discover the current approved version or select an earlier approved version ID and download its complete JSON. A later candidate never replaces the approved dataset until explicit promotion. Freshness warnings remain visible. An older-period/as-of delivery cannot regress current. No approved dataset means unavailable, not an automatic fallback. Downloads never mutate review/source state.

The worker stops when its process stops. Queued work and expired claims survive restart; an OS execution lock, heartbeats and token checks prevent competing workers publishing. Transient I/O/SQLite-busy failures retry up to three executions with persisted 5/30-second delays; validation failures require correction. Manual retry preserves pinned inputs; reprocessing creates a new job. Preserve source inbox, database, artifacts, rejected candidates and review history together. Publication remains a separate operation.


## Connected delivery review

Managed feeds is the default entry. Select a feed and a particular dataset version; its URL can be bookmarked. Jobs open their exact retained receipt/attempt, and versions expose the interpretation that produced them. Historical interpretations are read-only and newer attempts are flagged. Return to the current receipt workspace explicitly if new processing is intended.

After dataset approval, prepare reconciliation from that approved version. Confirm the pinned interpretation, select other sources and their supported entity types, then explicitly create a candidate run. Review clinician/location links before choosing field scope. Saved run, clinician/location, proposal and confirmed follow-up selections are reflected in the URL for reload/resume. Work-case links retain a return path to that review. Existing previews, acknowledgements, exports and approvals keep their separate meanings.

A held/rejected candidate never replaces the approved consumer version. Invalid feed/version/interpretation or cross-scope proposal/follow-up references require renewed selection; the interface must not quietly choose another record. Opening or restoring any step performs reads only. The [operator procedure](operations_governance/sop_provider_remediation.md#connected-managed-delivery-to-follow-up) describes the combined demonstration.
