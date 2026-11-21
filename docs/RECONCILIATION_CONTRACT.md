# Reconciliation and change impact contracts

Current product direction is owned by [SPEC](../SPEC.md) and [ROADMAP](../ROADMAP.md). The historical R/I identifiers below describe the implemented baseline. Planned D1 multi-resource evidence extends the retained-reference boundary through [the FHIR contract](FHIR_INTAKE_CONTRACT.md) and [C3 in ARCHITECTURE](ARCHITECTURE.md); it is not implemented by this note. Update this contract with actual projection/snapshot changes in D1.2, preserving existing source-row behavior.

R0 contracts/fixtures, R1–R4 reconciliation and I1–I2 typed proposals/impact/confirmed follow-up are available locally at schema10; RI1 combined qualification is complete locally; receipt (historical reference retained separately). Current milestone gates are in [ROADMAP](../ROADMAP.md). The implemented comparison boundary is described below; confirmed follow-up contracts are implemented as described below. Source onboarding recipes and provenance remain independently usable. No matching score, equal NPI or shared address authorizes an automatic identity link.

## Source record and address references

A retained input reference is `(attempt_id, locator, address_path)`. `attempt_id` pins an immutable interpretation and its artifact/recipe evidence. `locator` identifies an exact retained row/resource, not a business entity. `address_path` is empty for a flat single-office row and an explicit native practice-address path for a multi-address record. Mailing addresses cannot become operating locations. Duplicate native keys remain separate retained references until reviewed; a missing native key cannot be carried automatically to later deliveries.

Candidate inputs select explicit receipt/attempts and retain their source namespace, profile and dataset/network scope. Comparisons use only those inputs. A source record may be quarantined and still supply review evidence; approving a link neither accepts it nor creates participation. Clinician, organization, practice location and payer-network identity remain distinct. File inputs with no entity-type evidence stay unknown or require an explicit source declaration; names alone do not establish person-versus-organization type.

## Versioned comparison values

The normalization recipe/result provides retained original values, comparison values, transformation version and findings. Add address-component comparison without discarding unit/suite, ZIP+4, extensions or unknown values. Display values and preferred values are separate decisions. Identifier shape is structural evidence, not certification. Existing accepted interpretations are never rewritten when comparison rules improve.

## Persistent records

Schema 6 adds observation comparison evidence, immutable comparison runs and candidates. Schema7 adds clinicians and reviewed decisions/links. Schema8 adds field decisions. Schema9 adds immutable change proposals with derived read-only impact. Schema10 adds immutable confirmed assessments/action plans, individually scoped work associations and independent receipt acknowledgements.

| Record | Identity and required content |
| --- | --- |
| Clinician | Opaque local ID, label, asserted identifiers, actor/reason/time; no replacement of existing NPI-derived provider/work keys. |
| Match run | Opaque ID, selected immutable inputs, comparison-rule version, source baseline/link/catalog revision snapshot and measured execution scope. |
| Candidate | Run ID, typed clinician/location pair of retained references, deterministic ordering, agreements, contradictions, missing evidence and rule ranking. Ranking is not a probability. |
| Reviewed link revision | Exact retained reference, clinician or existing practice-location target, previous revision, approve/reject/defer decision and actor/reason/time. Each type has an independent revision chain. |
| Reconciled field decision | Clinician or clinician/location scope, field, pinned source/link/rule snapshot, selected source reference or explicit retained conflict, previous decision and actor/reason/time. |
| Change proposal and assessment | Explicit typed identity/location/field, proposed value and prior value evidence; immutable dependency snapshot, reasons and coverage categories. |
| Follow-up association | Proposal revision, assessment revision, exact target/field and durable work-case reference, with a uniqueness constraint for retry-safe confirmation. |

Existing practice-location catalog IDs are reused only through explicit reviewed links. Candidate generation does not create identities, links, field selections or cases. Selecting a clinician target never implies a location target. Shared offices may host several clinicians; one clinician may occupy several offices.

## Freshness and transactions

Runs and decisions pin selected attempt fingerprints, explicitly assessed source baselines and relevant link/catalog revisions. A new interpretation of a selected receipt, later accepted delivery in the assessed source/dataset scope, or revised relevant link makes dependent previews stale. Old snapshots and review history remain readable. A stale preview cannot approve a link, select a field or confirm follow-up without renewed review.

