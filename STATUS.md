# Implementation status

Updated 2026-11-15. Provider Directory Workbench implements the bounded local workflow in [SPEC](SPEC.md). The implementation checkpoint is `d09b664`; [the integrated verification record](docs/evidence/canonical/integrated-review-2026-11-15/README.md) identifies tested files, exports and qualification results. Publication of this candidate is authorized; GitHub verification is recorded separately from local checks.

## Completed software

| Capability | Status | Evidence |
|---|---|---|
| File intake, cleaning and recurring feeds | Implemented | Reviewed recipes, quarantine, quality holds, explicit approval and pinned consumer in the [operations rehearsal](docs/evidence/canonical/operations-2026-11-14/README.md) |
| Saved FHIR and bounded HTTP intake | Implemented within declared subset | Native review/acceptance, retained response replay, filtered-query checks and [relationship qualification](docs/evidence/canonical/provider-graph-2026-11-14/README.md) |
| Reconciliation and investigations | Implemented | Separate identity/field decisions, NORTH/SOUTH provenance, outreach assertions, simulated submission and independent observation |
| Recovery and distribution | Verified | Restart, stale-write fencing, stopped backup/restore, packaged assets and isolated wheel/sdist journeys |
| AI/MCP assistance | Client and review integration implemented; actual-model evaluation incomplete | Controlled-provider tests and deterministic/manual fallback; experimental and disabled by default |

The core non-AI operations demonstration and all R1–R4 engineering follow-ups are complete. This describes implemented and automatically verified behavior; the project remains a local prototype.

## Verification

| Check | Last complete result |
|---|---|
| Python and synthetic pipeline | 869 tests passed; pipeline passed |
| Frontend | 134 tests passed; production build passed |
| Browser workflows | 72 desktop/phone scenarios passed |
| Installed distributions | Wheel and sdist-derived installations passed actual CLI/consumer/recovery journeys outside the checkout |
| Profile validation | Pinned whole synthetic Plan-Net graph: zero errors/warnings; intentional invalid fixtures retained |
| Public-source observation | Bounded HAP Location and role captures retained; multiple-Network projection and unsupported HealthcareService limits explicit |

These local results come from [the integrated record](docs/evidence/canonical/integrated-review-2026-11-15/README.md). The existing TestClient deprecation and Vite chunk-size advisory did not fail qualification. Historical test totals and failed/interrupted runs remain in their dated records.

## Remaining evidence and deferred scope

- **Actual-model A1/A3:** no completed real-provider trials. The last check found disabled configuration/no supplied API key. The [next brief](NEXT.md) defines the frozen eight-case evaluation and its bounds.
- **Human H1/H2:** no uncoached participant outcomes or demonstrated time savings. The [investigation walkthrough](docs/INVESTIGATION_DEMO.md) and [prepared-state observer kit](docs/OPERATIONS_DEMO.md#h2-prepared-state-observer-kit) are ready.
- **Standards and source coverage:** synthetic profile validity and limited actual captures do not establish application-wide or source-wide conformance. Broader coverage needs a named workflow and scoped contract.
- **Deployment:** authenticated teams, hosting, automated outreach, payer writeback and extra transport families are outside the current scope.

[ROADMAP](ROADMAP.md) sequences remaining work. The [archived execution record](docs/archive/status-2026-11-15.md) preserves the detailed checkpoint history; it is not a competing status page.
