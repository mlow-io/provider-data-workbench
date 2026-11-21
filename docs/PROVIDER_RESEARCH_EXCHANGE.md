# Scoped provider research and exchange

Proposed product extension, 2026-11-19. No behavior, migration or endpoint in this document is implemented merely by being specified. [STATUS](../STATUS.md) records delivered behavior; [NEXT](../NEXT.md) selects the active brief. Existing evidence, schemas and manual workflows remain valid.

## Scheduling and relationship to adaptive ingestion

Updated 2026-11-21: [ROADMAP](../ROADMAP.md) supersedes this document's original first-journey priority. [S1](ADAPTIVE_INGESTION_SPEC.md) owns immediate ingestion/profile adaptation. Reuse the profile concepts here; do not build a second registry. Recipient exchange and bounded research are later P7 work. Runtime adaptation remains declarative; agent-generated parser code may be proposed through ordinary reviewed development in a later selected scope, never executed as uploaded configuration.

## Outcome and first journey

A provider-data operator needs to explain what happened to a clinician/office change, reconcile source relationships, and prepare an evidence-backed follow-up. Extend the existing workbench around this journey:

1. Select a retained two-office clinic delivery and its reviewed identities.
2. Prepare a version-pinned exchange for a declared recipient profile. In the initial rehearsal, submission is a local assertion and sends nothing.
3. Receive a supplied acknowledgment CSV that accepts one row and rejects another. Retain the original bytes and distinguish file receipt from row disposition.
4. Correlate response rows using declared exchange/native row identifiers. Ambiguous or absent keys remain unresolved. A clinician match alone cannot select an office.
5. Inspect selected enrollment/organization evidence and later directory observations. Acknowledgment does not establish directory publication, credentialing, commercial participation or billability.
6. Request bounded research on one unresolved case. Compare retained evidence, perform explicitly permitted source reads, and return supported/contradicted/unresolved findings with citations.
7. Review a correction proposal and export the recipient-specific packet, complete source/decision lineage and outstanding questions. SOUTH remains distinct; repeat/restart cannot duplicate outcomes or replace an approved dataset.

Use fictional parties and hand-authored adversarial fixtures for committed examples. Actual-source observations and operator studies are separate evidence. Payment/claims investigation and regional pricing analytics remain separate product directions.

## Reuse and actual gaps

| Existing responsibility | Reuse | Proposed extension |
|---|---|---|
| IntakeStore/artifacts/receipts/attempts | Exact bytes, locators, interpretation revisions, acceptance | Explicit response/enrollment profiles with their native grains |
| OnboardingService/recipes/model mapping | Editable declarative proposals, deterministic preview, separate approval | Compatibility report and reviewed profile selection for additional declared schemas |
| IdentityReview/FieldReconciliation/change-impact | Clinician/location crosswalks, source-scoped values and retained dependencies | Source-native enrollment/reassignment relationships without universal identity merging |
| ManagedFeed/acquisition workers | Claimed durable work, budgets, retry/failure retention, restart | Explicit research task lifecycle through shared services and registered connectors |
| Follow-up/investigation/export | Append-only local actions and scoped packets | External response correlation and pinned recipient exchange; internal acknowledgments retain their existing meaning |
| Web workspaces and SQL runner | Source/version context, read-only lineage and review | Case research panel, response disposition review and bounded operational questions |

`follow_up_acknowledgement` currently acknowledges an internal association. It must not be relabeled as a payer acknowledgment or migrated into one. Existing local submission events are not evidence of external delivery.

## Three bounded operating modes

### Intake adaptation

Inspect declared container/media type, worksheet/header/envelope and source shape. Return recognized profile/version, unsupported fields, missing keys and ambiguity. An existing model can propose a mapping from retained samples into an allowlisted profile. Validate it deterministically and require ordinary preview/approval/acceptance.

Adaptation produces versioned data configuration, never executable parser code. A new source family needs a reviewed parser and native semantics. Unknown input stays inspectable and unsupported; it is not forced into clinic rows. Native FHIR and relational enrollment resources keep separate rules. Schema drift creates a new compatibility report/attempt and cannot reinterpret old approved versions.

### Selected-case research

The operator supplies an exact question, case/version and allowed source set. A lead research run pins those inputs and may allocate up to two nonrecursive tasks: retained-evidence comparison and source verification. A single task is sufficient when delegation adds no value. This product execution uses configured model/tool providers and service contracts; it does not depend on a developer chat session or its credentials.

Initial proposed limits: one case, two tasks, six total network requests, twenty returned resources, 2 MiB total network response bytes, three model calls, 120 seconds of active wall time and a $0.50 conservative reservation per run. Effective limits are the tighter of run bounds and connector bounds. Redirects, references, retries and failed responses consume budgets. Uncertain provider-call outcomes retain the reservation. Provider-side accounting is not an invoice guarantee. Freeze actual supported configuration before live evaluation.

