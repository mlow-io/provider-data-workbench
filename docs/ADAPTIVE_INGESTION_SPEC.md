# Adaptive ingestion and contact-review specification

S1.1 and the S1.3 correction delta define the bounded adaptive intake and contact-review contract selected on 2026-11-21. The implementation uses existing roster authority, a Tennessee-filtered NPPES reference sample, reviewed mapping reuse and a pinned workbook. [STATUS](../STATUS.md) and its receipts identify implemented coverage and limits; [NEXT](../NEXT.md) states current authorization. This contract does not itself establish completion or authorize a new migration.

## Product objective

Turn heterogeneous provider files and retained source evidence into versioned, reviewable provider data. An operator can understand unfamiliar layouts, reuse approved mappings, compare deliveries, investigate office contact disagreements and export usable results without erasing original evidence or previous decisions. Optional model/API or external-agent assistance helps propose mappings and profile revisions. The longer-term domain includes licensing and provider/office/payer/product/network relationships.

The primary user is a provider-data operator. The first working environment is the existing single-user local application. The first integration is Tennessee-focused; statewide completeness, current appointment availability and verified insurance acceptance are not implied. A future public explorer consumes an approved export/API; it is not the initial operator interface.

## Release boundary and import breadth

Separate transport (upload, retained HTTP response), syntax (CSV, XLSX, JSON, FHIR Bundle), source semantics (roster, registry, directory, license, enrollment), and interpretation recipe. A new column layout is not necessarily a new parser. A readable file is not necessarily a valid provider roster.

The original S1.1 candidate matrix records the intended breadth, not a claim that every source or case is fully qualified:

| Candidate case | Required exercise | Boundary |
|---|---|---|
| Clinic CSV layout A | Text identifiers, missing values, repeated delivery and contact change | Supplied synthetic roster; operator-selected meaning |
| Clinic XLSX layout B | Explicit worksheet/header selection, different headings and reviewable cleaning | Same domain through a genuinely different layout; preserve originals |
| Declared JSON reference profile | Retained native keys, nested/repeated address semantics within supported profile | Do not flatten arbitrary JSON or generate clinician-office cross-products |
| Existing FHIR subset | Practitioner/Organization/Location/PractitionerRole evidence and unresolved references | Preserve existing profile/version and unsupported-resource limits |
| One named Tennessee-relevant source | Actual sample, source permission/access note, contact/address purpose, dated coverage and replay | Prefer reuse of a working adapter; no assumed licensing-to-office equivalence |
| Drift/unsupported challenge | Renamed header, ambiguous binding, missing key, unknown structure and partial capture | Hold or abstain with a reason; never silently force a mapping |

This matrix does not imply six new adapters. See the [adaptive release receipt](evidence/canonical/adaptive-release-2026-11-21/README.md) for actual coverage. Keep real samples outside Git; synthetic replay is not live-source qualification.

## Bounded source shortlist for P0

This is the historical P0 shortlist, not a current source selection or a list of newly qualified integrations. Verify access, actual response and field meaning before a new source is selected. The Tennessee-specific goal can be met by a Tennessee subset of a national registry, but must be labeled accordingly; it is not a state licensing or payer-participation dataset.

