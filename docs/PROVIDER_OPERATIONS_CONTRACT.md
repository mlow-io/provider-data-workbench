# Provider operations contract v1

PX0 design contract, proposed 2026-11-19. No migration, endpoint, integration or standards-conformance claim follows from this document. [Product scope](PROVIDER_RESEARCH_EXCHANGE.md), [operator experience](OPERATOR_EXPERIENCE.md), [operational measures](OPERATIONAL_MEASURES.md) and [STATUS](../STATUS.md) retain their respective authority. Scheduling update 2026-11-21: [S1](ADAPTIVE_INGESTION_SPEC.md) ingestion-first work precedes PX1. This contract is retained for later exchange/enrollment milestones under [ROADMAP](../ROADMAP.md); it is not the active implementation brief.

## 1. Scope and decision boundaries

The first journey prepares a pinned two-office exchange from an existing approved export, receives a supplied synthetic recipient response, previews its interpretation, explicitly links source rows and exports a selected rejection packet. It sends no data to a recipient and makes no network or model request. Preserve clinic originals, approved consumer versions, reviewed identities and existing work history.

Separate six facts: packet prepared; locally asserted sent; recipient file receipt; recipient row disposition; operator-selected working disposition; later directory observation. None establishes another automatically. Existing `follow_up_acknowledgement` records an internal reviewer acknowledgment and is not reused as recipient evidence.

## 2. Declared profiles and adaptive intake

All proposed profiles are immutable versions registered in application code/configuration, not executable user content. A profile defines container/media type, allowed schema, required identity keys, field meaning, normalization operations, source bounds and validation. The initial response profile is `synthetic-recipient-response/1`; its outbound companion is `synthetic-recipient-roster/1`. Later profiles are `cms-ppef-snapshot/1` and `nppes-v2-supplied/1`. These names describe application contracts, not published standards or live recipient compatibility.

A compatibility report pins the input receipt/artifact hash, selected worksheet/header/envelope, profile version and recipe revision. It lists supported fields, missing keys, extra fields, ambiguous bindings, source limits and whether deterministic preview is possible. Unknown/ambiguous input remains inspectable and cannot be accepted through a guessed clinic profile. A model may propose only field bindings and existing allowlisted transformations; no parser source, expressions, SQL, destinations or relaxed required fields are accepted. Approval creates a new recipe revision; applying it creates a new interpretation. Acceptance is a separate operation.

PX1 accepts UTF-8/BOM CSV with comma delimiter, one header, at most 1 MiB and 2,000 data rows. Identifiers are bounded text, at most 128 characters, preserving leading zeros, case and whitespace; no trimming or case folding is permitted for correlation. A nonblank response ID is required. Blank exchange/recipient/item keys remain retained unresolved source values with the applicable blocker; they cannot be confirmed. Empty optional fields remain null/unknown. The listed canonical headers are case-sensitive and ordered; only a leading UTF-8 BOM is ignored. Duplicate headers, invalid UTF-8, extra columns without a declared mapping, invalid enums and invalid timestamps produce explicit findings. Unknown columns can be retained as original evidence but cannot become business fields. A known new profile/version is selected explicitly after drift; old interpretations and approved versions are not rewritten.

## 3. Pinned outbound exchange

Preparing an exchange requires the selected approved dataset version, its export/records digests, exact input receipt/attempt, recipient identifier, recipient-profile revision, reviewer actor/reason and expected current source/link snapshot. The service validates these in one read/write transaction before saving immutable exchange and item records. Conflicting/stale inputs reject preparation; the existing consumer remains unchanged.

An exchange has an opaque `exchange_id`. Its manifest includes recipient/profile, source/approval pins, prepared server time, item count, artifact digest, designation and optional superseded exchange. A prepared packet is immutable. A correction creates a new exchange with explicit ancestry, never edits the earlier packet.

Each item has an exchange-scoped opaque `item_key`, source-native row identity, observation reference/locator, approved clinician link revision and approved office link revision. It may have a declared source network/product key. NPI alone is insufficient for office correlation. No duplicate item keys are permitted. The item map identifies exact outgoing row numbers and retains original values; row number alone is not the response key. A manifest does not claim delivery. An optional local sent assertion preserves actor time/timezone separately from server-recorded time and labels its basis; PX1 can demonstrate preparation and response handling without that assertion.

