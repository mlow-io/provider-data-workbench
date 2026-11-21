# Implementation status

Updated 2026-11-21. This is the current summary; dated receipts hold historical details. [NEXT](NEXT.md) selects work, [SPEC](SPEC.md) defines behavior and [ROADMAP](ROADMAP.md) holds future scope. The documentation/code audit is complete. A report-pinned, filterable correction comparison is implemented; licensing implementation has not been selected.

## Implemented application

| Capability | Boundary |
|---|---|
| Intake and adaptation | CSV/XLSX, declared JSON/FHIR subset, bounded sources, reviewed recipes, compatibility/drift and optional mapping proposals |
| Identity and investigation | Separate clinician/office links, source-scoped comparisons, local field decisions, contact assertions and preserved history |
| Managed delivery and correction | Quality holds, current approved roster, reviewed-phone candidate, separate dataset approval and subsequent correction-drift review |
| Review and exports | Bounded previews, complete approved JSON/XLSX with extensions/source/decision lineage; complete candidate quality-report review |
| Workbench UI | Responsive shadcn/Tailwind shell and primary review/import/mapping controls; supporting legacy surfaces remain |
| Recovery/distribution | Retry/restart, stale-write guards, retained earlier output and installed wheel/sdist journeys |

This is a local prototype, not hosted multi-user software. Local approval/contact/submission assertions do not establish independent verification or a payer update. Existing bounded network intake/review is distinct from planned expanded network analytics.

## Current verification

The audit slice passed **920 Python tests, 155 frontend tests, production build and 76 full desktop/mobile browser scenarios**. After applying the existing download-link styling, the frontend/build checks and two affected correction browser scenarios passed again. Pipeline validation, frozen mapping replay, installed wheel/sdist journeys, documentation links and whitespace checks also passed. [The audit receipt](docs/evidence/canonical/documentation-code-audit-2026-11-21/README.md) maps findings to fixes and checks.

The preceding public `2ca2219` baseline is independently recorded in [GitHub CI](https://github.com/mlow-io/provider-data-workbench/actions/runs/44904046200). Historical results remain in dated receipts; they are not substitutes for checks on changed code.

## Audit outcome

Removed stale active-P0 instructions, repeated process text and competing “latest” sections. Preserved historical receipts and acceptance IDs. Added complete preapproval quality evidence for discrepancies outside the 50-entry sample, rejected unscored mapping targets before synthetic replay review, and removed duplicate evidence reconstruction within one discovery transaction. No schema migration, dependency version change or new infrastructure was needed.

## Recorded performance scope

[The correction receipt](docs/evidence/canonical/correction-export-2026-11-21/README.md) identifies the measured 100/1,000-row build: 848/847 ms median populated load and 33.4/33.5 ms p95 event-to-frame lab proxies. Preview transfer was about 12.4 KB; full server snapshot work remains data-dependent. These earlier measurements were not rerun or presented as a speedup for this audit. They do not establish field INP, capacity or leak freedom.

## Model evidence

The [independent external-agent challenge](docs/AI_MAPPING_EVALUATION.md) scored 54/54 target-field decisions versus aliases' 47/54 across six scorable cases; all seven additional matches came from one renamed-schema case. Duplicate headers caused whole-case abstention and the ambiguous phone stayed unaccepted. Five complete cases passed separate synthetic review/apply/accept. The frozen replay is deterministic service verification, not another inference trial.

Production-model client quality on its frozen corpus, broader generalization and observed human time savings remain unverified. The existing optional client stays experimental; no model access is required for manual operation.

## Remaining work and evidence gaps

- **Owner/human evidence:** visual acceptance and uncoached participant outcomes remain open. The [walkthrough](docs/INVESTIGATION_DEMO.md) and [observer kit](docs/OPERATIONS_DEMO.md#h2-prepared-state-observer-kit) are available; agents and tests cannot substitute for participants.
- **Selected UI limits:** supporting legacy surfaces, comprehensive accessibility and long-session behavior are not closed by the bounded 100/1,000 qualification.
- **Source/model scope:** no licensing-board integration, statewide completeness, broad conformance or production-model benefit is claimed. New coverage needs a named source/contract and its own evidence.
- **Future features:** S2 licensing/expanded identity planning remains proposed. Network expansion, bulk/address corrections, research, recipient templates and hosting are later work in ROADMAP, not current defects or automatic next actions.

[The evidence index](docs/evidence/canonical/README.md) links adaptive release, migration, qualification, correction, mapping and older FHIR/operations/distribution records. Older counts and failed attempts remain in those dated records rather than competing with this summary.

## Correction comparison paging — 2026-11-21

Operators can filter the complete persisted corrected-roster comparison by status and page through it before dataset approval. The page endpoint requires the inspected report hash; mismatches return a conflict. Full counts and the existing complete JSON report remain available. Tests cover a changed 51st office, filtered/empty results, invalid limits/status and stale hash, plus actual desktop/mobile review. Python 920, frontend 155, production build and full browser 76 passed. The service currently reads the complete persisted report before slicing; no constant-time or capacity claim is made.

## Office-scoped handoff — 2026-11-21

The approved handoff UI can select an exact source-native office ID or the entire roster. It validates response scope and carries the same ID and snapshot token through JSON/XLSX downloads; changing the selection clears earlier download eligibility, including an in-flight preview. Unknown offices return an error. The backend office scope and its complete workbook semantics were already implemented.

Frontend 158 and production build passed on the final rerun. The full browser run had 75 passes and one desktop three-source identity-review timeout; that exact case passed on an isolated rerun. Final scoped JSON/XLSX correction journeys passed separately on desktop and mobile. A repeated frontend run initially had two unrelated timing failures under load; the full rerun passed. No new backend semantics or measurements are claimed.
