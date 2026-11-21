# Data Dictionary

Scope: current application contracts. The durable schema v13 extends the v4 operational tables with v5 recipes, v6 comparisons, v7 crosswalks, v8 field decisions, v9 change proposals, v10 confirmed follow-up, v11 managed feeds, v12 durable FHIR acquisition and v13 optional mapping runs. [SPEC](../SPEC.md) owns current product requirements; the [2.0 proposal](INTAKE_2_0_PROPOSAL.md) preserves historical design intent. D1 native evidence reuses the prior schema as specified in [the FHIR contract](FHIR_INTAKE_CONTRACT.md); D2 adds schema 12 and D3 adds schema 13 below.

Legacy generated QA/comparison tables are replaced by pipeline runs. Compatibility workflow tables persist separately, but general QA detail depends on the current batch. Legacy row IDs/provider keys are distinct from durable receipt and location identities.

## Input Fields

| Field | Meaning | Example |
| --- | --- | --- |
| `record_id` | Source record identifier used for review and traceability. | `REC-00001` |
| `npi` | National Provider Identifier. | `1234567890` |
| `provider_name` | Provider display name from the source. | `Sarah Patel MD` |
| `specialty` | Provider specialty or practice area. | `Cardiology` |
| `address` | Practice location street address. | `201 23rd Ave N Ste 400` |
| `city` | Practice location city. | `Nashville` |
| `state` | Practice location state. | `TN` |
| `zip` | Practice location ZIP code. | `37203` |
| `phone` | Public directory phone number. | `(615) 555-0101` |
| `accepting_new_patients` | Whether directory says provider accepts new patients. | `yes`, `no`, `unknown` |
| `source` | Source system or export name. | `payer directory` |
| `status` | Directory active/inactive status. | `active` |
| `last_verified_date` | Last known verification date. | `2026-03-15` |

## Synthetic Payer Listing Input

`data/raw/synthetic_payer_directory_listings.csv` is a deterministic, synthetic comparison input. It is used only when explicitly supplied and never replaces a source record.

| Field | Meaning | Example |
| --- | --- | --- |
| `listing_id` | Stable synthetic payer-listing identifier. | `PAYER-00001` |
| `reference_provider_key` | Explicit synthetic crosswalk key used to locate source-record evidence. | `npi:1234567890` |
| `npi` | NPI published by the payer listing; compared independently after crosswalk matching. | `1234567890` |
| `provider_name` through `status` | Directory fields compared field by field to the selected review reference. | `615-555-0181` |
| `last_verified_date` | Retained as payer-listing evidence but not compared until source-specific verification semantics are defined. | `2026-01-01` |

## Normalized Fields

| Field | Meaning |
| --- | --- |
| `phone_digits` | Phone number reduced to digits for validation and comparison. |
| `normalized_provider_name` | Uppercase, punctuation-light provider name used for simple matching. |
| `normalized_specialty` | Uppercase specialty value. |
| `normalized_address` | Uppercase address with common suffix normalization. |
| `normalized_city` | Uppercase city value. |

## Output Files

| File | Purpose |
| --- | --- |
| `normalized_provider_records.csv` | Cleaned and normalized provider records. |
| `provider_directory_exceptions.csv` | Row-level issues for operations review. |
| `duplicate_candidates.csv` | Potential provider/location duplicates for human review. |
| `quality_summary.csv` | Summary metrics by issue type and severity. |
| `operations_review_memo.md` | Plain-English review memo for stakeholders. |
| `provider_directory_review_pack.xlsx` | Excel workbook for nontechnical review with summary, exceptions, duplicates, normalized records, rules, and notes. |
| `provider_directory_truth_layer.sqlite3` | SQLite database containing the same review tables. |
| `synthetic_payer_directory_listings.csv` | Normalized copy of the explicit payer-listing input used in this run. |
| `payer_listing_identity_results.csv` | One matched or unmatched crosswalk outcome for every payer listing. |
| `field_source_precedence.csv` | Flattened configured ordering of preferred sources for every compared field. |
| `provider_field_reference_values.csv` | Selected nonblank field-level review reference, its source record, and precedence rank. |
| `payer_listing_field_comparisons.csv` | Complete listing-by-field evidence, including matches and unavailable references. |
| `payer_directory_discrepancies.csv` | Actionable subset of comparison rows with a mismatch or missing payer-listing value. |
| `directory_remediation_risk_summary.csv` | Counts of actionable discrepancies by configured risk level. |

## Directory Remediation and Verification Tables

These optional Phase 1 outputs are written to SQLite using the file names above as table names only when a payer-listing file is supplied. They are evidence tables; none is a provider-truth table or a remediation workflow table.