The fixtures use symbolic retained IDs and digests to define expected behavior; they are not an already approved application export. A test seed must construct corresponding real synthetic records and computed digests rather than bypass preparation validation.

## 4. Supplied response CSV

Required exact canonical header:

`response_id,exchange_id,recipient_id,response_scope,item_key,disposition,reason_code,source_effective_at`

| Field | Meaning and validation |
|---|---|
| response_id | Recipient-declared logical message ID, scoped to recipient/profile. It is not the upload ID or a proof of sender authentication. |
| exchange_id | Exact referenced outbound exchange ID. Missing/unknown IDs cannot be inferred from NPI, names or newest exchange. |
| recipient_id | Must equal the pinned exchange recipient. Wrong recipient is a correlation blocker. |
| response_scope | `file` or `item`. |
| item_key | Blank for file rows; exact outbound item key for item rows. |
| disposition | File: `received`, `rejected`, `unknown`. Item: `accepted`, `rejected`, `pending`, `unknown`. Meanings are limited to this synthetic profile. |
| reason_code | Bounded source code, optional; retained even if the code-to-label dictionary is unknown. Source code and operator interpretation remain separate. |
| source_effective_at | Optional RFC3339 time with timezone. Missing is unknown. Retain original text and normalized UTC separately. It is not a retrieval or verification time. |

Each interpretation retains every original row and locator. One response message must have one response/exchange/recipient triple. Multiple triples in one file are unsupported in v1, retained with a blocker. There may be one file-scope record and one record per item key. Identical repeated rows are retained as duplicate evidence and not counted twice; conflicting repeated dispositions within the message block that item. Unsupported rows never create an outbound item or identity.

Exact exchange/item keys produce a proposed correlation, not an operational decision. The reviewer confirms the association against its preview hash, current exchange/context and the response interpretation. No fallback join on provider name, NPI, phone or row order occurs. A mismatch remains unresolved with a precise reason such as `exchange_unknown`, `recipient_mismatch`, `item_unknown`, `item_ambiguous`, `profile_unsupported` or `context_stale`. PX1 permits confirmation only when exact exchange, recipient and item keys agree; it has no manual override for missing/wrong keys. Corrected source data is a separate retained delivery/interpretation. Any future explicit association exception requires its own contract and cannot rewrite original evidence.

File receipt does not propagate an item disposition. A file-level rejection and a row-level acceptance can coexist as source assertions but create a `file_item_conflict` blocking the affected working view. Lack of an item response is unknown/pending work, not acceptance or rejection.

## 5. Repeat, contradiction and staleness rules

The physical upload always retains its delivery/receipt provenance. Repeating the same request ID and intent returns the same result; the same request ID with changed intent conflicts. Equivalent logical responses can reuse an interpretation while retaining distinct physical deliveries.

A logical response identity is `(recipient_id, profile_version, response_id)`. Its semantic digest includes the exchange ID and the canonical multiset of all interpreted source rows, including multiplicity and reason/time fields; row order and transport newline/encoding markers are excluded. Compute SHA-256 over UTF-8 JSON with lexically sorted object keys, compact separators and unescaped Unicode; sort canonical row objects by their serialized bytes while preserving multiplicity. Represent empty optional fields as JSON null, preserve original identifier/reason/time text and include the profile version. Hash source bytes separately; semantic equivalence never replaces original evidence. A reordered equivalent response is not a new business outcome. Changed semantic content under the same logical ID is retained as `response_identity_conflict`, with no overwrite or default winner. A response with a different message ID is new evidence even when it concerns the same item.

Contradictory source messages retain both assertions. An explicit reviewer selection pins an exact confirmed response item and current contradiction/context snapshot. Selection is a local working decision, not proof that the recipient's assertion is correct. New contradictory evidence makes the previous selection noncurrent for reporting until reviewed again; its history remains readable. Never choose the latest import timestamp as truth.

An exchange's immutable source pins remain historically valid after new clinic data or identity-link revisions arrive. A later response may still be linked to that historical exchange. If present identity/office/source versions differ, show a stale-context blocker before using the response for a current correction or working selection. Revalidation pins the current context and records a new decision; it never moves the historical response to a different exchange.