Tasks use only registered HTTPS connectors or retained evidence IDs. Connector registration is a proposed explicit dispatcher/configuration contract, not an existing generic framework: each source owns a fixed destination, typed query schema, response limits and parser. The current fixed HAP acquisition cannot be repurposed as an arbitrary HTTP client. No recursive delegation, arbitrary browsing, filesystem access, outbound contact or approval tool is exposed. Source text is untrusted data. External processing requires explicit source permission and bounded samples; retained sensitive fields are not automatically eligible for transmission.

Persist request, context snapshot, budget reservation, tool attempts, exact response artifacts, findings and terminal state. States distinguish queued/running/partial/completed/failed/cancelled/unavailable. Recheck the pinned case and evidence versions before publishing a current result. Cancellation or stale inputs fence late publication. Unknown external outcomes cannot trigger automatic repeated model calls. Retained successful responses can be reinterpreted after restart without refetching, labeled as replay.

Each finding declares subject kind/reference, predicate, value or unknown, supporting and contradicting evidence IDs/locators, source/retrieval dates, parser/model version and limits. A model's stated confidence is not calibrated accuracy. Every factual finding must resolve to retained evidence. Uncited interpretation is visibly a hypothesis. The UI shows partial/unsupported scope and original context. Research can create a reviewed proposal, not change identity links, approve datasets, verify a listing or assert participation.

### Exchange review

The operator inspects an exchange, response and recipient-specific correction packet. Keep prepared, locally asserted sent, file acknowledged, row accepted/rejected and directory observed as separate facts. Contradictory responses coexist; a documented selection/disposition resolves the working view without deleting evidence. Packet generation cannot imply that a payer accepted its contents.

## Sources and standards

Sources below were researched on 2026-11-19. Documentation availability establishes a candidate contract, not permission for unrestricted automation or successful live integration.

