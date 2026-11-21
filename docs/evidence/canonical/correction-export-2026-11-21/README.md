# Reviewed correction/export receipt — 2026-11-21

This slice implements [S1.3](../../../FIELD_MATERIALIZATION_SPEC.md): one reviewed office-phone assertion becomes an immutable complete roster candidate; a separate dataset approval rechecks the base, identity links, field decision and selected source. It preserves original bytes, prior approved versions, unrelated offices, local decision history and leading-zero extensions. [Review export format 2](../../../REVIEW_WORKBOOK_CONTRACT.md) includes complete JSON and an optional Reviewed corrections worksheet with selected-source/decision lineage.

## Requirement to check

| Behavior | Evidence |
|---|---|
| Exact reviewed office, base, source and current field decision | `tests/test_field_materialization.py`: source/link/decision/base staleness, wrong office, absent/ambiguous row and digest tampering |
| Candidate is separate from approval | Service test and actual desktop/mobile `correction-journey.spec.ts`: current pointer unchanged through creation; approval changes it |
| Repeat/restart does not duplicate work | Same-key request/approval retries after reopening storage; different-content and duplicate-selection requests rejected |
| Original and other office survive | Prior approved export bytes/token stable; NORTH changes, SOUTH remains unchanged |
| Complete inspected JSON/XLSX | `tests/test_correction_export.py`, two-office actual browser downloads, and 100/1,000-row service checks with binary XLSX inspection |
| Extensions and source/decision closure | `0042` remains literal text; correction references resolve to selected source receipt/artifact/locator, decision, reviewed link IDs and base |
| Later source cannot silently overwrite correction | Source-repeat case stays source-unchanged but effective-changed; hold requires acknowledgement before separate new approval; matching and invalid cases tested |
| Retry failure usability | UI covers failed refresh, stale rejection, exact saved retry across remount, storage denial and malformed retry records |
| Derived operation boundary | UI labels inherited quality evidence/original-source reconciliation and removes reprocess; service rejects derived reprocessing |
| Bounded display and full populations | Five-row preview arrays share full counts/token; version detail bounds effective-comparison entries at 50 while approved JSON retains the full report |

## Checks

- Python: **918 passed** in 91.56 seconds, with failed-only disposable fixture retention.
- Frontend: **154 passed**; production TypeScript/Vite build passed.
- Browser: **76 passed** in 4.9 minutes in the final full desktop/mobile run.
- Synthetic pipeline: passed through `make -o test validate`, reusing the immediately preceding full pytest result rather than repeating it.
- Distribution: wheel and sdist clean installed journeys passed; new materialization module is included. Generic distribution rehearsals do not replace the dedicated correction tests.
- Functional correction populations: **100 and 1,000** valid rows, one correction each, full independent workbook populations, source closure and restart/pointer checks passed. [Service results](correction-results.json) record single wall-clock diagnostics collected alongside other qualification checks; they are not isolated comparative performance measurements.
- Production corrected-roster browser populations: all declared load, interaction and overflow budgets passed. [Raw measurements](performance.json) retain all trials, slowed conditions, finite heap diagnostics and complete downloads.

| Corrected roster records | Median populated load | Row selection p95 lab proxy | Preview JSON bytes |
|---|---:|---:|---:|
| 100 | 848 ms | 33.4 ms | 12,401 |
| 1,000 | 847 ms | 33.5 ms | 12,413 |

The full workbooks retained all 100/1,000 rows plus the correction and literal extension, independently inspected after API and actual touch-browser downloads. These values are one machine's reference observations, not cross-version speedup claims. The preceding uncorrected runs also passed; the corrected mode above is the final population receipt.

The first narrow browser attempt reached workbook inspection but the reader rejected a temporary download lacking an `.xlsx` suffix; the test now uses an explicit saved filename. An initial full browser run passed 74 scenarios and failed two intake-search scenarios because the new correction fixture namespace contained an older fixture’s substring. The new fixture now uses a distinct roster namespace; the final full rerun passed all 76 scenarios. Failure evidence is retained privately. The final checks do not use live provider sources or production-model API calls. No storage schema or dependency change was introduced.