## 6. PX1 state, actions and atomicity

Keep separate dimensions rather than one misleading success funnel:

- Exchange: immutable `prepared`; sent assertions are separate events.
- Response interpretation: `received`, `interpreted`, `invalid` or `identity_conflict`.
- Row correlation: `proposed`, `confirmed`, `unresolved` or `blocked`.
- Working disposition: `unselected`, `accepted`, `rejected`, `pending`, `unknown` or `disputed`.
- Directory outcome: independent `not_observed`, `matching`, `mismatching` or `unresolved` with its own evidence.

Service-action contract names below are conceptual, not implemented HTTP routes:

| Action | Inputs/preconditions | Result |
|---|---|---|
| prepare_exchange | Approved export and source/link pins, recipient/profile, expected context, request ID, actor/reason | Immutable manifest/items and digest or a conflict; no transmission. |
| receive_response | Source identity/profile plus bounded bytes and request ID | Retained response receipt; no linkage or state advancement. |
| preview_response | Receipt, exact interpretation/profile revision | Full counts, bounded row display, every proposed correlation/blocker and preview hash. |
| confirm_correlations | Expected interpretation/preview/exchange-context hashes, selected row-item pairs, request ID, actor/reason | Atomic confirmed associations for the explicit selection; unchanged source/clinic/identity state. |
| select_working_disposition | Confirmed source item, expected previous selection and contradiction/context hashes, request ID, actor/reason | New immutable selection/history or a stale/conflicting-input error. |
| export_rejection_packet | Exchange, selected item(s), exact decision/context snapshot and recipient template revision | Read-only pinned packet, scoped source evidence and unresolved issues; no state change. |

For explicit selections, one stale/invalid target fails the entire requested selection transaction. Unselected rows stay pending; valid rows may be reviewed in a separate request. Expected-version conflicts return a conflict class (HTTP 409 if exposed through HTTP); shape/profile errors are validation failures (422); missing named records are not found (404); explicit over-limit bytes are rejected before interpretation (413). Persist enough evidence to distinguish failed interpretation from empty success. No error path promotes a dataset or resolves a case.

## 7. Additive relational model

Freeze actual SQL and a numbered migration at implementation time. Reuse artifacts, receipts, attempts, observations, reviewed identity links and work cases. Do not add a second master provider record or event store.

Proposed new exchange relations: `provider_exchange` (manifest/artifact/profile pins); `provider_exchange_item` (unique exchange/item key, retained observation and clinician/office link revisions); `exchange_response` (receipt/interpretation and logical message/digest); `exchange_response_item` (response/locator, scope/disposition/reason); `exchange_correlation_decision` (explicit association and expected snapshot); and `exchange_disposition_decision` (versioned working selection). Resolved references use foreign keys; unresolved source IDs remain source values with a separate unresolved reason. Join to current reviewed links only through explicit revision-aware queries. Append-only decisions retain actor/reason/server time and idempotency intent hashes.

### CMS PPEF and NPPES extension

A PPEF import is one declared release plus its supplied file manifest, hashes, completeness and parser revision. Preserve `ENRLMT_ID` as source-native enrollment identity; it is not NPI or a local clinician ID. Keys always include the source snapshot:

- Enrollment: `(snapshot_id, ENRLMT_ID)`.
- Reassignment: `(snapshot_id, REASGN_BNFT_ENRLMT_ID, RCV_BNFT_ENRLMT_ID)` with resolved references to enrollment rows from the same snapshot.
- Practice location: one source enrollment plus city/state/ZIP tuple and retained row locator. Preserve duplicate occurrences; coarse geography cannot establish an exact street/suite office link.
- Secondary specialty and additional NPI: source enrollment/value rows, not replacement identities.

Missing referenced enrollments remain unresolved evidence. Do not join across releases, collapse several enrollments by NPI, or infer commercial participation from Medicare evidence. These are provider/enrollment relationships, not a patient master-person-index project.