| Candidate | Starting reference | Decision to establish |
|---|---|---|
| NPPES Tennessee subset | [NPI Registry API](https://npiregistry.cms.hhs.gov/api-page) and existing NPPES adapter | Does the supported response expose usable practice-address/contact evidence with explicit query limits and multiple-address handling? |
| BCBST directory evidence | [BCBST developer resources](https://www.bcbst.com/developer-resources) | Can a bounded provider-directory response be obtained through an authorized route, and do its office links/profile semantics fit the existing FHIR subset? |
| Tennessee licensing report | [Health Professional Licensing Reports](https://internet.health.tn.gov/LicensureReports) | Inspect actual report shape and address purpose. Prefer S2 if it supports licensing evidence but not office-contact comparison. |

The original P0 remote investigation budget was: at most three candidates, ten total HTTP requests including redirects/retries, 10 MiB cumulative returned content, and a retained data sample of at most 200 records. It prohibited bulk national downloads, automated pagination crawls and model calls. Future investigations need their own selected scope and access limits.

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

The selected S1.1 implementation reuses existing registry/recipe relations; the full conceptual profile above is not a claim that every field is persisted. New semantics require a scoped contract and migration/recovery decision, not speculative tables.

Clinician, organization, office, license, payer, product and network are separate domain concepts. S1 implements only the additions required by its selected sources; preserve the ability to represent later relationships without prematurely building the entire network model. A license or enrollment row may provide reference evidence without establishing an exact practice location.

## Adaptation and learning contract

Recognize supported input or return unknown/ambiguous; never select a profile solely to obtain a successful parse. Drift produces a new compatibility report and proposed interpretation with pinned input/profile/recipe versions. Retain unknown fields as source evidence without silently making them business fields.

Current reuse retrieves compatible approved recipe examples in exact source/profile/scope; it creates a proposal for separate review. Superseded examples remain historical and are excluded from recommendations. Explicit example revocation and broader use of reviewer corrections remain future work. Rejected, unreviewed or source-injected content cannot become trusted examples.

Reuse the existing OnboardingService, MappingAssistant and MCP service boundary. A configured model API and an external agent must return the same validated proposal representation while retaining distinct provenance. Model proposals cannot approve recipes, accept sources, merge identities or promote datasets. Manual and deterministic paths remain usable.

Runtime extension produces declarative bindings and allowlisted transformations. A genuinely new parser is a developer-authored or agent-proposed code change, reviewed and tested through normal development before registration; runtime cannot install or execute generated code. Parser-generation assistance is later work, not an S1 runtime feature.

The selected model invocation contract specifies sample permission, redaction, prompt/result schemas, retrieval policy, configuration, budgets, cancellation, stale-input rejection and uncertain-call retry policy; see [source onboarding](SOURCE_ONBOARDING.md). Preserve the prior A1/A3 corpus; new capabilities receive a separate versioned evaluation. Use independent expected mappings, output values, abstentions and invalid-operation cases. Actual-model results, controlled-provider tests and observed human effort are different evidence. Do not tune expected answers after trials.

## Output contract

The implemented review workbook contains **Directory**, **Unresolved issues**, and **Sources and export details** worksheets, with **Reviewed corrections** when applicable. The Directory represents a pinned approved version; unresolved issues may refer to records still present with their previously approved value. Feed-scoped row/office/issue references and version/scope metadata make that relationship explicit without inferring a clinician identity. Preserve text identifiers, unknown values and safe spreadsheet cell serialization.

Retain existing machine-readable evidence exports. The [workbook contract](REVIEW_WORKBOOK_CONTRACT.md) defines columns, row grain, counts, selection, snapshot consistency, ordering, timestamps and source references. The workbook is a review deliverable, not an arbitrary payer's upload template. Recipient-specific exports require a named specification/version and their later acceptance gate. A locally approved value is not an externally verified contact or participation claim.

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

These requirements remain stable. The [adaptive receipt](evidence/canonical/adaptive-release-2026-11-21/README.md) maps the selected release to evidence; STATUS and later receipts identify subsequent changes and open gates. A design statement or test count alone does not close an acceptance ID.

## Decisions required for S1.1

The original S1.1 decisions covered the Tennessee reference source, roster authority, supported breadth, profile reuse, UI system, approval/export behavior and adaptive invocation. The selected decisions below and linked contracts supersede the initial candidate choices; remaining evidence gaps are recorded in STATUS.

## Revision discipline

Keep acceptance IDs stable. Changed semantics need a dated contract change and an assessment of affected tests, data and recovery before implementation. Later licensing, expanded network, research and exchange work require their own selected scope; see [ROADMAP](../ROADMAP.md) and [NEXT](../NEXT.md).

## Selected S1.1 decisions

- Existing approved clinic dataset remains the working roster; external reference assertions cannot replace it automatically. Field decisions do not implicitly promote a new dataset.
- First Tennessee evidence is a bounded NPPES API 2.1 Nashville/TN subset. A private three-record actual capture succeeded on 2026-11-21; six addresses included LOCATION and MAILING purposes. This is registry evidence, not state licensure or network acceptance. Synthetic samples remain committed examples.
- Reuse existing profile/recipe records and their approval history. Compatibility and reuse are bounded shared-service operations; missing mapped columns block reuse. No new database server or duplicate registry.
- The original S1.1 slice used shared CSS/components and deferred shadcn. The subsequent [workbench migration](UI_WORKBENCH_MIGRATION.md) adopted shadcn and Tailwind; component adoption alone does not establish visual acceptance.
- Review workbook reads a pinned approved version in a consistent read snapshot. It never applies contact proposals. Existing approval and verification stages remain authoritative.
- Optional actual-model and participant evidence remain independent open gates. A model transport is not invoked merely to claim completed adaptation quality.

## S1.3 selected correction-release delta — 2026-11-21

After UI qualification, the owner selected the complete reviewed-office-phone → candidate roster → separate dataset approval → pinned JSON/XLSX journey. [The materialization contract](FIELD_MATERIALIZATION_SPEC.md) freezes scope and failure semantics; [review format 2](REVIEW_WORKBOOK_CONTRACT.md) freezes extension/provenance output. Bulk and address corrections, licensing and expanded source-specific network reconciliation remain later work. Existing bounded organization/network intake and review are described in the [API reference](API_REFERENCE.md#organizationnetwork-intake-schema-v4). Existing AI-04/08/09 acceptance IDs cover decision preservation, inspected output and connected usability; the dated correction receipt records checks without substituting for participant evidence.