Approval and confirmation use `BEGIN IMMEDIATE`, recheck expected versions inside the transaction and append decisions atomically. Repeating the same approval returns its existing decision; contradictory retries require a new reviewed revision. Rejection/defer decisions remain visible when new runs are created. Transitive candidate chains do not become links automatically.

## Reconciliation and impact scope

Provider names are clinician-scoped; phones and coherent address components are practice-location-scoped. The reconciled view includes only explicitly approved typed links and retains each source assertion independently. Source precedence is field-specific and reviewed; the newest delivery does not automatically win. Selected field values keep source evidence and decision provenance; unresolved fields remain conflicts.

A change-impact preview traverses known approved links, selected retained listings and existing work. It returns affected, unaffected-within-assessed-scope and not-assessed counts with reasons. A NORTH phone change must exclude SOUTH and distinguish named payer networks. Unlinked/ambiguous records remain not assessed; coverage is never described as complete when dependencies are unknown.

Preview is read-only. Explicit confirmation can create/associate follow-up work atomically and idempotently without replacing existing owners, status or initial evidence. No source assertion, external directory or old downloaded file is updated. Acknowledgement and verification remain separate assertions.

## Implemented and planned API boundary

Run creation/detail/candidate routes are implemented at schema 6. Schema7 implements link review and typed identity reads; Schema8 implements field decisions and scoped exports; Schema9 implements change-proposal and impact-preview routes; Schema10 implements read-only follow-up planning, explicit confirmation, receipt/history/acknowledgement and pinned complete plan exports. The exact implemented request/response boundary is documented in API_REFERENCE.md. They use the existing typed error convention: invalid input 422, unknown IDs 404, stale expected state 409. Read pages have bounded samples, complete counts and cursors. Exports preserve complete selected evidence and literal spreadsheet values.

| Operation | Contract |
| --- | --- |
| POST `/api/reconciliation/runs` | `inputs` selects explicit receipt/attempt IDs and any operator-declared entity kind; records immutable run inputs/rule version and candidate output. Repeating pinned inputs/rules preserves candidate ordering, while each requested run retains its own receipt. |
| GET `/api/reconciliation/runs/{id}` | Run metadata, input references/freshness and typed candidate summary. |
| GET `/api/reconciliation/runs/{id}/candidates` | Implemented filters are clinician/location kind, eligible flag, reason and search, with offset and limit; agreements, contradictions and missing evidence remain separate. |
| POST `/api/reconciliation/links` | Explicit run/candidate/ref, approve/reject/defer, target identity or new reviewed identity label, expected prior link revision, expected run snapshot, actor and reason. Recheck under one transaction; return immutable revision. |
| GET `/api/reconciliation/identities/{kind}/{id}` | Implemented typed identity/current source assertions and link history/freshness; field revisions/preferences are available through the separate scoped fields route. |
| POST `/api/reconciliation/field-decisions` | Typed identity/location/field, selected retained reference or explicit unresolved conflict, expected snapshot/prior decision, actor/reason. Selection never changes a source observation. |
| POST `/api/reconciliation/change-proposals` | Immutable scoped field proposal, proposed value, prior evidence, actor/reason and expected reconciliation snapshot. |
| POST `/api/reconciliation/impact-preview` | Read-only proposal assessment returning pinned snapshot, affected/unaffected/not-assessed targets and reasons; creates no work or decision rows. |
| POST `/api/reconciliation/follow-up` | Proposal ID, exact preview snapshot, actor/reason and explicit confirmation. Recompute/check scope, persist confirmed assessment and create/associate work atomically; uniqueness makes retries idempotent. |
| GET `/api/reconciliation/identities/{id}/export` | Explicit location/snapshot/format selection for JSON/XLSX, retaining source locators and decision history; read-only. |

Example retained reference: `{"attempt_id":"ATTEMPT","locator":"$.results[0]","address_path":"addresses[1]"}`. Example field scope: `{"clinician_id":"OPAQUE_ID","location_id":"REVIEWED_LOCATION_ID","field":"phone"}`. Namespaced IDs and existing native keys are not interchangeable.

