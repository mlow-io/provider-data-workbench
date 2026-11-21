# Roadmap

Updated 2026-11-21. **Ingestion-first product evolution supersedes the November 19 PX1-first order.** Build one adaptable provider-data workbench with explicit module boundaries. Import breadth, reviewed cleaning/mapping and preserved decisions are the foundation; contact review proves the first complete workflow, followed by licensing, identity and network operations. [SPEC](SPEC.md) defines global behavior; [S1](docs/ADAPTIVE_INGESTION_SPEC.md) retains the selected release contract and unclosed goals; [STATUS](STATUS.md) reports actual outcomes.

## Selected workbench migration

The incremental S1.1 UI does not complete component-system adoption. [UI-W0–W5](docs/UI_WORKBENCH_MIGRATION.md) now sequences a populated design spike, shadcn/Tailwind foundation, one complete delivery workbench, import/mapping migration, remaining discrepancy/provider tools and retirement/qualification. Each stage has a U1 spec revision and WM acceptance gates. The shared shell and primary delivery/import/mapping/reconciliation components are implemented; STATUS and the migration receipt identify remaining qualification/supporting-surface gates. The [100/1,000-record engineering qualification](docs/UI_QUALIFICATION.md) records actual preview/export and responsiveness checks. S1.3 connects reviewed field decisions to separately approved candidates; supporting legacy retirement and owner/human evidence remain explicit gates. preserve all later domain milestones and separate actual-model/human gates.

## Active planning and first release

The owner authorized implementation on 2026-11-21. The first integrated S1.1 release implements bounded ingestion reuse, assisted context and reviewed export; [STATUS](STATUS.md) and its receipt identify exact coverage and remaining gaps. [NEXT](NEXT.md) selects the current continuation. The table below retains milestone goals and contract gates; authorization does not turn unimplemented rows into completed work. P0 must identify existing implementations before proposing new work. Preserve existing D/R/PX/UX acceptance identifiers; AI identifiers belong to S1.

| Milestone | Spec goal and deliverable | Exit gate and next revision |
|---|---|---|
| **P0 — source, workflow and design readiness** | Refine S1.0 into an S1.1 review packet: implementation gap map, bounded source matrix and actual sample semantics, field-to-export flow, module ownership, synthetic challenge inventory and populated UI proposal | AI-01–10 mapped to existing/gap/evidence; consequential decisions explicit; owner reviews scope and UI direction before production coding. Write P1 brief only after that decision. |
| **P1 — coherent operator interface** | Implement the approved S1.1 shell and populated import/mapping/quality/office-review journey using existing services; refactor touched screens and remove conflicting styles | AI-09 and UX1–5 on touched paths; working desktop/narrow views and state retention; no decorative future destinations. Preserve exports and decision boundaries. |
| **P2 — source profiles and repeatable ingestion** | Implement S1.1's declared breadth, reusable manual/deterministic profiles, drift reports and required additive persistence; integrate the Tennessee source into normal review | AI-01–04, AI-07, AI-10 plus affected existing checks; actual-source gate separately reported. Before P3, draft and review **S1.2** adaptation/provider/evaluation contract. |
| **P3 — assisted adaptation** | Implement S1.2 profile/example reuse and model/API or external-agent proposals through common validated services | AI-05, repeat/stale/cancel/permission cases, frozen comparison to manual/deterministic baseline. Actual model access/quality remains separately gated. Before P4, freeze **S1.3** output/release acceptance. |
| **P4 — complete contact-review release** | Finish S1.3 contact decisions, pinned workbook/evidence export, subsequent-delivery comparison, replay/restart and prepared example | AI-01–10 integrated results with exact limits; inspect real exports, preserve earlier approved output, owner visual review and separate human observation. Reproducible launch and walkthrough. Draft S2 at closure. |

P1 is a coherent UI slice over existing functionality, not a promise that P2/P3 already exist. P2 includes its own connected UI; P4 integrates and qualifies the complete release. A blocked actual-model trial does not prevent manual use; it also cannot be called completed model qualification. If actual-source access fails, complete independent tasks, retain the blocker and obtain a source-scope decision before claiming the live goal.

## Long-term milestones and scheduled specification work

| Milestone | Next spec revision to draft before coding | Product outcome and hard boundary |
|---|---|---|
| **P5 — licensing and expanded identity investigation** | **S2.0** after P4: named Tennessee licensing source, permitted access, native license keys, status/effective-date meaning, matching rules and reviewer flow | Review license disagreements and ambiguous/duplicate identities. Basic safe clinician/office association already belongs in S1. Name-only matches never establish licensure or exclusion. |
| **P6 — provider and network relationships** | **S3.0** after S2 qualification: payer/product/network/organization/office grains, participation periods, identifiers, source assertions and consumer queries | Compare source-scoped participation and network changes. Preserve explicit links and uncertainty; NPI alone never means globally in-network. Revisit supported FHIR resources/versions only for selected queries. |
| **P7a — bounded acquisition and discrepancy research** | **S4.0** after a named P5/P6 evidence gap: specific search/HTML/PDF source, terms/access, extraction locators, shared budgets and proposal schema | Retained search/capture/extraction evidence attached to a selected case. Failed search is not evidence of absence. No open crawl or autonomous outreach. |
| **P7b — recipient exchange and response reconciliation** | **S4.1** using retained PX contracts: one named recipient template/version, outbound pins, response correlation, partial acceptance and correction workflow | Prepare recipient-specific output, inspect response disposition and later observation separately. Full X12/claims processing remains a separate product decision. |
| **P8 — independent consumer and delivery architecture** | **S5.0** when the core release is useful: audience, hosting/data isolation, persistence/backup, authorization, operational limits and actual deployment requirements | A public/sandbox explorer can consume an approved export or read-only API. Extract ingestion into a package only for a second real consumer; separate service/repository only for independent deployment or ownership needs. |

