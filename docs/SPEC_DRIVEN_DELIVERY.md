# Spec-driven delivery plan

Updated 2026-11-21. The active work is P0 planning for [S1](ADAPTIVE_INGESTION_SPEC.md); P0–P8 scheduling lives in [ROADMAP](../ROADMAP.md). The D/R work packages below are retained historical delivery contracts, not the current task queue.

Historical baseline updated 2026-11-14. The work packages below define the delivery sequence; linked receipts identify implemented and verified slices. This plan decomposes [ROADMAP](../ROADMAP.md); [STATUS](../STATUS.md) remains the sole summary of verified completion, and [NEXT](../NEXT.md) selects one active slice.

## Documentation authority

| Document | Owns | Update rule |
|---|---|---|
| [SPEC](../SPEC.md) | User, problem, behavior, non-goals and end-to-end acceptance | Change when product behavior or boundaries change; do not put task logs here |
| [ARCHITECTURE](ARCHITECTURE.md) | Components, shared contracts C1–C6 and integration risks | Change when a boundary or responsibility changes |
| Area contracts below | Detailed semantics, input/output expectations and failure cases | Mark planned versus implemented explicitly; resolve contract changes before dependent code |
| This delivery plan | Ordered work packages, dependencies, requirement-to-check mapping | Keep work IDs stable; link completed evidence instead of repeating logs |
| [ROADMAP](../ROADMAP.md) | Milestone outcomes and exit gates | Do not treat subtask completion as whole-milestone qualification |
| [NEXT](../NEXT.md) | One executable brief, current blockers and next action | Replace after a slice closes; link contracts and acceptance IDs |
| [STATUS](../STATUS.md) and `docs/evidence/` | Actual implementation/verification and dated receipts | Record revision, command, fixture, result and limits; preserve failed attempts |
| [DECISIONS](DECISIONS.md) | Why a consequential design was chosen | Add a short dated decision; explicitly supersede old choices |
| [API_REFERENCE](API_REFERENCE.md), [DATA_DICTIONARY](DATA_DICTIONARY.md) | Implemented HTTP and persistence contracts | Update with code; proposed interfaces belong in a labeled area contract first |

The README is the entrypoint, not another roadmap. Older intake proposals and execution/progress files are historical context, not competing task queues. Do not copy private chats into public design documents.

## Active specification revision protocol

S1.0 records the selected product direction. P0 must turn it into S1.1 with inspected source examples, a code/test gap map, populated user-flow/UI proposal, explicit planned service/storage/export contracts and an owner review. The roadmap assigns S1.2 before assisted adaptation, S1.3 before integrated release, then S2–S5 for licensing, networks, research/exchange and consumer/deployment architecture.

For each revision, record: previous revision; reason and changed behavior; affected requirement IDs; source/record grain; input/output examples; state transitions and error behavior; compatibility/migration/backfill/recovery impact; fixture expectations; chosen UI flow; budget/access limits; unresolved decisions; and selection/approval status. Do not invent an approval date or overwrite earlier decisions. Add a dated decision entry for consequential changes.

Each milestone brief must identify:

1. User-visible outcome and non-goals.
2. Required spec revision, dependencies and verified baseline.
3. Existing code to reuse and narrow implementation ownership.
4. Acceptance IDs mapped to meaningful tests/observations and actual exports.
5. Invocation-owned storage, source/model request limits and restart behavior.
6. Stop conditions, evidence to retain and exact continuation instructions.

A long run may complete the explicitly authorized milestones within their frozen contracts. It may choose internal implementation details. It must stop dependent work for unresolved durable semantics, insufficient source rights/access, an unapproved external cost/action or a required owner design decision; continue unrelated authorized work when useful. Record the blocking fact and proposed resolution rather than silently changing the goal. No passage of time grants approval.

Before implementation, maintain this row shape in the active area spec: **requirement ID → existing implementation/test → remaining gap → planned check → observed receipt/limit**. Unrun checks remain planned. A passing parser test does not close the UI/export requirement. Existing D/R/F/N/A/E/PX/UX identifiers remain stable; S1 uses AI-01–10.

After completion, STATUS records evidence, ROADMAP records the closed gate, NEXT selects one continuation, and implemented API/data docs change with code. Do not create another status dashboard or duplicate roadmap. Documentation-only revisions require link/whitespace checks and content consistency review, not full application requalification.

## Work areas and scope

| Area | What must change | Authoritative detail |
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

1. Read NEXT and its linked contracts; verify checkout, branch, dirty state and owned test storage. Preserve unrelated work. Use a focused branch from public ancestry for implementation.
2. Freeze the slice's user-visible behavior, data grain, service input/output, state changes, failure behavior and migration/recovery consequences. Mark open decisions. Resolve any that affect durable data or consumer meaning before dependent coding.
3. Author representative fixtures and independent expected outcomes. Add meaningful failing boundary tests; use a temporary characterization check where current behavior is unclear. Avoid tests that merely mirror helper implementations.
4. Implement the smallest connected path through producer, shared service, consumer/UI and export. Keep intermediate parser changes clearly incomplete until connected acceptance passes.
5. Run affected checks and AGENTS-required full gates for the completed slice. Inspect outputs and failure/recovery behavior. Record implementation versus automated verification versus human observation separately.
6. Review the diff against the contract, append a short receipt, update implemented API/data docs, STATUS and NEXT in the same change. Revise the area contract first if evidence requires a semantic change. Publication follows the repository's separate rules.

Use one active slice and a short ordered backlog. Small commits may isolate parser, persistence and UI changes, but merge/claim the feature only when its complete acceptance boundary passes. Do not add a new goal/tooling system, generated status dashboard or duplicated task tracker for this plan.

## Receipt and handoff minimum

A dated receipt records work ID, baseline/candidate revision, acceptance IDs, invocation-owned fixtures/root designation, commands and exit results, inspected output values, failed attempts/reruns, unresolved limits and the next action. Keep private runtime paths, credentials, real provider records and participant details outside public receipts. STATUS links the receipt and states what remains open.

H1 can run independently with [the existing walkthrough](INVESTIGATION_DEMO.md). H2 observes the expanded journey after D4. Engineering does not wait indefinitely for a participant, and automated success never substitutes for human usefulness evidence.

## Independent completion slices R1–R4

The renewed 2026-11-14 continuation is ordered in [ROADMAP](../ROADMAP.md#independent-headless-continuation): filtered-response integrity, coherent relationship qualification, portable distribution, then reviewable integrated delivery. These strengthen C1–C5 and packaging of the existing local product; actual-model access is not their dependency. R1 Q1–Q4 are frozen in [the source contract](PUBLIC_DATA_SOURCES.md#filtered-response-integrity-r1) and their retained brief/receipt. R2 G1–G4 are frozen in the FHIR contract, R3 P1–P4 in the operations distribution contract, and R4 V1–V4 in its retained review receipt/source contract. Each slice freezes acceptance before implementation. Preserve the original challenge corpus and historical receipts; qualify changed producer, consumer, UI and exports together before advancing.