| Table / File | Required Fields | Contract |
| --- | --- | --- |
| `field_source_precedence` | `field_name`, `source`, `precedence_rank` | Lower rank wins when a nonblank source value is available. Precedence is configured separately for every comparison field. |
| `payer_listing_identity_results` | `listing_id`, `reference_provider_key`, `published_npi`, `identity_status`, `is_actionable`, `risk_level` | One crosswalk outcome per listing. An unmatched key is a high-risk listing-identity finding and has no field comparison rows. |
| `provider_field_reference_values` | `provider_key`, `field_name`, `reference_value`, `reference_source`, `reference_record_id`, `precedence_rank` | The selected review reference. `provider_key` is `npi:<NPI>` for valid NPIs and otherwise retains a record-specific key. |
| `payer_listing_field_comparisons` | `listing_id`, `provider_key`, `field_name`, `listing_value`, `reference_value`, `comparison_status`, `is_discrepancy`, `risk_level`, `risk_reason` | Complete evidence; values are compared in normalized form while raw display values remain inspectable. |
| `payer_directory_discrepancies` | All comparison fields above | Contains only `discrepancy` and `listing_missing` statuses. It is an input to later review, not an instruction to overwrite data. |
| `directory_remediation_risk_summary` | `risk_level`, `field_discrepancy_count`, `unmatched_listing_count`, `total_actionable_findings` | Stable high, medium, and low rollup for operational triage. |

`comparison_status` is one of `match`, `discrepancy`, `listing_missing`, or `reference_unavailable`. Only `discrepancy` and `listing_missing` have `is_discrepancy=true`. `identity_status` is `matched_reference_provider` or `unmatched_reference_provider`; only the latter is an actionable identity finding. Actionable rows receive a configured `high`, `medium`, or `low` risk; `match` is `none`, and `reference_unavailable` is `unverified`. Verification date is intentionally absent from the comparison contract until source-specific semantics are defined.

## Payer Remediation Workflow Tables

The local remediation API reads `payer_directory_discrepancies` as immutable Phase 1 evidence and adds the following separate workflow tables. It does not update provider, normalized, source, payer-listing, or Phase 1 evidence tables. These tables exist only after the remediation API initializes against SQLite output produced with an explicit payer-listing input.

| Table | Required Fields | Contract |
| --- | --- | --- |
| `remediation_case` | `case_id`, `listing_id`, `reference_provider_key`, `field_name`, `workflow_status`, `initial_risk_level`, `active_proposed_correction_value`, `evidence_snapshot`, timestamps | Current workflow projection. `case_id` is a deterministic hash of the stable listing ID, reference-provider key, and field name, excluding mutable values and risk. `evidence_snapshot` is the complete discrepancy row captured only when the case is first inserted; synchronization never replaces it. `active_proposed_correction_value` is updated only by approval or reapproval. There is at most one case for each identity. |
| `remediation_event` | `event_id`, `case_id`, `event_type`, `from_status`, `to_status`, `actor`, `reason`, `occurred_at` | Append-only history. Approval additionally records `proposed_correction_value`, `original_payer_value`, and `reference_value`; submission records `submission_reference` and `submitted_at`; verification/reopen records `observed_payer_value` and `verification_evidence_note`. |

`workflow_status` is one of `new`, `triaged`, `approved`, `pending_verification`, `verified`, `reopened`, or `deferred`. Valid state changes are `new → triaged → approved → pending_verification → verified`, `pending_verification → reopened → triaged`, and `new`, `triaged`, or `reopened → deferred → triaged`. Every event requires a nonblank `actor` and `reason`; actor is an explicit local attribution value, not evidence of authentication. Verification compares normalized observed payer value to `active_proposed_correction_value`, not automatically to the snapshot's `reference_value`. `payer_listing_identity_results` rows with `unmatched_reference_provider` do not create remediation cases.

## Directory Review Console Tables

The local review console reads the QA tables above and adds only these workflow tables to the same generated SQLite database. It never updates the provider or QA source tables.

| Table | Purpose |
| --- | --- |
| `review_case` | Current review-state projection for an exception in a QA batch: case identifier, status, assignee, latest note, and timestamps. |
| `review_event` | Append-only assignment, review, resolution, defer, and note events. Each event records a reason, optional note, state transition, assignee, and timestamp. |

`review_case` is a read-optimized projection. `review_event` is the audit record used to reconstruct how a case reached its current review state.

General QA case IDs include a batch fingerprint and row index. Old detail queries current generated exceptions; a preserved event does not preserve its original source evidence. Remediation instead retains initial evidence snapshots. These compatibility endpoints do not use the new work-version protocol. Shared storage now explicitly enables per-connection foreign keys, WAL and busy timeout; the durable intake/work contract is below.

## Durable intake schema (version 2)

| Table | Grain / retained meaning |
| --- | --- |
| `artifact` | Exact-byte SHA-256, size, generated storage key. |
| `receipt` | Delivery, source namespace, designation, label, received time, artifact, profile, duplicate receipt, metadata. |
| `attempt` | Versioned mapping/parser specification, fingerprint, state, full preview/quarantine, creation/commit time, acceptance actor/reason/policy. |
| `observation` | Native record ID or unresolved null, original locator/payload, normalized interpretation, provider/location projection, retrieval/source-update/human-verification dates. |
| `relationship` | Audited exact-provider/operating-location crosswalk; optional native location index for multi-address evidence. |
| `work_case` | Stable scoped work identity, immutable initial evidence JSON, status/owner/follow-up/version, active proposal/observed value, explained priority. |
| `work_evidence` | Initial and later source-observation links, independent of current issue detection. |
| `work_event` | Append-only accountable actions and from/to state with exact payload. |
| `schema_migration` | Applied numbered migrations; `PRAGMA user_version` rejects future schemas. |

