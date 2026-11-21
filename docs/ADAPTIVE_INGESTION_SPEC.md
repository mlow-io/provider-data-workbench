# Adaptive ingestion and contact-review specification

Revision **S1.1 — selected implementation boundary, 2026-11-21**. Owner-selected direction; detailed source, UI and durable-interface decisions remain open. The owner authorized implementation on 2026-11-21. The bounded first implementation uses the existing roster authority and services, a Tennessee-filtered NPPES reference sample, reviewed mapping reuse and a pinned workbook. Detailed added interfaces are frozen in their area contracts before code. This is a product contract, not an API/schema migration or completion receipt. [SPEC](../SPEC.md) owns global invariants; [ROADMAP](../ROADMAP.md) owns sequence; [NEXT](../NEXT.md) is the executable brief.

## Product objective

Turn heterogeneous provider files and retained source evidence into versioned, reviewable provider data. An operator can understand unfamiliar layouts, reuse approved mappings, compare deliveries, investigate office contact disagreements and export usable results without erasing original evidence or previous decisions. Optional model/API or external-agent assistance helps propose mappings and profile revisions. The longer-term domain includes licensing and provider/office/payer/product/network relationships.

The primary user is a provider-data operator. The first working environment is the existing single-user local application. The first integration is Tennessee-focused; statewide completeness, current appointment availability and verified insurance acceptance are not implied. A future public explorer consumes an approved export/API; it is not the initial operator interface.

## Release boundary and import breadth

Separate transport (upload, retained HTTP response), syntax (CSV, XLSX, JSON, FHIR Bundle), source semantics (roster, registry, directory, license, enrollment), and interpretation recipe. A new column layout is not necessarily a new parser. A readable file is not necessarily a valid provider roster.

S1.1 should freeze this candidate qualification matrix after checking existing support:

| Candidate case | Required exercise | Boundary |
|---|---|---|
| Clinic CSV layout A | Text identifiers, missing values, repeated delivery and contact change | Supplied synthetic roster; operator-selected meaning |
| Clinic XLSX layout B | Explicit worksheet/header selection, different headings and reviewable cleaning | Same domain through a genuinely different layout; preserve originals |
| Declared JSON reference profile | Retained native keys, nested/repeated address semantics within supported profile | Do not flatten arbitrary JSON or generate clinician-office cross-products |
| Existing FHIR subset | Practitioner/Organization/Location/PractitionerRole evidence and unresolved references | Preserve existing profile/version and unsupported-resource limits |
| One named Tennessee-relevant source | Actual sample, source permission/access note, contact/address purpose, dated coverage and replay | Prefer reuse of a working adapter; no assumed licensing-to-office equivalence |
| Drift/unsupported challenge | Renamed header, ambiguous binding, missing key, unknown structure and partial capture | Hold or abstain with a reason; never silently force a mapping |

This matrix is a proposed validation breadth, not six new adapters. P0 inventories what already works. Commit synthetic equivalents; keep real samples outside Git. A known inaccessible source remains a named open gate. An explicitly selected accessible alternative requires an updated source decision; synthetic replay must not be represented as live qualification.

## Bounded source shortlist for P0

These are research leads, not newly qualified integrations. Verify current access, actual response and field meaning before selection. The Tennessee-specific goal can be met by a Tennessee subset of a national registry, but must be labeled accordingly; it is not a state licensing or payer-participation dataset.