## Reproduce

Use the documented warm project dependencies and Chromium installation:

```sh
PYTHONPATH=src pytest -q -o tmp_path_retention_policy=failed
npm test --prefix web
npm run build --prefix web
npm run test:e2e --prefix web
make -o test validate
PYTHONPATH=src python3 scripts/qualification/corrections.py --root /tmp/provider-correction-new
node web/qualify-performance.mjs /tmp/provider-correction-ui.json --corrected
python3 scripts/check_distribution.py --root /tmp/provider-correction-package-new
```

Use new invocation-owned roots. Run timing separately from resource-heavy suites. Setup is excluded: corrected-mode qualification creates/reviews identity links and a selected phone through the actual services, creates and separately approves a complete candidate, then measures the resulting 100/1,000-row workbench through actual HTTP. Both API and touch-browser workbooks are opened independently and checked for the correction and extension. Default uncorrected qualification remains available without `--corrected`. Retain compact evidence and failed/pinned results, then retire only the owned runtime storage. No 10,000-record run is selected.

## Interpretation and remaining limits

Phone number and extension remain one assertion. Office identity is reviewed independently; equal NPIs do not select an office. Existing source observations remain immutable. A later source delivery therefore has two explicit comparisons: source-to-source history and incoming values against approved local corrections. Acknowledging the drift hold records a risk decision; it does not approve the delivery. Approval is still local dataset release, not provider verification or payer writeback.

The candidate inherits the approved base's quality report and acknowledged holds, with an explicit UI notice; those comparison counts describe the base, not a newly calculated correction delta. Correcting the same row again replaces the latest row ledger entry but retains the prior immutable result through base_version. A rejected selection needs a new field decision before another candidate under a new key. Browser session storage improves retry recovery; when unavailable, only the in-memory request survives and the UI says so.

Reference cold-load and event-to-second-frame measures are local lab results, not field INP, asynchronous completion guarantees, server capacity or human time savings. The bounded preview still computes the complete server snapshot. Owner visual approval, uncoached participant outcomes, licensing/network workflows, bulk/address corrections, production-model quality and hosting remain separate gates.


## Populated captures

- [Desktop correction selection](wide-correction-choice.png) and [approved correction preview](wide-approved-correction-preview.png).
- [Narrow correction selection](mobile-correction-choice.png) and [approved correction preview](mobile-approved-correction-preview.png).
- Later source-drift hold: [desktop](wide-effective-drift.png), [narrow](mobile-effective-drift.png).
- Corrected 1,000-row measured handoff: [desktop](delivery-1000-desktop.png), [narrow preview](export-1000-narrow.png). The independently downloaded workbook contains every row even though the preview is sampled.

All captures use synthetic fixtures. Page overflow, keyboard table scrolling, touch targets and list/detail focus have engineering checks; screenshot inspection is distinct from owner visual acceptance.


## Follow-up: attribution loading guard

A prior Linux CI trace showed an empty Reviewer after an attempted fill while a selected delivery was loading. Inspection found an editable attribution placeholder that was replaced when the selected version arrived. A deterministic delayed-response regression reproduced that exposed editing window. The placeholder now shows progress without editable attribution; review fields become available with the actual selected evidence. This closes the unstable input lifecycle rather than increasing a timeout or weakening review requirements.

The regression failed before the fix and passes after it. The full frontend suite now has **155 passing tests**, the production build passes, and **10 affected desktop/mobile delivery/correction browser scenarios pass** after the guard. The earlier full local run passed 76 scenarios. No backend/contract/dependency change was made. Population timing/screenshots above identify the preceding populated-workbench build by asset hashes; the small loading-state follow-up was not presented as a new performance measurement.