Artifact identity is not business identity. Identical source/artifact/specification reuses an interpretation while retaining another receipt. Changed mapping creates an attempt; changed/reordered source-native rows link to scoped work and retain original snapshots. Missing native identity remains unresolved. A bounded response's absence is only `missing_from_this_delivery`; no termination is inferred.

NPI supports provider identity, not operating location, enrollment or payer listing. Supplied location IDs are source-scoped; native multi-address records retain all locations and require explicit practice-address selection for crosswalks. CMS native composites retain enrollment/group/address grain. Phone discrepancies in the new workbench compare explicit listed and requested values at that location. Legacy provider-precedence comparisons remain a separate compatibility path.

`retrieved_at`, `source_updated_at`, source publication/modification metadata, and `human_verified_at` have distinct meanings. A source update never becomes human verification. Human correction verification is recorded in the work event and observed-value projection; it is not a write into provider evidence. CSV actual nulls stay blank; literal `NA` stays text; leading-zero identifiers remain strings. Simple XLSX all-zero numeric display formats are retained along with raw cell metadata; formula cells are quarantined.

## Exception Review Fields

| Field | Meaning |
| --- | --- |
| `review_status` | Workflow status for the issue. Defaults to `new`. |
| `assigned_to` | Reviewer owner. Defaults to `unassigned`. |
| `recommended_action` | Suggested next action derived from the issue type. |
| `priority_rank` | Numeric sort key derived from severity and issue type. Lower means higher priority. |

## Workbook Tabs

| Tab | Purpose |
| --- | --- |
| `Summary` | High-level record and issue metrics. |
| `Exceptions` | Review queue for data quality issues. |
| `Duplicates` | Possible provider/location duplicate candidates. |
| `Normalized Records` | Cleaned provider records after normalization. |
| `Rules` | Current QA configuration values. |
| `Review Notes` | Plain-English reviewer guidance. |
| `Payer Listings` | Normalized synthetic payer-directory listings used for deterministic comparison. |
| `Listing Identity` | One crosswalk match outcome per payer listing. |
| `Field Precedence` | Configured source rank for every comparison field. |
| `Reference Values` | Field-level selected reference evidence. |
| `Field Comparisons` | Complete payer-listing comparison evidence. |
| `Discrepancies` | Actionable payer-directory discrepancies only. |
| `Remediation Risk` | High, medium, and low discrepancy summary. |

## Issue Codes

| Issue Code | Meaning |
| --- | --- |
| `missing_required_field` | A required field such as NPI, specialty, address, city, state, or phone is blank. |
| `invalid_or_missing_phone` | Phone is missing or has too few digits. |
| `inactive_or_unknown_status` | Provider record is not marked active. |
| `missing_verification_date` | No last verification date exists. |
| `stale_verification` | Last verification date is older than the configured threshold. |
| `invalid_accepting_new_patients` | Accepting-new-patients value is not `yes`, `no`, or `unknown`. |
| `possible_duplicate_provider_location` | Multiple records share the same normalized provider/location key. |


## Durable work handoff workbook

`GET /api/work-export.xlsx` exports **all durable work**, irrespective of UI filters or the 200 rendered matches. Optional `case_id` exports exactly one case (404 if absent), all its linked initial/later observations, relationships and decision events. Legacy QA/remediation cases are excluded. Related receipt deliveries include matching source/profile/artifact repeats; their complete attempt previews can include rows outside the selected case. This is evidence context, not additional selected work.

The exporter opens SQLite in read-only/query-only mode, begins a transaction, and pins its snapshot with the first read. Every subsequent receipt/evidence/event read uses that connection and snapshot. Reads finish before XLSX rendering begins. `snapshot_at_utc` describes the pinned read, not a business event or source date. It writes no source, case, version, event or artifact. No schema migration is needed.

| Sheet | Content / grain |
| --- | --- |
| Read me | Format version 2, snapshot time, exact scope/count, value/date/null/safety conventions and limits. |
| Cases | One current work projection; explicit provider/NPI/location/native/listing identifiers, field, issue/risk, status, owner/follow-up/version, immutable initial listed/requested values, active approved proposal and latest observed value. |
| Evidence | One case/observation link, marked initial or later; source/designation/artifact, receipt/attempt/native IDs, row locator and location fields. Initial columns use the case's immutable selected practice-address snapshot. Later columns use the latest explicit relationship for that observation and the same provider/location scope, including its selected native address and locator. Separate native-observation identifiers/locator and payload retain the original multi-address grain. |
| Receipts | Related original/repeat delivery identifiers, labels, source/designation/profile, dates, digest and duplicate relationship. |
| Attempts | All attempts for included receipts, with mapping/preview/quarantine/acceptance retained in the payload. |
| Decisions | Every append-only work event, accountable actor/reason, from/to status/time, owner/follow-up inputs, proposal, simulated submission reference, observed result and verification note. |
| Relationships | Audited explicit native provider/location choices matching the exported case’s provider and location, including native location index and reviewer/reason. Other locations on a shared observation are not attributed to this case. |
| Payloads | Complete JSON for referenced case snapshots, native observations, receipts, attempts and events. Concatenate `json_chunk` by `payload_id`, ordering `part` numerically, then parse JSON. Long scalar displays reference `payload:ID`. |

