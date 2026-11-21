# Implementation status

Updated 2026-11-21. Provider Directory Workbench implements the bounded local workflow in [SPEC](SPEC.md). The historical core implementation checkpoint is `d09b664`; [its integrated record](docs/evidence/canonical/integrated-review-2026-11-15/README.md) identifies the older backend/distribution qualification. UI1 is a local change set on feat/provider-operations-ui based on 52a6f4f; [the UI receipt and file hashes](docs/evidence/canonical/operator-ui-2026-11-19/README.md) identify this slice. No source push or deployment accompanied the local UI work.

## Adaptive release implementation

The owner authorized implementation and privacy-reviewed public delivery on 2026-11-21, superseding the P0-only boundary. The [adaptive release receipt](docs/evidence/canonical/adaptive-release-2026-11-21/README.md) records new verification separately from UI1 and older results.

Implemented additions: approved-recipe compatibility/drift and proposal-only reuse through HTTP/MCP; duplicate-header abstention; opt-in bounded approved-example context for model proposals; scoped work identity with matching legacy-history reuse; registry-reported license/contact-purpose metadata; pinned approved-directory workbook preview/download; readable original/interpreted evidence tables and connected import/export controls.

No new database server, queue, runtime code plugin or schema migration was introduced. Model-context transport is controlled-provider tested; actual-model usefulness is still unverified. Registry license entries are not licensing-board verification. New licensing-source profiles, expanded network analytics, case research and recipient exchange remain roadmap work. At that adaptive-release checkpoint, the workbook did not materialize field proposals into a roster; S1.3 below adds explicit candidate creation and separate approval.

Existing private history is preserved separately from the clean-history public release candidate. Public delivery is source-code delivery, not a hosted production application or a claim that all long-term milestones are complete.

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

## Workbench migration planning

The [UI migration](docs/UI_WORKBENCH_MIGRATION.md) is now implemented for the shared shell and primary delivery/import/mapping/reconciliation controls using official shadcn Radix Nova and Tailwind 4. Delivery table/inspector, mobile detail return, evidence tabs and route code splitting are connected to existing services. [The migration receipt](docs/evidence/canonical/workbench-migration-2026-11-21/README.md) records checks and limits. Supporting legacy surfaces and measured scale/interaction/owner-human acceptance gates remain open; component-system adoption does not close them.


## Selected UI/performance qualification

The [qualification receipt](docs/evidence/canonical/ui-qualification-2026-11-21/README.md) records production-build measurements at 100/1,000 synthetic records, bounded five-row preview responses with complete counts/tokens, independently inspected full workbooks, actual touch/keyboard/list-detail behavior, repeated-navigation heap observations and a separate slowed CPU/network trial. No 10,000-record run was performed. Python 907 and frontend 144 tests pass; full browser 74 and final affected 16 scenarios pass. The receipt records scope and failures separately. Source/reference demo code was inspected without importing its private Site identity or browser-local storage design.

The new preview reduces transfer but still computes the full snapshot. Primary hover contrast and coarse-pointer target sizing were refined during qualification. Owner visual/human gates and supporting legacy retirement remain separate. The user prioritized this dated qualification before correction features; its release excluded correction/agent-evaluation drafts. The later S1.3 slice is recorded below.

## Latest adaptive release verification

- Python: 906 passed with propagated checkout source path.
- Frontend: 142 passed; production build passed.
- Browser: full 74 passed; final affected 18 passed after layout/interaction updates.
- Synthetic pipeline and installed wheel/sdist journeys passed.
- Privacy-reviewed clean-history candidate has only noreply commit emails and no findings in the release scanner.

See the [release receipt](docs/evidence/canonical/adaptive-release-2026-11-21/README.md) for initial failures, corrected runs and remaining boundaries. Historical counts below remain dated baseline evidence.

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

[ROADMAP](ROADMAP.md) explicitly reschedules PX1/PX3/PX4 into later exchange/research work and maps PX2 evidence to licensing/network milestones. [S1.1](docs/ADAPTIVE_INGESTION_SPEC.md) owns the immediate ingestion/contact target. Existing model/human evidence gates remain open; no recipient compatibility follows from the implemented shell or planned workbook.

## Reviewed correction/export S1.3

Implemented one explicitly selected current office-phone assertion → immutable complete candidate → separate dataset approval → pinned JSON/XLSX handoff. Original bytes, prior approved output and unchanged offices survive; phone extensions and source/link/decision/base lineage remain inspectable in review format 2. Derived jobs cannot be source-reprocessed, and inherited base quality evidence is labeled. Exact retries survive restart; stale source/link/decision/base and conflicting/ambiguous/no-op requests fail.

A subsequent file retains source-to-source history and separately compares previously corrected keys against the effective approved roster. A drift hold requires acknowledgement before separate dataset approval, so resending an old source phone cannot silently erase a local correction. Browser retries handle storage denial and malformed saved payloads. This slice adds no database migration or dependency change.

[The correction receipt](docs/evidence/canonical/correction-export-2026-11-21/README.md) owns final checks, failure disposition, actual two-office UI/download captures, 100/1,000-row correction service checks and production-build measurements. Owner visual approval, participant outcomes, source-specific licensing, bulk/address changes, recipient templates, production model calls and hosting remain outside this engineering slice.

S1.3 qualification: 918 Python tests, 154 frontend tests, production build, 76 full desktop/mobile browser scenarios, synthetic pipeline and installed wheel/sdist journeys passed. Production corrected-roster median populated load was 848/847 ms at 100/1,000 rows, with row-selection p95 lab proxies 33.4/33.5 ms. Complete API/touch-browser workbooks retained every row and extension/decision/source lineage. The receipt distinguishes initial test-fixture failures and concurrent service diagnostics from the final browser measurements.

## Independent external-agent mapping challenge

A case-author agent froze seven synthetic cases and a withheld key before a fresh Terra Medium proposer saw headers, cells and source notes. Six scorable cases produced 54/54 exact field/abstention decisions versus deterministic aliases' 47/54; the seven extra matches were all in one renamed-schema case. Duplicate headers caused whole-case abstention/input rejection. The ambiguous phone stayed quarantined; five complete cases passed separate review/apply/accept. Unapproved apply and unsupported operations were rejected for their intended reasons, and originals/text identifiers were preserved.

[Protocol, full results and limitations](docs/AI_MAPPING_EVALUATION.md) distinguish this one external-agent observation from saved-proposal replay, production-model API quality, general injection resistance and human time savings. The frozen replay is included in CI without a model/API call. [NEXT](NEXT.md) now proposes Tennessee licensing-source S2 planning, awaiting selection; no licensing adapter or migration is claimed.