P5/P6 may expose a source gap worth a bounded P7a acquisition slice earlier; revise ROADMAP/NEXT explicitly with dependency and acceptance impact. Do not silently reorder the plan. CMS public enrollment and NPPES supplied profiles can support S2/S3 when their exact relationship semantics are selected. No statewide completeness, inferred appointments, global network truth or production benefit claims follow from a demo.

## Spec revision and execution rules

Before each milestone: inspect current code and STATUS; draft the named revision with input/output examples, states, data ownership, migration/backfill/recovery consequences, adverse fixtures and exact acceptance; record open decisions; obtain review for consequential product changes; update NEXT to a bounded executable brief. API_REFERENCE and DATA_DICTIONARY describe implemented contracts only and change with code.

After each milestone: inspect outputs and history, run required affected checks, retain failures and limits, update STATUS and the acceptance map, and draft the next revision. Keep one active milestone. The next agent may choose implementation details within agreed contracts; it must not redefine record meaning, remove approval boundaries or quietly broaden source/model scope.

Use one application, Python/FastAPI, React/TypeScript, SQLite and retained artifacts until requirements justify change. The primary client now uses official shadcn Radix Nova primitives and Tailwind; qualify changes against the selected workbench contracts. Do not add infrastructure solely to increase the technology list.

## Proposed provider research and exchange extension

The November 19 [PX design](docs/PROVIDER_RESEARCH_EXCHANGE.md), [operations contract](docs/PROVIDER_OPERATIONS_CONTRACT.md), [measures](docs/OPERATIONAL_MEASURES.md) and [archived PX1 brief](docs/archive/next-2026-11-19-px1.md) remain valuable future contracts. Their scheduling is superseded above; their safety and semantic boundaries remain unless explicitly revised.

| Earlier work | New placement |
|---|---|
| PX0 profile/adaptation concepts | Reconcile with S1/P0–P3; do not create duplicate registries |
| UI1 implemented shell | Baseline for P1; historical verification remains separate |
| PX1 external responses | P7b/S4.1 |
| PX2 enrollment and NPPES profiles | Selected source evidence in P5/P6 |
| PX3 bounded case research | P7a/S4.0 |
| PX4 recipient templates and measures | P7b; measures only when the operational question exists |
| PX5 integrated rehearsal | Each relevant milestone gets its own integration gate |

## Independent evidence gates

Actual-model A1/A3 and uncoached-human H1/H2 remain open according to STATUS. Preserve the existing frozen model corpus and historical receipts; new adaptation capability needs its own evaluation. Human observation can proceed independently of implementation and cannot be replaced by agent rehearsal. Source-wide conformance is not established by synthetic profile validation or bounded captures. Publication/visibility, hosting and outreach are separate actions, not implicit in milestone completion.

## Delivered baseline


| Milestone | State | Completion boundary |
|---|---|---|
| D0 Product and contract alignment | Complete | One local provider-data operations workflow, documented source/decision boundaries and ordered acceptance cases |
| D1 Saved FHIR evidence | Complete within declared subset | F1–F8: bounded parsing, typed relationships, native review/acceptance, NORTH/SOUTH lineage and inspected exports; pinned synthetic profile reports |
| D2 Bounded network ingestion | Complete within recorded source scope | N1–N3: fixed payer endpoint, query/page/reference budgets, retained failures/replay, source cooldown and restart; limited actual HAP observations recorded separately |
| D3 Optional mapping assistance | Client/review engineering complete; actual-model evaluation open | A2 controlled negative paths pass; A1/A3 need configured approved access and measured results on the unchanged frozen corpus |
| D4 Integrated operations demonstration | Complete through no-model route | E1–E2: mixed-source workflow, held candidate, independent approved-version consumer, NORTH handoff and stopped recovery |

The earlier M0–M4 investigation/consolidation milestones remain documented in [historical verification](docs/evidence/canonical/README.md). D3's open evaluation does not prevent manual/deterministic operation or the completed D4 demonstration.

<a id="independent-headless-continuation"></a>

## Delivered headless continuation


| ID | Delivered result | Evidence |
|---|---|---|
| R1 | Filtered match/include/outcome checks, retained errors and publication-time revalidation | [Filtered-response qualification](docs/evidence/canonical/filtered-response-2026-11-14/README.md) |
| R2 | Coherent graph, versioned profile handling and explicit actual-source projection limits | [Graph qualification](docs/evidence/canonical/provider-graph-2026-11-14/README.md) |
| R3 | Packaged immutable defaults and clean wheel/sdist installed workflows | [Distribution qualification](docs/evidence/canonical/portable-distribution-2026-11-14/README.md) |
| R4 | Strict reference JSON, isolated builds, integrated verification, content review and local commit organization | [Integrated review](docs/evidence/canonical/integrated-review-2026-11-15/README.md) |

R1–R4 are complete. Their verification does not close actual-model, human or broader conformance gates.

## Integrated-release continuation

The bounded S1.1 release does not close every goal in the table. S1.3 implements explicit field-decision-to-candidate-roster materialization with separate approval. The independent external-agent mapping challenge is recorded in STATUS; broader production-model and human evidence remain open. Next revise the Tennessee licensing-source S2 spec before implementation, preserving network S3 as its own later revision. Continue under the owner's implementation authorization while freezing each new semantic contract before code. Actual-model calls require approved configured access; human outcomes require real participants. Do not relabel those external evidence gaps as completed engineering.