Full export reads are not limited by the UI's 50 observation sample, eight visible preview rows or 200 rendered cases. Excel has a 1,048,576-row sheet limit; exceeding it returns a clear error suggesting selected-case export. Export is an in-memory local operation, not a large-scale reporting service.

All populated cells, including identifiers, dates and formula-like `=`, `+`, `-`, `@` strings, are literal text with no executable formulas or hyperlinks. Null displays as a blank cell; empty text displays as two quotes. JSON payloads preserve the exact distinction, types and originals. Prohibited XML controls in scalar displays are escaped. ASCII JSON is split into numbered chunks of at most 30,000 characters rather than silently hitting Excel's cell limit. The JSON payload is authoritative for exact values.

`listed_value` and `requested_value` are initial source assertions; `approved_value` is the current human proposal; `observed_value` may represent a failed verification. A populated observation does not imply verified status. Source update/retrieval/receipt dates do not establish human verification. Human verification actions, times and notes remain Decisions records; the original observation's `human_verified_at` is not rewritten by workflow review.

## Recurring interpretation revisions

`mapping_revision` stores one immutable reviewed source/profile/scope-specific template: opaque ID/name, effective column/parsing settings, required header names, actor/reason and creation time. Update/delete guards preserve every revision. Attempts retain their own immutable `spec` and fingerprint; accepting an attempt updates its state/decision, never its interpretation. Saving/applying a template is separate from acceptance.

For clinic files, longitudinal identity is source scope plus source-native `record_id` and supplied `location_id`; neither row number, bytes nor provider label is an identity. Every duplicate/conflicting key is quarantined. Preview counts distinguish raw rows and unique identities. A known invalid key is `blocked_invalid`; an unresolved row cannot suppress a baseline record's `missing` entry. The baseline is exactly one accepted attempt, never a union of latest keys from history. Its ID is pinned in `attempt.spec.baseline_attempt_id`, excluded from the interpretation fingerprint, and rechecked at acceptance. The mapping revision remains part of the fingerprint.

Schema migration 3 adds the mapping table/index/guards and immutable attempt-spec guard, preserving existing tables/IDs/history/artifact links. Existing v1/v2 databases receive a `.pre-intake-v3.bak` SQLite backup before this additive transaction; fresh databases apply migrations 1–3. Migration and rollback rehearsals use owned copies. Back up the database and matching artifacts together.

## Explicit organization/network records

| Table | Grain and contract |
| --- | --- |
| organization | One opaque local organization ID with label/kind, issuing-namespace identifiers and accountable creation. Labels are not identity. |
| network | One opaque payer-network ID, optionally referencing a known payer organization. Unknown owner remains null. |
| practice_location | One explicit local practice location, optionally linked to an organization. NPI alone never chooses a location. |
| identity_binding | One immutable reviewed source/kind/exact-key revision. Typed organization/network/location FKs and a kind CHECK require one valid target; previous revision and expected-current checks retain corrections without rewriting earlier evidence. |
| participation_observation | One accepted source assertion linked by observation_id. Native key, provider, local location, network, optional supplied organization, mapping revision, source-listed status, reported dates, binding snapshot and original labels remain separate. |
| case_scope | One new network-review case's explicit network/location/native-key scope, with supplied organization when known. Existing clinic case IDs are unchanged. |
| participation_review_evidence | One append-only comparison-evidence link to a case and processing attempt. Source comparison evidence is separate from human work events. |

Network longitudinal identity is source/dataset scope + native participation key + provider + explicitly bound practice location + network. Rows in different networks or at different locations cannot collide. Original source codes and as-imported labels stay in original/normalized payloads; binding corrections create new interpretations. The source-listed status/effective/end dates never establish human verification, licensing, credentialing or patient benefits. Invalid or contradictory dates quarantine the row.

Schema migration 4 adds these tables, typed FKs, scope index and immutable-record guards. It never backfills network membership for old rows or rebuilds existing cases. Existing databases are backed up with SQLite's backup API to `.pre-intake-v4.bak` before the transaction; migration rollback/integrity/FK and populated v3 preservation are rehearsed on owned copies. Keep each database with its matching artifact root.

## Network comparison evidence and scoped handoff

`participation_review_evidence` retains accepted-row source assertions and missing/known-invalid comparisons linked to processing attempt/receipt. A missing/validation case can have no accepted observation: its immutable initial snapshot explains the current receipt, baseline references and quarantined source row. It must not be presented as an accepted participation. Its source evidence appends separately from work_event, and later source data never changes human workflow automatically.

