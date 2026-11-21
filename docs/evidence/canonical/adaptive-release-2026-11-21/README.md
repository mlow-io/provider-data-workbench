# Adaptive intake and reviewed-output release

Implementation started 2026-11-21 on the existing local operator-shell branch. This receipt records new results separately from historical UI1 qualification.

## Contract and reuse decisions

- S1.1 uses existing retained receipts/attempts, immutable approved recipes and shared services. No duplicate profile store or schema migration is introduced.
- Approved example lookup is scoped by source/profile/dataset scope. Structural drift is reported rather than silently declaring field meaning correct. Reuse produces a proposal, followed by existing preview/approval/application decisions.
- The workbook is a read-only pinned approved-version deliverable; it never applies a pending field proposal. Its new preview snapshot protects download against changed issue context.
- The frontend retains React/TypeScript/Vite and TanStack dependencies. Shared evidence tables and components replace primary raw JSON while retaining original payload access. No component-library migration is claimed.
- A bounded Nashville/TN NPPES read succeeded: three records, six addresses, LOCATION/MAILING purposes. Actual bytes remain outside Git. Registry-reported license entries are unverified source assertions.

## Acceptance traceability

| Requirement | Implementation or boundary | Verification |
|---|---|---|
| AI-01/02 | Existing CSV/XLSX/JSON/FHIR parsers and preserved native scopes; new reported-license projection | Existing ingestion/FHIR suites plus source-adapter regressions |
| AI-03 | Bounded actual NPPES Tennessee subset; no claim of state board or payer qualification | Actual-source metadata above; synthetic replay tests |
| AI-04/05 | Approved-example compatibility/reuse through onboarding HTTP/MCP and normal proposal review | New reuse, drift, stale and invalid-state tests; actual-model evaluation remains open |
| AI-06/07/10 | Existing independent clinician/office links, immutable approvals and recovery | Existing two-office/repeat/restart and held-consumer regressions |
| AI-08 | Approved-directory review workbook and snapshot preview | Independent workbook-cell/source/count/scope/concurrency tests |
| AI-09 | Shared readable evidence UI, compatibility diagnostics and approved export controls | Frontend/build/browser results recorded after completion |

## Qualification

Final backend: `PYTHONPATH=src python3 -m pytest -q` passed **906 tests in 96.82 seconds**. Final frontend: 142 tests passed and production build passed. Full isolated desktop/mobile browser suite passed 74 scenarios; following compact-layout and assisted-context updates, the affected 18-scenario run passed. The final screenshot/contrast operations pair passed two scenarios. The existing build chunk-size advisory remains nonfatal.

`PYTHONPATH=src python3 scripts/run_validation.py` passed the owned synthetic pipeline: 12 records, 11 issues and six field discrepancies. `scripts/check_distribution.py` passed wheel and source-distribution installed journeys twice, including a final backend snapshot. Documentation links, bundled asset parity and whitespace checks passed.

Initial bare pytest attempts resolved an older installed package in subprocesses and failed; corrected runs explicitly propagated `PYTHONPATH=src`. Initial browser failures were outdated raw-JSON assertions and the same subprocess path issue; corrected assertions inspect readable field values and actual workbook downloads. A final visual check identified primary-button hover contrast; its selector was fixed and affected browser checks passed. No failed attempt is presented as a first-pass success.

Cross-scope regressions independently inspect workbook cells, separate organizations with repeated native IDs, historical foreign evidence exclusions and same-clinician/multiple-office keys. Work identity now includes canonical dataset scope and reuses legacy cases only when their initial scope matches; no history migration or rewrite occurs.

 Human usefulness, actual-model quality, full licensing-board support, new network analytics, bounded research and recipient exchange remain separate roadmap work.

## Public release preparation

Technical changes use focused Git commits with GitHub noreply metadata. Existing private history is preserved; a separate clean-history release candidate excludes ignored preparation/runtime directories and removes career-purpose narrative from published documentation. Release privacy checks cover tracked private file types/directories, personal home paths, personal email-provider addresses, key material and all commit author/committer emails. These checks supplement diff/content review; they are not a claim of comprehensive automated PII detection. Actual-source response bytes and local receipts remain private.

## Remaining work

This release implements the bounded S1.1 workflow, not the full long-term roadmap. Native-profile semantic adaptation, explicit example revocation, a licensing-board source adapter, expanded network analysis, case research, recipient templates/responses and an independent hosted consumer remain planned. Actual-model benefit and uncoached-human outcomes remain unverified. Field decisions do not automatically alter the approved Directory; a future explicit candidate-materialization/approval contract is required.

## Captured synthetic interface

Lead-inspected running screenshots: [delivery overview](delivery-overview.png), [approved export desktop](approved-export-wide.png), [approved export narrow viewport](approved-export-mobile.png). Screenshots contain authored synthetic examples. Horizontal evidence tables scroll within their own region at narrow widths. Automated checks and these captures do not establish uncoached user success.
