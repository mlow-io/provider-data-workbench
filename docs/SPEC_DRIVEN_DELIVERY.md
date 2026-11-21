# Spec-driven delivery plan

This is a reference for the delivery contracts and stable acceptance IDs. P0 planning and the D/R packages below are historical, not the current task queue. [NEXT](../NEXT.md) states the current selection and authorization, [STATUS](../STATUS.md) records implementation and evidence, and [ROADMAP](../ROADMAP.md) describes future direction.

## Documentation authority

[AGENTS](../AGENTS.md) defines the working agreement and document authority. [SPEC](../SPEC.md) and the relevant area contract describe behavior; [API_REFERENCE](API_REFERENCE.md) and [DATA_DICTIONARY](DATA_DICTIONARY.md) describe implemented interfaces and persistence. [DECISIONS](DECISIONS.md) records consequential choices, while dated evidence preserves observed outcomes and limitations. Older intake proposals and progress files are historical context.

## Active specification revision protocol

The S1 planning and implementation history is retained in [the adaptive contract](ADAPTIVE_INGESTION_SPEC.md) and its linked receipts. Before a new selected slice changes durable meaning, specify its source and record grain, input/output and failure behavior, compatibility and recovery effects, acceptance checks, and unresolved decisions. Reuse existing implementations and keep requirement IDs stable. A roadmap item is not authorization to implement it.

For a completed slice, record actual checks and limits in STATUS or its linked receipt, and update implemented API/data references when applicable. [AGENTS](../AGENTS.md) owns the working and verification rules.

## Work areas and scope

The following responsibilities retain the original D-series framing; see STATUS for their present implementation and limits.