Network work items add explicit catalog scope and label fields. Case detail includes that scope and source-comparison history; review actions still use expected_version and append human events atomically. Missing and validation case identities use the same full participation scope plus finding kind. Unknown network/location/provider bindings remain quarantine, with no invented case membership.

Format 2 exports add network/organization/location labels to Cases. Network exports additionally contain Participations (case/accepted-observation link, source status/reported dates/receipt metadata), Review evidence (case/attempt/comparison row), Catalog (referenced organizations/networks/locations only) and Bindings (row bindings for the selected operational scope). All/case/network reads are consistent and non-mutating. Complete shared receipt/attempt payloads remain source context, not additional scoped operational rows. Related repeated-byte receipt discovery also checks declared dataset scope.

Shared writable connection contexts commit or roll back and then close deterministically; backup targets close explicitly too. Python's native SQLite context manager alone does not close a connection. Closing each completed request prevents retained connections/late WAL checkpoints; read-only exports and SQL queries still use their own explicitly closed snapshot connections.

Case scope and its organization filter describe the immutable initial work scope. Later source organization assertions remain separate evidence; selected handoffs include all catalog/binding references actually used by those accepted observations, without rewriting initial work scope.

## Normalization recipes and provenance schema 5

`recipe_revision` stores immutable proposed/approved definitions, parent revision, source/profile/dataset scope, receipt/attempt, actor, reason and timestamp. Approval creates a separate row. `observation_normalization` links accepted observations to approved recipes and complete per-field transformation evidence. Update/delete triggers protect both histories; previous observations and attempts remain unchanged.

Recipe compatibility and reuse add no tables or migration. Approved leaves in the existing parent chain are retrieved only within exact source/profile/scope; an approved correction supersedes its ancestor as a recommendation, while history and previously pinned applications remain intact. Reuse creates an ordinary proposed revision whose parent is the approved example. Header drift is computed from retained artifacts and the original pinned attempt settings; reports are read-only, not persisted approval facts.

Field evidence retains the source column, original value, transformed value, ordered before/after operations and findings. Applying a recipe creates an attempt with `spec.recipe_revision_id` in its fingerprint. Saved recurring mappings retain that ID. Repeat deliveries can reuse the same committed interpretation while recording a new receipt.

Schema 5 is additive. Existing databases receive a `.pre-intake-v5.bak` SQLite backup before migration; unknown future schemas are rejected. MCP attachment requires a current schema without migration/startup recovery. See [source onboarding](SOURCE_ONBOARDING.md).

## Source onboarding and comparison extensions

Schema 5 retains immutable proposed/approved recipe revisions and application provenance; see [source onboarding](SOURCE_ONBOARDING.md). Optional `suite` and `address_line2` mapping fields retain separate address components.

Schema 6 adds `observation_comparison` (accepted observation plus rule-version evidence), `comparison_run` (selected receipt/attempts, retained records, scoped baseline snapshot, actor/reason and measured counts) and `comparison_candidate` (run-scoped typed pair, rank, eligibility and explained evidence). Update/delete triggers protect these append-only records. Migration creates a versioned v5 backup; existing accepted records are not rewritten.

Comparison evidence retains original values separately from versioned comparison values and field findings. Native practice/mailing addresses keep exact paths; clinician row identity remains separate from address references. Null, blank, missing and malformed values are distinguishable. Current rule version is `provider-comparison-v4`. Candidate IDs/order are deterministic for pinned inputs/rules. No comparison record is an approved identity link or verified fact.

## Reviewed identity extension (schema 7)

`clinician_identity` stores opaque local identity IDs, reviewer labels, identifiers and actor/reason/time. Creation does not certify a source identifier. `identity_review_decision` retains exact run/candidate, typed retained-pair key, decision, target, prior pair decision, expected snapshot and full request hash/unique idempotency key. `reviewed_identity_link` appends independently versioned clinician-row or native operating-address references to a clinician/practice-location target with foreign keys, previous link revision and creating decision. Updates/deletes are rejected by triggers. Current links are the latest revision per kind/reference, independent of pair rejection/defer history. New deliveries do not inherit links automatically. Schema-6 backups and transactional rollback protect existing runs/candidates during migration.

## Field-decision extension (schema 8)

`reconciled_field_decision` retains a typed clinician/location scope, field, select/conflict decision, selected exact reference/value, evidence snapshot, reviewed view snapshot, complete selected assertion/conflict evidence, previous decision, unique request ID/full-content hash and actor/reason/time. Foreign keys retain the clinician/location targets; checks enforce clinician-only name/NPI versus location-scoped phone/address and selected-reference semantics. Triggers reject update/delete. A versioned schema7 backup precedes transactional migration.

The evidence snapshot controls staleness; the view snapshot additionally pins current field-decision IDs. Current stale selections have no active preferred value while their historical values/evidence remain available. Phone includes its extension and address includes all components from one source; field selection never assembles components across sources. Null/blank/malformed values remain original evidence; explicit absence preference is not certification.

