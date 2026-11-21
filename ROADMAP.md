# Roadmap

Updated 2026-11-15. The bounded local operations workflow is implemented and automatically verified. Remaining work strengthens model, human and standards evidence. [STATUS](STATUS.md) records current results; [SPEC](SPEC.md) defines behavior and [the delivery map](docs/SPEC_DRIVEN_DELIVERY.md) preserves detailed acceptance IDs.

## Delivered scope

| Milestone | State | Completion boundary |
|---|---|---|
| D0 Product and contract alignment | Complete | One local provider-data operations workflow, documented source/decision boundaries and ordered acceptance cases |
| D1 Saved FHIR evidence | Complete within declared subset | F1–F8: bounded parsing, typed relationships, native review/acceptance, NORTH/SOUTH lineage and inspected exports; pinned synthetic profile reports |
| D2 Bounded network ingestion | Complete within recorded source scope | N1–N3: fixed payer endpoint, query/page/reference budgets, retained failures/replay, source cooldown and restart; limited actual HAP observations recorded separately |
| D3 Optional mapping assistance | Client/review engineering complete; actual-model evaluation open | A2 controlled negative paths pass; A1/A3 need configured approved access and measured results on the unchanged frozen corpus |
| D4 Integrated operations demonstration | Complete through no-model route | E1–E2: mixed-source workflow, held candidate, independent approved-version consumer, NORTH handoff and stopped recovery |

The earlier M0–M4 investigation/consolidation milestones remain documented in [historical verification](docs/evidence/canonical/README.md). D3's open evaluation does not prevent manual/deterministic operation or the completed D4 demonstration.

## Remaining work and entry conditions

| Priority | Work | Entry condition and bounded outcome |
|---|---|---|
| 1 | Actual-model A1/A3 | Approved configured API access. Run the existing eight-case evaluation once within its call/cost limits. Retain actual responses, invalid outputs, abstentions, corrections, usage and latency. Keep experimental/disabled when benefit is unsupported. |
| 2 | Human H1/H2 | Available uncoached participant and synthetic owned root. Observe task completion, errors and assistance using the [investigation walkthrough](docs/INVESTIGATION_DEMO.md) or [prepared-state operations task](docs/OPERATIONS_DEMO.md#h2-prepared-state-observer-kit). Comparative time savings require comparable observed tasks. |
| 3 | Broader standards/source evidence | A specific workflow gap and named bounded task. Whole synthetic-graph validity and recorded HAP captures do not establish source-wide conformance. Preserve the source's advertised guide version and the consumer's target version separately. |

[NEXT](NEXT.md) gives the executable actual-model brief. Human observation can proceed independently. Publishing the reviewed candidate is authorized; GitHub ref and CI checks establish delivery separately from these product-evidence gates. Hosted deployment is outside this publication task.

## Independent headless continuation

| ID | Delivered result | Evidence |
|---|---|---|
| R1 | Filtered match/include/outcome checks, retained errors and publication-time revalidation | [Filtered-response qualification](docs/evidence/canonical/filtered-response-2026-11-14/README.md) |
| R2 | Coherent graph, versioned profile handling and explicit actual-source projection limits | [Graph qualification](docs/evidence/canonical/provider-graph-2026-11-14/README.md) |
| R3 | Packaged immutable defaults and clean wheel/sdist installed workflows | [Distribution qualification](docs/evidence/canonical/portable-distribution-2026-11-14/README.md) |
| R4 | Strict reference JSON, isolated builds, integrated verification, content review and local commit organization | [Integrated review](docs/evidence/canonical/integrated-review-2026-11-15/README.md) |

R1–R4 are complete. Their verification does not close actual-model, human or broader conformance gates.

## Growth and stop conditions

Keep the current Python/FastAPI, React/TypeScript, SQLite and retained-artifact design. New work starts with a named user problem, explicit source/decision grain, bounded acceptance case and recovery consequences. Resolve durable contract changes before implementation; qualify the affected backend, UI and export together.

Scraping/OCR, SFTP/object storage, arbitrary plugins, FHIR server/export/writeback, authenticated teams and hosting are deferred. Add one only when a concrete workflow or measured workload requires it. Ambiguous source relationships remain visible; do not broaden cardinality or invent bindings to force a source into an office projection.

A delivery is useful when a reviewer can run the synthetic workbench, trace an output to its originals and decisions, explain a held delivery, and reopen the same pinned data. The [case study](docs/CASE_STUDY.md) describes those engineering outcomes and the claims still unproven.