| Source | Useful information | Acquisition and initial decision |
|---|---|---|
| NPPES API and Version 2 files | NPI/type, names, practice locations, source updates | Keep bounded API support; evaluate supplied V2 files and their auxiliary location/name data. Bulk/incremental processing is a separate bounded contract, not a national crawl. [CMS files](https://download.cms.gov/nppes/NPI_Files.html) |
| CMS Public Provider Enrollment Files | Enrollment identifiers, reassignments, location city/state/ZIP, specialty and additional NPIs | Priority new relational profile. Preserve each source snapshot and enrollment key. It is Medicare evidence, not proof of a commercial-plan contract or an exact street-level office match. [Methodology](https://data.cms.gov/resources/fee-for-service-public-provider-enrollment-methodology-q1-2026), [dictionary](https://data.cms.gov/resources/medicare-fee-for-service-public-provider-enrollment-data-dictionary) |
| Existing CMS Doctors/Clinicians and fixed payer capture | Source-native enrollment/address and directory relationships | Extend documented field coverage only for an acceptance case; preserve partial scope and existing source bounds. |
| Tennessee licensing verification | Named professional license evidence | Interactive site currently presents CAPTCHA. Use a permitted supplied report/manual observation unless an authorized machine-access route is established. Do not automate around the challenge. [Official site](https://internet.health.tn.gov/Licensure/) |
| OIG LEIE | Exclusion candidates and update history | Later, separate review profile. Matching names is insufficient to conclude identity; keep candidates unresolved where needed. [OIG instructions](https://oig.hhs.gov/exclusions/leie-quick-tips-instructions/) |
| Practice-owned website | A displayed office contact or location assertion | One named, explicitly permitted HTML connector if needed. Retain page bytes, URL, field locator and observation time; a displayed insurance name is not verified participation. No general web crawler. |
| Supplied payer response/template | Delivery/file receipt and recipient row dispositions | Initial exchange profile uses synthetic supplied CSV plus versioned recipient mapping. Actual recipient semantics require sample/schema review. |

Continue targeting FHIR R4 4.0.1 / Da Vinci Plan-Net 1.2.0 for the declared directory-consumer subset. Preserve advertised source guide versions separately. PractitionerRole associates practitioner, organization, locations and network context; ambiguity/cardinality remains visible. No broad FHIR conformance claim follows from sample validation. [HL7 implementation guide](https://hl7.org/fhir/us/davinci-pdex-plan-net/STU1.2/implementation.html).

X12 274 is a relevant provider-information transaction to investigate when a named partner supplies a required version/implementation guide and appropriate access. It is not an initial supported format or a synonym for every payer roster. X12 837/835 belong to future claims/remittance work, not this directory exchange slice. [X12 274](https://x12.org/node/4252).

Use JSON Schema-style strict typed outputs for tool/profile boundaries, tested CSV/XLSX semantics, stable source keys, UTC retrieval timestamps and original effective dates. Version every adapter/recipe. No additional standard is adopted solely to lengthen the supported-formats list.

## Linked SQL model

Retain SQLite and existing transactional services. A linked model means foreign keys, source-native relationships, immutable evidence and useful joins; it does not require a graph database or PostgreSQL migration. Existing observation, identity, network, case and event tables remain authoritative for their current meanings.

Candidate additive relations, to freeze at each implementation slice:

| Relation | Grain and links |
|---|---|
| enrollment_snapshot | One retained source release/import, linked to receipt/artifact/attempt and version/completeness metadata |
| enrollment_record | One `(snapshot_id, native_enrollment_id)`; source NPI/PAC and entity type remain assertions |
| enrollment_reassignment | One source reassignment pair within a snapshot, referencing both enrollment records when resolved |
| enrollment_practice_location | One source enrollment/location tuple; coarse locations must not become exact reviewed office links |
| provider_exchange | One pinned prepared packet, recipient profile/revision, original delivery and export digest; local sent assertion separately recorded |
| provider_exchange_item | One exchange-native row key linked to its retained observation and current reviewed clinician/office references, if established |
| exchange_response_item | One retained response row/interpretation with locator, disposition/reason and explicit correlation to an exchange item or unresolved status |
| research_run / research_task / research_event | Pinned case/evidence context, finite task allocation, reserved/consumed budgets, append-only execution history and versioned results |
| research_finding_evidence | Finding-to-existing-observation/artifact/locator links, including contradictions and unsupported scope |

Do not store a second canonical provider record in the research tables. Resolve findings through existing retained observations and reviewed links. Composite source/snapshot keys prevent cross-release joins. Missing referenced enrollment rows remain retained unresolved evidence, not silently dropped or fabricated identities. Use foreign keys for resolved references, explicit unresolved status, indexes on selected joins and expected-version checks for actions.

Add read-only questions over a single snapshot: unresolved response rows by reason; exchange items awaiting recipient acknowledgment; case findings by supporting/contradicting source; source enrollment/reassignment relationships; and stale research results. Counts declare row/clinician/office grain. "Candidate change", "acknowledged" and "observed corrected" have separate denominators. No revenue/savings estimate without observed financial evidence.

## Acceptance and evaluation

| ID | Required outcome |
|---|---|
| PX-A1 | File acknowledgment and row disposition stay separate; wrong/missing delivery keys cannot attach to another exchange. |
| PX-A2 | Repeat, reordered, contradictory and stale responses preserve history; exact retry is idempotent; no automatic dataset promotion. |
| PX-A3 | Typed graph joins preserve source snapshot, enrollment pair and office ambiguity. Equal NPI never collapses multiple enrollments/offices. |
| PX-A4 | Unknown adapter/envelope, header drift and ambiguous mappings are visible; approved historical versions remain unchanged. |
| PX-A5 | Research request/reference/byte/time/cost bounds cover all tasks; cancellation/restart/late results cannot bypass limits or replay uncertain calls. |
| PX-A6 | Instruction-like source content cannot grant tools or change scope; citations resolve to retained evidence; contradiction/abstention remains visible. |
| PX-A7 | Exported recipient packet pins input/decision/profile versions, excludes unrelated offices, retains unknowns and reproduces after restart. |
| PX-A8 | One connected UI journey and inspected JSON/XLSX/CSV outputs agree with independent expected values and read-only SQL views. |

Freeze a held-out corpus before model trials: previously unseen headers/acknowledgments, shared phones, two offices, swapped IDs, coarse enrollment locations, source errors, irrelevant text, contradictory dates and missing evidence. Compare deterministic profile/matching rules with assistance. Report wrong links, missed links, correct abstentions, unsupported claims, reviewer corrections, run cost/latency and denominators. Inject controlled failures independently of the model. Actual calls, controlled transports, synthetic labels and human observations are separate receipts.

The first slice does not require model access. External model usefulness and human H1/H2 tasks remain independent open evidence. Run required repository checks for affected code/UI; inspect real serialized packet contents. Preserve source artifacts and failed runs. No migration or live database experiment is part of this design document.

## Delivery order

The historical PX sequence below describes dependencies within the later exchange work; it is not the active roadmap. PX0 freezes the [v1 exchange/source/research contract](PROVIDER_OPERATIONS_CONTRACT.md) and challenge fixtures. UI1 then rebuilds the shell and receive/delivery/work-queue journey under the [operator contract](OPERATOR_EXPERIENCE.md), preserving guarded actions and evidence before extending the UI. PX1 creates a minimal pinned exchange manifest from an existing approved two-office export, then implements one supplied acknowledgment CSV through preview, explicit correlation and inspected scoped export. This manifest supplies stable outbound row keys before later recipient-specific template generation. PX2 adds the CMS enrollment relational profile and read-only linked views. PX3 adds selected-case research using registered sources and then evaluates actual model calls when configured. PX4 adds one recipient-specific correction template and read-only operator views under the [separate measure contract](OPERATIONAL_MEASURES.md). PX5 qualifies the complete journey, recovery and model/human evidence within their observed scope.

Broader sources, OCR/PDF email attachments, autonomous outreach, payer writeback, universal adapter generation, hosted teams and additional databases remain separate decisions. Revisit architecture only when an observed workflow or workload requires it.