Comparison v4 resolves all supplied entity-type discriminators together. A null/malformed generic field cannot hide a known NPPES discriminator. Contradictory known aliases remain unknown with retained evidence and cannot be declared away. Older runs remain readable but must be regenerated/reviewed before writing preferences. Cross-run organization/person declaration conflicts also block fresh field decisions.

## Change proposals and derived impact (schema9)

`change_proposal` stores immutable request ID/content hash, typed clinician/location/field, original/canonical proposed target, complete prior field evidence, field-view snapshot, explicit retained input pins/records/baselines, network scope, comparison version, previous/root proposal IDs and actor/reason/time. Foreign keys preserve target/previous references; scope checks enforce clinician name/NPI versus practice phone/address. Update/delete triggers protect history; schema8 backup/transactional rollback preserves existing field decisions.

Impact preview is derived read-only. It returns listing and existing-work classifications with independent counts/pages, reasons and a dependency snapshot; it persists no assessment/work state. Clinician-level targets deduplicate native addresses by retained clinician row; practice targets retain exact address refs. Unknown/excluded/stale evidence remains not assessed. Duplicate receipts expose their selected attempt separately from the original observation evidence attempt. Exact work provenance, scope and version participate in the snapshot. Confirmed assessment/work association records are schema10 below.

## Confirmed follow-up extension (schema10)

`follow_up_confirmation` stores unique proposal/request IDs, full request hash and request-ID-independent intent hash, impact/plan snapshots, complete frozen assessment/plan, actor/reason/time. `follow_up_association` stores confirmation/proposal/target key/field, existing-or-new case ID, all retained refs, complete action/scope evidence, case version at confirmation, create/reuse and attribution. A unique proposal/target/field constraint prevents duplicate associations. `follow_up_acknowledgement` stores immutable attributed receipt history with unique request/hash, prior acknowledgement and observed case version. All three tables reject updates/deletes; foreign keys and a schema9 backup protect migration history.

Target keys use explicitly unique original flat record IDs or NPPES numbers within source/profile/query/comparison/network/source-location/reviewed clinician/location/field scope. Missing/duplicate IDs and CMS rows use exact retained refs. New QA evidence references actual retained receipt/attempt/locator, with no invented accepted observation. Follow-up scopes are derived from immutable associations and remain separate from source participation. Reusing work changes no original case/evidence/event row; acknowledgement changes no case state. Frozen assessment intent and current source/work/acknowledgement snapshots have separate meanings.


## Managed recurring feed (schema 11)

`feed` identifies one source/profile/dataset scope and projects its active configuration revision and current approved dataset. `feed_config` is immutable attributed configuration history. `feed_contract` holds separate proposed/approved immutable revisions; its definition pins an approved normalization recipe, required headers, text/null/native-key semantics, CSV parsing, full-snapshot scope, source data designation inherited from the recipe sample, output schema and quality policy. Contract approval never accepts a delivery.

`feed_delivery` retains one source-issued delivery ID, complete manifest and original artifact digest. Same-ID conflicting bytes/metadata become a visible issue and block approval of that ID. Same bytes in a new period retain a separate delivery and approval even when accepted observations reuse an interpretation. Inbox inputs are never modified/deleted.

`feed_job` is the mutable execution projection: queued/running/retry_wait/succeeded/failed/cancelled, pinned delivery/contract/config/baseline, persisted receipt/attempt stage IDs, execution count, claim token, lease, retry time and error. `feed_job_event` appends claims/retries/cancellation/reprocessing/completion. One OS-locked worker lane prevents concurrent parsing; heartbeats and token/expiry checks fence publication. API startup excludes these owned attempts from legacy interrupted-attempt recovery.

`feed_version` is one immutable candidate per job: full rows/quarantine, manifest, policy/report and checksums. `feed_exception` records attributed acknowledge/defer events for exact-report soft holds. Hard blockers cannot be waived. `feed_decision` records one immutable approved/rejected decision with idempotency key/request hash. Explicit approval accepts valid intake rows and advances `feed.current_version` in the same transaction; exceptions never make quarantined rows valid. Ordinary intake mapping/acceptance rejects managed receipts.

`feed_window` projects expected weekly periods; immutable `feed_window_event` retains observed transitions. `feed_issue` retains malformed/missing/hash/conflicting delivery diagnostics. Missing from a full delivery is absence evidence, never termination. Required-header failures retain raw counts while unassessed interpretation counts are null.

Consumer JSON is addressed by an approved version ID, independent of receipt-latest state. It contains complete valid records, quarantine, original locators/values, normalization lineage, delivery/contract/recipe/baseline, report/checksums, approval and frozen exception history. Interactive row/comparison-entry previews stop at 50; complete exports do not. A held candidate leaves the prior approved pointer intact; current lookup labels freshness. No first approved version means unavailable. Backups before schema-11 migration use `.pre-intake-v11.bak`; retain the matching artifact root. Direct database edits remain outside the trust boundary.