| Candidate | Starting reference | Decision to establish |
|---|---|---|
| NPPES Tennessee subset | [NPI Registry API](https://npiregistry.cms.hhs.gov/api-page) and existing NPPES adapter | Does the supported response expose usable practice-address/contact evidence with explicit query limits and multiple-address handling? |
| BCBST directory evidence | [BCBST developer resources](https://www.bcbst.com/developer-resources) | Can a bounded provider-directory response be obtained through an authorized route, and do its office links/profile semantics fit the existing FHIR subset? |
| Tennessee licensing report | [Health Professional Licensing Reports](https://internet.health.tn.gov/LicensureReports) | Inspect actual report shape and address purpose. Prefer S2 if it supports licensing evidence but not office-contact comparison. |

Default P0 remote investigation budget: at most three candidates, ten total HTTP requests including redirects/retries, 10 MiB cumulative returned content, and a retained data sample of at most 200 records. Use smaller source limits when required. No bulk national download, automated pagination crawl or model call. If a report requires a larger transfer or unavailable interaction, record the blocker and propose a bounded alternative rather than claiming access or silently expanding the budget.

## One complete operator journey

1. Open a labeled prepared example or choose a supplied delivery. Show source, scope and current approved version.
2. Inspect the file shape and compatibility report. Select the worksheet/profile explicitly when ambiguous. Failed reads, empty results and unsupported inputs have different states.
3. Reuse an approved recipe, manually edit a proposed mapping, or request optional assistance. Preview original and interpreted values, transformations, findings and affected row counts before approval.
4. Approve a recipe revision and apply it to a new interpretation. Review source acceptance and dataset eligibility separately. A schema change cannot rewrite an earlier approved interpretation.
5. Compare office contacts within established clinician/office links. Unknown associations remain unresolved. Show source address purpose, field values, source/effective/retrieval dates and supporting locators.
6. Record a reasoned decision: retain the current value, approve a proposed value for the appropriate existing workflow, or leave unresolved. Editing a roster is not proof that a payer directory changed. Preserve the existing proposal/submission/observation distinctions.
7. Preview export scope and counts. Export the chosen approved roster plus unresolved issues and evidence references. No pending proposal silently enters the approved roster.
8. Import the next delivery, inspect changes, repeat an earlier delivery, and restart. Preserve previous decisions and original bytes; surface stale decisions rather than silently applying them to new evidence.

## Internal data model and ownership

Reuse current receipts, artifacts, attempts, recipes, observations, reviewed links and managed approvals. The conceptual model distinguishes source profiles, recipe revisions and evidence from domain identities and decisions. Do not create parallel stores for the same facts.

A proposed source-profile revision records: stable namespace and version; supported container and source kind; one-record meaning; native key and identifier systems; relationship/cardinality rules; field meaning and address/contact purpose; supported operations; required/optional fields; unknown handling; limits and coverage; parser/configuration version; compatibility findings; origin and approval history. A recipe maps a specific input shape to that declared meaning. A new profile is not an unreviewed relaxation of required fields.

P0 must decide whether the existing registry/recipe relations can represent these concepts or require additive persistence. Freeze exact service shapes and a migration/backfill/recovery decision before P2 coding. Conceptual fields here do not authorize speculative tables.

Clinician, organization, office, license, payer, product and network are separate domain concepts. S1 implements only the additions required by its selected sources; preserve the ability to represent later relationships without prematurely building the entire network model. A license or enrollment row may provide reference evidence without establishing an exact practice location.

## Adaptation and learning contract

Recognize supported input or return unknown/ambiguous; never select a profile solely to obtain a successful parse. Drift produces a new compatibility report and proposed interpretation with pinned input/profile/recipe versions. Retain unknown fields as source evidence without silently making them business fields.

Learning means retrieving approved profile/recipe examples and recorded reviewer corrections. Scope reuse by source family, semantics and compatible version, not merely similar column labels. Rejected, unreviewed or source-injected content cannot become trusted examples. Revoked/superseded examples remain historical and are excluded from new recommendations under an explicit policy.

Reuse the existing OnboardingService, MappingAssistant and MCP service boundary. A configured model API and an external agent must return the same validated proposal representation while retaining distinct provenance. Model proposals cannot approve recipes, accept sources, merge identities or promote datasets. Manual and deterministic paths remain usable.

Runtime extension produces declarative bindings and allowlisted transformations. A genuinely new parser is a developer-authored or agent-proposed code change, reviewed and tested through normal development before registration; runtime cannot install or execute generated code. Parser-generation assistance is later work, not an S1 runtime feature.

Before P3, freeze sample permission, redaction, prompt/result schemas, retrieval policy, model/provider config, request/time/token/cost limits, cancellation, stale-input rejection and uncertain-call retry policy. Preserve the prior A1/A3 corpus; new capabilities receive a separate versioned evaluation. Use independent expected mappings, output values, abstentions and invalid-operation cases. Actual-model results, controlled-provider tests and observed human effort are different evidence. Do not tune expected answers after trials.

## Output contract

Primary planned output: a review workbook with **Directory**, **Unresolved issues**, and **Sources and export details** worksheets. The Directory represents a pinned approved version; unresolved issues may refer to records still present with their previously approved value. Cross-sheet clinician/office/issue identifiers and version/scope metadata make that relationship explicit. Preserve text identifiers, unknown values and safe spreadsheet cell serialization.

Retain existing machine-readable evidence exports. S1.1 must define exact column names/types, row grain, completeness/count rules, selection behavior, snapshot consistency, ordering, timezone representation and source-locator resolution. The workbook is a review deliverable, not an arbitrary payer's upload template. Recipient-specific exports require a named specification/version and their later acceptance gate. A locally approved value is not an externally verified contact or participation claim.

## Stable acceptance scenarios

| ID | Observable requirement | Evidence to plan before coding |
|---|---|---|
| AI-01 | Different supported CSV/XLSX layouts produce the independently expected values and preserve text/unknown semantics | Authored fixtures and expected interpreted rows; actual output inspection |
| AI-02 | JSON/FHIR retain native keys, address purpose and relationships; unsupported/ambiguous shapes stay visible | Multi-office and unresolved-reference fixtures; no cross-product joins |
| AI-03 | A named Tennessee source has inspectable provenance, coverage and field meaning | Private actual sample receipt plus synthetic replay; record unavailable gates honestly |
| AI-04 | Approved mappings can be reused; drift creates a new version without reinterpreting history | Changed-header/meaning fixtures, before/after history and approved-export checks |
| AI-05 | Model/API and external-agent proposals use validated review boundaries; malformed, stale or adversarial proposals change no approved state | Controlled negative cases, manual fallback; separate actual-model evaluation |
| AI-06 | Two offices sharing one clinician cannot receive one another's contact decisions | Independent link/field expectations, uncertainty handling and stale-write check |
| AI-07 | Repeated delivery and restart preserve approved data, original evidence and decisions without duplicate logical results | Repeat/new-delivery identity cases, restart and inspected persisted history |
| AI-08 | Workbook and evidence export agree with the selected approved snapshot, unresolved scope and displayed totals | Inspect actual cells/JSON, cross-sheet references, identifiers and formula-like text |
| AI-09 | A populated import-to-export journey is understandable and operable at desktop/narrow widths | Running screenshots, keyboard/focus/error checks, separately recorded owner review |
| AI-10 | New processing failure or held candidate leaves the prior approved output usable | Failure/recovery rehearsal and independent downstream reader |

These are target requirements. P0 maps each to existing coverage, a concrete gap and planned verification. Do not label an acceptance ID passed from a design statement or merely from a test count.

## Decisions required for S1.1

| Decision | Recommended starting point | How to resolve |
|---|---|---|
| Tennessee contact evidence | One accessible registry/payer source with explicit office/contact meaning | Inspect actual sample and existing adapter; licensing only if semantics support the task |
| Baseline authority | Practice roster is an explicitly chosen working baseline; other sources are competing evidence | Specify first-import and subsequent-approval behavior with the owner |
| Breadth | Candidate matrix above, reusing existing parsers | Inspect supported limits and qualify multiple layouts; enumerate exclusions |
| Profile persistence | Extend current versioned recipe/registry model | Identify exact gaps and freeze service/storage contract without duplicate canonical state |
| UI system | React/TypeScript/Vite, existing TanStack Query/Table, shadcn/ui candidate | Record compatibility and maintenance decision; owner reviews populated visual proposal |
| Approval/export behavior | Explicit field decisions and pinned dataset/workbook snapshot | Resolve how existing field decisions feed a candidate dataset; never infer propagation |
| Adaptive invocation | Existing model client and MCP adapter through shared services | Freeze retrieval/proposal interface and limits before P3; credentials never inferred |

## Revision discipline

S1.0 captured direction. S1.1 freezes the source matrix, user flow, design proposal and planned interfaces after P0 review. S1.2 freezes the adaptive invocation/evaluation contract before P3. S1.3 freezes integrated release/export/demo acceptance before P4. Minor clarifications preserve IDs; changed semantics require a dated delta, affected tests/data assessment and explicit selection before implementation.

Later S2 licensing/identity, S3 networks and S4 research/exchange are roadmap goals. Draft their detailed contracts at the preceding revision gate; do not execute speculative migrations for them now. Record owner decisions in DECISIONS, implementation evidence in STATUS, and exactly one active task in NEXT.

## Selected S1.1 decisions

- Existing approved clinic dataset remains the working roster; external reference assertions cannot replace it automatically. Field decisions do not implicitly promote a new dataset.
- First Tennessee evidence is a bounded NPPES API 2.1 Nashville/TN subset. A private three-record actual capture succeeded on 2026-11-21; six addresses included LOCATION and MAILING purposes. This is registry evidence, not state licensure or network acceptance. Synthetic samples remain committed examples.
- Reuse existing profile/recipe records and their approval history. Compatibility and reuse are bounded shared-service operations; missing mapped columns block reuse. No new database server or duplicate registry.
- Preserve the existing React/TanStack runtime. Deliver consistent evidence tables and controls with shared CSS/component boundaries for this slice; introducing shadcn is deferred to a separately validated dependency migration if needed. No component library alone establishes visual acceptance.
- Review workbook reads a pinned approved version in a consistent read snapshot. It never applies contact proposals. Existing approval and verification stages remain authoritative.
- Optional actual-model and participant evidence remain independent open gates. A model transport is not invoked merely to claim completed adaptation quality.

## S1.3 selected correction-release delta — 2026-11-21

After UI qualification, the owner selected the complete reviewed-office-phone → candidate roster → separate dataset approval → pinned JSON/XLSX journey. [The materialization contract](FIELD_MATERIALIZATION_SPEC.md) freezes scope and failure semantics; [review format 2](REVIEW_WORKBOOK_CONTRACT.md) freezes extension/provenance output. Bulk and address corrections, licensing and network reconciliation remain later revisions. Existing AI-04/08/09 acceptance IDs cover decision preservation, inspected output and connected usability; the dated correction receipt records checks without substituting for participant evidence.

The earlier shadcn deferral above is historical: the component-system migration and 100/1,000-record qualification are implemented; see STATUS. No new framework or dependency is selected by S1.3.