For supplied NPPES V2 files, retain the release, base provider key and auxiliary other-name/location/endpoint references. The API and downloadable profiles remain separate. A supplied subset declares partial coverage. Incremental files require an explicit baseline/release chain; never treat a weekly update as a complete directory. NPI identifies provider records, not a verified operating office, license or payer enrollment. [CMS NPPES files](https://download.cms.gov/nppes/NPI_Files.html), [PPEF methodology](https://data.cms.gov/resources/fee-for-service-public-provider-enrollment-methodology-q1-2026), [PPEF dictionary](https://data.cms.gov/resources/medicare-fee-for-service-public-provider-enrollment-data-dictionary).

## 8. Bounded research contract

Research is later PX3 scope. A run pins one selected case/version, exact question, retained evidence/source-profile versions and allowed registered connectors. It may allocate at most two nonrecursive tasks. Parent accounting atomically reserves aggregate bounds: six requests, twenty resources, 2 MiB response bytes, three model calls, 120 seconds active wall time and a conservative $0.50 reservation. Effective bounds are the tighter connector/run limits. Calls, redirects, retries, references, failed responses and uncertain outcomes consume the same durable budget; task-local counters cannot reset the run allowance.

Tasks return strict findings: subject kind/reference, predicate, value or explicit unknown, `supported`/`contradicted`/`unresolved` assessment, supporting and contradicting retained evidence references, exact locators, source/effective/retrieval times, parser/model versions and coverage limits. A citation must resolve to an input/run artifact or observation, not merely a generated URL. A factual claim with no resolvable evidence fails validation or remains a labeled hypothesis. Conflicting claims coexist; research has no approval, identity-mutation, outreach, transmission or case-resolution tool.

Cancellation/revision fencing prevents late results from becoming current. Stale input results remain historical with their original pins. Retained responses can be replayed without refetching; a model call with unknown external outcome cannot automatically repeat after restart. Partial runs expose completed findings plus missing work; unavailable access is distinct from failed/empty sources. External processing follows explicit source permissions and bounded sampling. Do not send patient data or borrow developer-session credentials.

## 9. Recipient packet minimum

The first recipient-specific packet is the declared synthetic CSV template with exact item keys, requested change, target office and source-native recipient fields, plus a readable evidence manifest. It includes exchange/recipient/profile revision, source/approval/decision pins, source locators, original/requested values, unresolved fields, designation and digest. Missing required template fields block the affected item from the ready-to-send section; retain it in an unresolved-items section. Formula-like values are emitted as literal spreadsheet text under the existing export protections. Generation never asserts that a packet was sent or accepted.

A scoped rejection packet for SOUTH must not include NORTH operational rows. Shared original response files may contain both offices; label that original context explicitly rather than presenting it as selected operational scope. Reproduce identical selected content after restart from the same snapshot. Full template generation is PX4; PX1 may export the manifest/selected rejection evidence without claiming recipient-system compatibility.

## 10. Independent fixture expectations and acceptance

[Contract fixtures](../fixtures/provider_operations_contract/) are hand-authored synthetic examples with symbolic storage IDs. They are design inputs, not verification receipts. The expected outcomes are independent of any parser implementation.

PX1 acceptance requires: two office items retained under one clinician; original approved version unchanged; file received distinct from one accepted/one rejected row; explicit row/office correlation; unknown and contradictory keys visible; idempotent retry/reordered response handling; a stale selection rejected without partial writes; an inspected SOUTH-only rejection packet; and restart preserving all source/decision history. SQL totals, UI populations and exports must agree at the declared exchange-item grain.

For PX1, the rejection denominator contains only current, explicitly selected accepted/rejected exchange items. Pending, unknown, disputed and unselected items are separate counts. Response-item coverage counts exchange items having at least one confirmed item response; established-disposition coverage counts exchange items with a current selected accepted/rejected disposition. Each uses all exchange items as its coverage denominator. A file row contributes to neither numerator.

The fixture baseline has two exchange items and two established row dispositions only after the explicit confirmation/selection actions: accepted 1, rejected 1, rejection denominator 2, rate 1/2; both coverage measures are 2/2. It establishes zero independently observed directory corrections. A new contradictory message makes SOUTH disputed and reduces the established-disposition denominator to 1 until another explicit review; show one disputed item, established-disposition coverage 1/2 and response-item coverage 2/2 beside the resulting rate 0/1. No recovered revenue, compliance or live-payer claim follows.