## Connected review context

A managed feed version's retained manifest identifies its exact receipt and interpretation attempt. Navigation uses those identifiers rather than the receipt's newest attempt. An explicit historical receipt read reports that attempt's preview/state, accepted or reused observations, and linked cases from one SQLite read snapshot; all attempts remain available as history. Links do not create dataset approvals, clinician/location identities, field preferences, change proposals or follow-up confirmations. No schema change is required.

## Investigation outreach

Outreach is an append-only work_event action with structured contact_at/method/outcome and optional contact_target/respondent_role/response_summary/reported_phone in payload JSON. occurred_at is the server record time; contact_at is the asserted contact time including timezone. There is no migration or additional case identity. The action preserves status, ownership, scheduling, proposal and observed result while incrementing the case version. Investigation summaries are derived within the existing export snapshot, not a new database of record.

## Native FHIR reference evidence — schema 11 reuse

D1.2 adds no tables or migration. `receipt.profile=fhir-plannet-r4` selects a dedicated interpreter and explicit reference-resource acceptance path. `attempt.spec` pins the native parser/projection version; its immutable fingerprint includes source namespace, dataset scope, artifact hash and specification.

`attempt.preview.rows` retains one entry/resource locator, exact original resource, scoped source-native type/id, native normalized metadata/assertions and eligibility problems. `preview.native` retains the resource/reference/assertion graph, coverage, validation states and findings. Unsupported or malformed content remains in source bytes and diagnostics. Resource counts are not complete clinician-row counts.

Explicit native decisions store expected attempt, actor/reason, receipt-scoped request ID and intent hash in the existing `attempt.decision` JSON. Accepted eligible resources use `observation` with null provider/location projections; no clinician/office keys are fabricated. A repeated committed interpretation records `reuses_attempt` and reuses original observations through existing detail lineage. Source-native graph edges are not stored as human-reviewed `relationship` rows.

Native comparison records retain `supporting_refs` as `{attempt_id,locator,path,field}` objects plus raw `source_network_reference` and unknown profile/terminology states. Local network IDs remain null. These references survive candidate/field decisions, impact/follow-up evidence and scoped JSON/XLSX payloads. Source context includes all contributing resource rows; NORTH evidence does not silently include SOUTH rows as selected evidence. Receipt artifact context may contain both and is separately labeled.

## FHIR acquisition extension — schema 12

Schema 12 adds `fhir_acquisition` and `fhir_acquisition_event`; it does not rewrite existing source observations, identity links, case history or approved clinic versions. A stopped populated database is backed up to `.pre-intake-v12.bak` before migration. Backup verification/restore supports schema-11 archives as well as current schema 12; restore preserves the old archive, and the application upgrades only the restored copy when opened.

`fhir_acquisition` stores one globally unique request ID and full-intent hash, immutable-at-creation config, mutable revision/state/checkpoint, persisted due retry, optional result receipt and creation time. Checkpoint records pending and completed URLs, exact-body artifact references, page/reference/request/byte/time/retry budgets and error context. Worker request/response transitions increment revision; cancellation fences an in-flight result.

`fhir_acquisition_event` is append-only (database triggers reject ordinary UPDATE/DELETE). Each event retains acquisition ID, sequence, kind, request/response/error metadata, optional exact-body artifact hash and recorded time. Cookie/authorization headers are excluded; selected content/version/rate-limit/redirect headers are retained. Empty/network failures do not invent response files; capped bodies are explicitly truncated.

Finished captures create a separate derived searchset artifact, receipt and native attempt atomically with the result pointer. Result IDs are deterministic per operation, preventing partial publication/restart duplicates. Equal entries can share an assembled resource while retaining every original source-page origin. Raw native references and local reviewed identities remain distinct. Reference acceptance and approved clinic dataset promotion remain separate decisions.

## Optional mapping assistance (schema 13)

`assistant_run` pins one request identity/intent, receipt/attempt, public provider configuration, bounded input context, exact request artifact and optional response artifact. It stores state/revision, integer micro-USD reservation, result JSON and optional recipe proposal ID. `assistant_run_event` is append-only request/response/cancellation/failure/publication evidence with optional retained artifact hash. No key or Authorization header is stored. Source permission basis and explicit run consent are retained with context/events. Optional `include_approved_examples` permission in the creation event selects a separate prompt version; `context.approved_examples` retains its versioned policy, selected revision/receipt/attempt/artifact pins, candidates examined, omitted count and UTF-8 example byte count. The provider body includes only selected definitions and revision IDs, never prior source cells or reviewer attribution. Selected approved leaves are checked before invocation and inside publication transactions. This is additive JSON in schema 13, with no migration or backfill; older runs keep their original prompt and context.

The reservation is 80,000 micro-USD per invoked run, within 1,000,000 micro-USD lifetime allowance in that database, including unknown outcomes. This is a conservative local estimate at dated rates, not invoice-exact billing. Partial/truncated/error responses remain diagnostic artifacts when available; 401/403 bodies are excluded to avoid retaining echoed credential fragments. Invalid proposals retain available usage/cost and raw output without creating a recipe.