## Challenge and qualification acceptance

Hand-authored [challenge fixtures](../tests/fixtures/onboarding/reconciliation_challenge.json) and a separately authored held-out fixture define expected clinician links, location links, unresolved cases and impact targets before implementation. Include contradictory identifiers, organization/person distinctions, shared addresses, different suites, missing keys, ambiguous names and multiple native addresses. Structural fixture tests verify labels and references; they do not establish matching quality.

R2 must report proposed true links, missed true links, incorrect proposals, candidate volume and execution cost on declared inputs. Later qualification adds an independently labeled approximately 1,000-row three-source corpus, held-out evaluation, known-scope impact precision/recall and not-assessed coverage. Synthetic results do not establish production accuracy.

Every implementation gate includes its user-facing behavior, API contracts and meaningful tests. Rehearse populated schema-5 migration, injected-failure rollback, repeat/restart, source/artifact preservation, stale decisions, cross-scope isolation and non-mutating JSON/XLSX exports. The combined browser demonstration must exercise three sources, reviewed links, a location-specific phone proposal, explicit follow-up and inspected outputs. Public publication remains a separate privacy/adoption gate.

Additional implemented read routes: `GET /api/intakes/{id}/comparison-profile` (required expected attempt), `GET /api/reconciliation/runs` and `GET /api/reconciliation/runs/{id}/export`. Interactive samples are bounded; the JSON attachment retains complete pinned records/candidates. Export is comparison evidence, not a reconciled or verified directory.

Schema-7 review refinement: pair rejection/deferral does not remove an existing approved link. Approval explicitly appends both typed retained-reference revisions to a selected/new target. Unknown/incompatible entity type or address purpose must be resolved before approval; other same-type evidence conflicts can be manually reviewed. Selected-attempt state, including later rejection, participates in freshness. Review/target/identity read pages expose complete totals and bounded samples.

Schema8 refinement: field names/NPI are clinician-only; phone/extension and coherent address blocks require both current clinician and exact-location links. Separate evidence/view snapshots preserve preference staleness independently of another field decision while pinning exports to the observed review state. Full selected JSON/XLSX handoffs retain source context, historical field evidence and approved link provenance. See API_REFERENCE.md for implemented routes.

I1 refinement: explicit retained source selection bounds the assessed scope; clinician fields deduplicate to retained row grain while location fields retain exact native-address grain. Selected receipt/attempt and reused accepted-observation attempt stay distinct. Preview is derived/read-only, with separate listing/work counts and snapshot-sensitive existing work versions. I2 confirmation persists its complete frozen assessment and work associations without accepting or certifying source facts.

## Confirmed target and acknowledgement boundary (I2)

Unique explicit flat record IDs or NPPES numbers identify follow-up targets only within exact source/profile/query/comparison/network/source-location and reviewed clinician/location/field scope. Missing/duplicate IDs and CMS use exact retained references. All contributing refs survive grouping. New QA work references retained evidence without creating accepted observations or participation. Existing eligible open work is associated unchanged; ambiguous open matches require a choice, and closed work is not reopened.

Confirmation pins impact and action-plan snapshots, saves the full frozen assessment/plan and appends all associations atomically. One confirmation per proposal and exact-content/intent hashes prevent duplicate confirmation across retries/restarts; changed intent needs a proposal revision. Acknowledgements form a separate immutable expected-version chain and never close, assign or verify work. Current receipt/export snapshots include current case versions, source state and acknowledgement IDs separately from frozen confirmation intent. Work queue/details/selected exports expose follow-up scope independently from participation. See I2 evidence (historical reference retained separately).

## Evidence-reason review views

Saved-run candidates can be filtered by a recorded evidence code with complete type/eligibility/search reason counts. The result grain remains one typed pair; reason-array fan-out cannot duplicate pairs or inflate a code's count. Distinct codes may overlap. Filtering/paging is a read-only view over the same immutable candidate evidence and does not change rule version, eligibility or reviewed links. Missing NPI and conflicting NPI remain separate operator questions, with current identity safeguards preserved. A separate filtered JSON handoff contains all selected pairs and their retained comparison records, with explicit scope and no paging truncation; the complete-run export remains separate. See the triage qualification (historical reference retained separately).
