# Roadmap

Build one adaptable provider-data workbench: import and clean declared sources, preserve review decisions, and release traceable data. Office-contact correction is the first integrated application; licensing and provider/network operations remain the long-term direction. [SPEC](SPEC.md) defines behavior, [STATUS](STATUS.md) records observed results, and the current request/[NEXT](NEXT.md) select work. This roadmap does not authorize every future row.

## Delivered foundation and remaining evidence

| Area | Current disposition | Detail |
|---|---|---|
| Ingestion/adaptation and contact workflow (original P0–P4 / S1) | Bounded implementation delivered: source/recipe reuse, reviewed identities, phone candidates, separate approval and complete exports | [Adaptive contract](docs/ADAPTIVE_INGESTION_SPEC.md), [correction contract](docs/FIELD_MATERIALIZATION_SPEC.md) |
| Workbench migration (UI-W) | Primary shell and review/import/mapping controls migrated; 100/1,000-record engineering qualification recorded | [Migration scope and remaining surfaces](docs/UI_WORKBENCH_MIGRATION.md), [qualification](docs/UI_QUALIFICATION.md) |
| Optional assistance | Shared proposal/review services and controlled client implemented; one independent external-agent challenge recorded | [Evaluation and limits](docs/AI_MAPPING_EVALUATION.md); production-model quality and human benefit remain open |
| Human/owner acceptance | Owner visual acceptance and uncoached participant outcomes have not been established | [Investigation walkthrough](docs/INVESTIGATION_DEMO.md), [observer kit](docs/OPERATIONS_DEMO.md#h2-prepared-state-observer-kit) |

These dispositions do not close every original acceptance goal. A bounded live sample is not statewide coverage; an agent rehearsal is not human evidence. Supporting UI cleanup can proceed when a selected task touches it rather than forcing another whole-app migration.

## Proposed next domain milestone

**P5 / S2 — Tennessee licensing and expanded identity investigation.** Select a named source and inspect actual access, terms, credential grain, identifiers, status/date meaning and retained evidence. Define conservative matching/review rules and synthetic adverse cases before adding an adapter or migration. Existing NPPES license metadata is not board verification. S2 planning remains a proposal unless the owner selects it; the current audit does not select licensing implementation.

## Later specification revisions

| Milestone | Contract needed before implementation | Outcome and boundary |
|---|---|---|
| P6 / S3 — provider and network relationships | Payer/product/network/organization/office grains, participation periods, identifiers, source scope and reviewed links | Expand existing scoped network intake/review into named operational queries; no global in-network inference from NPI |
| P7a / S4.0 — bounded acquisition and case research | Named search/HTML/PDF source, access, locators, shared budgets and proposal schema | Retained evidence for a selected discrepancy; no open crawler or autonomous outreach |
| P7b / S4.1 — recipient exchange | Named recipient/template version, outbound pins, response correlation and partial acceptance | Distinguish receipt, recipient acceptance and later observation; full claims/X12 processing is a separate product decision |
| P8 / S5 — independent consumer/deployment | Actual audience, isolation, authorization, refresh, persistence/recovery and operational needs | Separate explorer or ingestion package only for a real second consumer; services/repositories only for independent deployment or ownership |

A named licensing/network evidence gap may justify acquisition work earlier. Revise the selected contract and NEXT explicitly; do not silently expand source/model access or durable meanings. Bulk/address corrections and recipient templates are future features, not defects in the one-phone contract.

## Evidence and architecture gates

- Keep the modular Python/FastAPI, React and SQLite application until a measured requirement justifies extraction. Do not add technology to enlarge the stack.
- A source adapter needs supported access, native keys/grain, retained examples and checks. Standards documentation alone is not integration or conformance.
- Production-model trials and human outcomes retain their own evidence and access requirements. The external-agent challenge does not close them.
- Hosting, visibility changes, outreach and payer writeback remain separate actions. Follow existing owner authorization; do not infer it from milestone completion.
- Update contracts when behavior changes, STATUS when evidence changes and NEXT when selected work changes. [AGENTS](AGENTS.md) owns the working process; [delivery traceability](docs/SPEC_DRIVEN_DELIVERY.md) preserves acceptance IDs.

<a id="proposed-provider-research-and-exchange-extension"></a>

## Retained research and exchange designs

[Provider research/exchange](docs/PROVIDER_RESEARCH_EXCHANGE.md), [provider operations](docs/PROVIDER_OPERATIONS_CONTRACT.md) and [operational measures](docs/OPERATIONAL_MEASURES.md) remain design references. Earlier PX1/PX4 exchange work maps to P7b; PX3 case research maps to P7a; PX2 enrollment/registry ideas can inform S2/S3 only after source semantics are selected. They are not additional active queues or implemented recipient integrations.

<a id="independent-headless-continuation"></a>

## Historical delivered milestones

D1 saved FHIR, D2 bounded source capture, D4 no-model operations and R1–R4 filtered-response/graph/distribution/integration work are recorded in the [evidence index](docs/evidence/canonical/README.md). D3 client/review engineering is implemented; its production-model evaluation remains open. Older M0–M4 and PX briefs are historical references. Preserve their IDs and results without replaying their implementation plans as current work.