Only immutable proposed recipes are produced. Atomic publication connects the recipe, succeeded run and history event; approval/application/acceptance continue through existing services. `normalization.assistant` carries run/model/input/sample/response and optional approved-example provenance into accepted observations and exports. Evidence packets include full receipt-scoped run history with raw bodies referenced by hash. Reprocessing creates a new attempt; an older run cannot silently publish against it.

Populated schema-12 storage is backed up to `.pre-intake-v13.bak` before additive migration. Stopped schema-11 and schema-12 archives remain verifiable/restorable; restored copies migrate only when opened by the current app. Neither archive bytes nor original artifacts are reinterpreted in place.

## Source cooldown and approved contact projection

D4 preserves schema 13. FHIR acquisition request/response events now include `source_wait_until`; the effective future maximum is derived across configurations with the same source base in this workbench, including completed/cancelled/failed operations. Existing operation retry timestamps are also considered. A `source_wait` event retains a no-request decision without consuming request budget. The registry exposes the future due time as `source.next_request_at`, otherwise null. Retained Retry-After applies even when retry or response-byte budgets fail; local publication performs no HTTP request and is exempt.

The independent approved-data reader consumes the existing schema-1 managed-feed export and emits `consumer_schema_version=1`, version/feed/input/records/report digests, declared designation, approval context, contacts and a source-assertion notice. A contact contains text `record_id`, `location_id`, `npi`, `provider_name`, `address`, `city`, `state`, `zip`, `phone` and optional `phone_extension`. Native key is `(record_id, location_id)`; ordering is deterministic by that key. Extension absent/null/blank/text distinctions survive projection. No source values are repaired by the reader and it stores nothing. Its narrower representation requirements and resource bounds belong to [OPERATIONS_DEMO](OPERATIONS_DEMO.md#small-approved-data-consumer), not a changed producer schema.

The operations dossier is a synthetic file index linking the existing approved JSON, consumer JSON, selected field JSON/XLSX and selected investigation JSON/XLSX by SHA-256. It identifies clinician, reviewed location, identity-review run, source case and approved version. It does not merge these scopes or create another durable case table. Complete shared receipts/Bundles may contain SOUTH; selected field rows/cases remain NORTH-only.


## HAP routing and native-ID queries

The follow-up live-boundary change preserves schema 13. Optional immutable acquisition `config.resource_id` is a source-native FHIR ID, serialized as one `_id` query parameter. When present, it also participates in the receipt's scope digest and appears in `metadata.query` with resource type/count. Unfiltered scope hashes and receipt shape remain unchanged. A query is a declared request scope, not proof that a source is complete or truthful.

Pending nodes, retained bodies and request/response event payloads can include `source_url` when a declared HAP URI was routed to the fixed published origin. `url`/resource-origin `request_url` remain the actual fetched gateway URI. Reference entries in the derived Bundle use their advertised `source_url` as `fullUrl`, preserving source reference identity without changing resource values. Search-page entries remain byte-derived from their original pages. Relative references resolve within the originating resource's declared REST base; disallowed bases remain unresolved. The exact authority, path, port and query rules belong to [PUBLIC_DATA_SOURCES](PUBLIC_DATA_SOURCES.md#d20-selected-acquisition-contract). No alias can be configured by an API payload or inherited by a test-only source.

## Filtered query validation report (R1)

Schema 13 remains unchanged. A newly published filtered receipt and its publication event add `query_validation` version 1 with requested resource type/ID and raw captured-page match, implicit-match, include and outcome entry counts. Implicit matches are a subset of matches. Direct reference fetches are counted by the existing acquisition reference counter, not by this report. Counts include duplicate source page entries; derived resources can be deduplicated while retaining every raw origin. In filtered derived output, a matching copy takes precedence over an otherwise identical included copy, preserving original search metadata in the unchanged raw pages.

The report is recomputed from digest-verified retained pages before publication; it is not trusted from new checkpoint counters and requires no extra request. Query integrity is separate from resource eligibility, standards validation, human review and provider truth. Old completed receipts are immutable and do not receive a report retroactively; unfiltered receipts retain their prior shape. Failures retain response events/artifacts without a ready receipt or approval effect. [The source contract](PUBLIC_DATA_SOURCES.md#filtered-response-integrity-r1) owns exact rejection and empty-result behavior.

## Native parser revision R2

`fhir-plannet-r4-v2` is an interpretation version, not a schema version or source `meta.versionId`. Its supported Network profile set is the bare canonical or exact `|1.2.0`; unknown explicit versions remain unresolved. The Plan-Net 1.2 subset permits at most one Network-reference extension per role projection. Multiple references remain in original/native evidence with a cardinality finding; no preferred network or office cross-product is invented. Old v1 attempts/observations remain immutable until a separately reviewed new interpretation. The [eight-resource qualification](evidence/canonical/provider-graph-2026-11-14/README.md) retains NORTH/SOUTH export locators and explicit local binding boundaries.