| Area | Original scope | Authoritative detail |
|---|---|---|
| Source acquisition | One bounded payer FHIR source; explicit query scope, page/error/retry evidence and replay | [Public sources](PUBLIC_DATA_SOURCES.md), C1, D2 |
| Parsing and healthcare semantics | Typed resource interpretation, references, profile findings and conservative comparison projections | [FHIR intake](FHIR_INTAKE_CONTRACT.md), C2/C3, D1 |
| Cleaning and quality | Preserve versioned clinic recipes; keep resource validity, comparison usability and operational eligibility separate | [Source onboarding](SOURCE_ONBOARDING.md), FHIR contract, D1/D3 |
| Reconciliation and data management | Carry supporting source references, preserve reviewed identity scopes and stale-write checks; keep approved clinic versions stable | [Reconciliation](RECONCILIATION_CONTRACT.md), [data dictionary](DATA_DICTIONARY.md), C3–C5 |
| Operator experience | New evidence and assistance states within existing Intake/Reconcile/Feeds; usable next action and preserved selections | SPEC web requirements; acceptance cases in each slice |
| AI assistance | One optional mapping proposal task with actual invocations, manual fallback and baseline evaluation | [Source onboarding](SOURCE_ONBOARDING.md), SPEC AI requirements, C6, D3 |
| Consumer and evaluation | Approved-version reader, traceable exports, failure rehearsal and observed operator task | [Managed-feed data contract](DATA_DICTIONARY.md#managed-recurring-feed-schema-11), [operator procedure](operations_governance/sop_provider_remediation.md), D4, H1/H2 |

These areas are responsibilities, not seven independent builds. Implement one complete slice through the affected backend, UI, export and tests before starting the next.

## Ordered work packages

These are historical D-series work packages and acceptance boundaries, not instructions to repeat completed work.

| ID | Deliverable | Depends on | Acceptance / completion evidence |
|---|---|---|---|
| D1.0 | Contract readiness: inspect acceptance/projection/export seams; choose additive persistence and comparison representation; specify interface examples and fixture inventory | Existing M0–M4 baseline | Resolve FHIR contract's three readiness decisions; record ADR and exact proposed payloads/migration disposition. No parser implementation before this boundary is coherent. |
| D1.1 | Pure saved-Bundle parser and validator integration with authored fixtures | D1.0 | F1–F5; pinned validation tool/packages and offline behavior; no database/network side effects in parser |
| D1.2 | Durable intake, typed comparison projection and reviewed evidence export | D1.1 | F3–F7; populated storage preservation, explicit reference acceptance, stale rejection and complete field lineage |
| D1.3 | Connected saved-Bundle UI task and D1 qualification | D1.2 | F6–F8; inspect real downloads, restart and NORTH/SOUTH scope; required full checks for affected code |
| D2.0 | Select one public endpoint and freeze query/coverage, response budget, acquisition state/retry and destination policies | D1 qualified | Read-only capability/sample investigation and source contract; choose controlled fixture endpoint if live source unavailable and label live verification open |
| D2.1 | Bounded transport through existing retention and D1 parser, with visible operational states | D2.0 | N1–N3; controlled HTTP faults, repeat/restart and unchanged approved version; separate public smoke receipt |
| D3.0 | Freeze mapping evaluation, one model/agent invocation route, data policy, budgets and run/proposal API | D2 qualified | Proposed request/result examples and adverse cases; expected mappings authored before model trials; no new transformation language |
| D3.1 | Optional assistance in normal review, provenance and evaluated outcomes | D3.0 | A1–A3; actual invocation, rejected malformed/stale output, manual fallback and held-out comparison; experimental if benefit unproven |
| D4.1 | Mixed-source journey plus downstream approved-version consumer | D3 evaluated, or explicitly limited no-model route while actual access is unavailable | E1–E2; usable without AI, version-pinned consumer output, inspected evidence handoff, held delivery and recovery |
| D4.2 | Qualification and concise case-study update | D4.1 | Fresh required checks, receipt index, limitations, original baseline preserved; publication remains a separate action |

D1 saved-source and D2 bounded-source engineering are implemented and qualified within their declared limits. D3 client/review engineering is controlled-provider tested; actual-model A1/A3 remain open. D4 is qualified through the documented no-model route. [STATUS](../STATUS.md) and [the evidence index](evidence/canonical/README.md) identify the exact outcomes. The [operations contract](OPERATIONS_DEMO.md) owns consumer representation and demonstration instructions.

## Acceptance traceability

F1–F8 are defined in [the FHIR contract](FHIR_INTAKE_CONTRACT.md). The remaining stable acceptance IDs are:

| ID | Required observable behavior | Intended check and evidence |
|---|---|---|
| N1 | Local replay and bounded HTTP capture produce equivalent supported evidence from the same bytes | Adapter/service integration with controlled responses and retained digests |
| N2 | Later-page failure, 429, malformed response, unsafe next/reference target and budget exhaustion stay failed/partial | Controlled HTTP tests plus UI state; retain attempted/completed page scope and error bodies when available |
| N3 | Repeat/restart cannot duplicate accepted logical results or change the prior clinic-approved version | Transaction/recovery tests and exact consumer version/content checks |
| A1 | Actual model/agent proposal retains run/input context and reaches normal review without an approval side effect | Invocation receipt, proposal inspection and browser/service checks |
| A2 | Invalid, adversarial, stale, timed-out or cancelled output cannot bypass deterministic validation; manual mapping works | Negative service tests, failure-state UI and no-model journey |
| A3 | Mapping quality is measured against authored expectations and current deterministic suggestions | Frozen corpus manifest, model/configuration, raw outcomes, denominators, corrections/abstentions and available usage; human effort measured only if observed |
| E1 | A consumer can read a named approved version and retains it while a new candidate is held | Small read-only consumer rehearsal against the existing approved-version export; assert version and actual values |
| E2 | Selected NORTH investigation retains all contributing evidence across restart without claiming SOUTH evidence as NORTH | Integrated browser/recovery rehearsal, inspected JSON/XLSX, scope/value assertions |

Each implementation PR/receipt maps affected IDs to actual test names or observed artifacts. Intended tests above do not exist merely because they are listed. Unsupported behavior must have an explicit finding or scoped exclusion, never a silent pass.

## Working loop

Follow the selected brief and the working agreement in [AGENTS](../AGENTS.md). Inspect existing behavior, implement a connected slice, verify meaningful outputs and preserve any failed or partial evidence. Do not treat a planned check as an observed result.

## Receipt and handoff minimum

A dated receipt identifies the revision, fixtures, checks, inspected outputs, failures and limitations; STATUS links it. Keep private runtime data and credentials out of public receipts. H1 and H2 require actual participants; automated checks cannot establish human usefulness.

## Independent completion slices R1–R4

The 2026-11-14 continuation is recorded in [ROADMAP](../ROADMAP.md#independent-headless-continuation): filtered-response integrity, coherent relationship qualification, portable distribution, then reviewable integrated delivery. These strengthen C1–C5 and packaging of the existing local product; actual-model access is not their dependency. R1 Q1–Q4 are frozen in [the source contract](PUBLIC_DATA_SOURCES.md#filtered-response-integrity-r1) and their retained brief/receipt. R2 G1–G4 are frozen in the FHIR contract, R3 P1–P4 in the operations distribution contract, and R4 V1–V4 in its retained review receipt/source contract. These are historical completed slices; preserve their challenge corpus and receipts. See STATUS for their verified boundaries.
