# Implementation status

Updated 2026-11-21. Provider Directory Workbench implements the bounded local workflow in [SPEC](SPEC.md). The historical core implementation checkpoint is `d09b664`; [its integrated record](docs/evidence/canonical/integrated-review-2026-11-15/README.md) identifies the older backend/distribution qualification. UI1 is a local change set on feat/provider-operations-ui based on 52a6f4f; [the UI receipt and file hashes](docs/evidence/canonical/operator-ui-2026-11-19/README.md) identify this slice. No source push or deployment accompanied the local UI work.

## Current planning state

The 2026-11-21 documentation revision selects ingestion-first evolution, modular application boundaries, draft spec S1.0 and milestones P0–P8. [NEXT](NEXT.md) now selects P0 source/workflow/design readiness. The [planning receipt](docs/evidence/canonical/planning-2026-11-21/README.md) records documentation validation only. P0's actual-source selection, code/test gap matrix, detailed interface/export contracts, populated UI proposal and owner review remain **open**. No new adapter, profile-learning feature, licensing/network capability or redesigned release was implemented by this revision.

Existing UI1 and application edits remain local in this worktree. Historical test totals below were not rerun for documentation work. Future capabilities in S1 are targets, not a restatement of the implementation table.

## Completed software

| Capability | Status | Evidence |
|---|---|---|
| Operator shell and delivery evidence | Implemented locally | Task navigation, work entry, bounded typed comparisons, original evidence and precise source/status meanings in the [UI1 receipt](docs/evidence/canonical/operator-ui-2026-11-19/README.md) |
| File intake, cleaning and recurring feeds | Implemented | Reviewed recipes, quarantine, quality holds, explicit approval and pinned consumer in the [operations rehearsal](docs/evidence/canonical/operations-2026-11-14/README.md) |
| Saved FHIR and bounded HTTP intake | Implemented within declared subset | Native review/acceptance, retained response replay, filtered-query checks and [relationship qualification](docs/evidence/canonical/provider-graph-2026-11-14/README.md) |
| Reconciliation and investigations | Implemented | Separate identity/field decisions, NORTH/SOUTH provenance, outreach assertions, simulated submission and independent observation |
| Recovery and distribution | Verified | Restart, stale-write fencing, stopped backup/restore, packaged assets and isolated wheel/sdist journeys |
| AI/MCP assistance | Client and review integration implemented; actual-model evaluation incomplete | Controlled-provider tests and deterministic/manual fallback; experimental and disabled by default |

The core non-AI operations demonstration and all R1–R4 engineering follow-ups are complete. This describes implemented and automatically verified behavior; the project remains a local prototype.

## Verification

| Check | Last complete result |
|---|---|
| Python and synthetic pipeline | Historical 2026-11-15: 869 tests and pipeline passed; unchanged backend, not rerun for UI1 |
| Frontend | UI1: 136 tests passed; production build passed |
| Browser workflows | UI1 initial full suite 74 passed; final affected run 18 passed/4 old-heading assertions failed, then all four passed in a corrected fresh run; final shell/focus pair 2 passed |
| Installed distributions | Wheel and sdist-derived installations passed actual CLI/consumer/recovery journeys outside the checkout |
| Profile validation | Pinned whole synthetic Plan-Net graph: zero errors/warnings; intentional invalid fixtures retained |
| Public-source observation | Bounded HAP Location and role captures retained; multiple-Network projection and unsupported HealthcareService limits explicit |

The older backend/distribution/source results come from [the integrated record](docs/evidence/canonical/integrated-review-2026-11-15/README.md); [UI1 evidence](docs/evidence/canonical/operator-ui-2026-11-19/README.md) preserves frontend/browser failures and reruns separately. The existing TestClient deprecation and Vite chunk-size advisory did not fail qualification. Historical test totals and failed/interrupted runs remain in their dated records.

## Remaining evidence and deferred scope

- **Actual-model A1/A3:** no completed real-provider trials. The last check found disabled configuration/no supplied API key. The [retained model brief](docs/archive/next-2026-11-15.md) defines the frozen eight-case evaluation and its bounds.
- **Human H1/H2:** no uncoached participant outcomes or demonstrated time savings. The [investigation walkthrough](docs/INVESTIGATION_DEMO.md) and [prepared-state observer kit](docs/OPERATIONS_DEMO.md#h2-prepared-state-observer-kit) are ready.
- **Standards and source coverage:** synthetic profile validity and limited actual captures do not establish application-wide or source-wide conformance. Broader coverage needs a named workflow and scoped contract.
- **Deployment:** authenticated teams, hosting, automated outreach, payer writeback and extra transport families are outside the current scope.

[ROADMAP](ROADMAP.md) sequences remaining work. The [archived execution record](docs/archive/status-2026-11-15.md) preserves the detailed checkpoint history; it is not a competing status page.

## Selected design and next domain work

PX0's [v1 contract](docs/PROVIDER_OPERATIONS_CONTRACT.md) and independent two-office response fixtures define adaptive profiles, exact recipient-response correlation, CMS enrollment/NPPES relationships, finite case research and recipient packets. They introduce no runtime adapters, endpoints, migrations or new model/source trials. The [operator contract](docs/OPERATOR_EXPERIENCE.md) governs UI1; [operational measures](docs/OPERATIONAL_MEASURES.md) remain a separate planned read-only surface.

[ROADMAP](ROADMAP.md) explicitly reschedules PX1/PX3/PX4 into later exchange/research work and maps PX2 evidence to licensing/network milestones. [S1.0](docs/ADAPTIVE_INGESTION_SPEC.md) owns the immediate ingestion/contact target. Existing model/human evidence gates remain open; no recipient compatibility follows from the implemented shell or planned workbook.
