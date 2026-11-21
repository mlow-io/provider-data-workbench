# D4 combined operations qualification — 2026-11-14

Local uncommitted working tree on `feat/provider-data-operations-plan`, based on `760acde`. [Checked file digests](checked-files.json) identify the qualified code, fixtures, contracts and retained outputs. This qualifies D4.1/D4.2's source-independent no-model engineering route under the documented fallback. It does not close actual-model A1/A3 or human H1/H2. The original M0–M4 evidence remains unchanged.

## Commands and results

| Check | Actual final result |
|---|---|
| `make validate` | Exit 0; **786 Python tests in 50.19 s**, then pipeline passed (12 records, 11 findings, six discrepancies) |
| `npm test --prefix web` | Exit 0; **130 tests**, 18 files |
| `npm run build --prefix web` | Exit 0; TypeScript and Vite build |
| `npm run test:e2e --prefix web` | Exit 0; **68 desktop/phone scenarios in 2.5 min** |
| `provider-truth-layer rehearse-operations --root NEW_ROOT` | Exit 0; complete retained CLI journey, actual consumer subprocess and stopped backup/restore |

The [Python/pipeline](validate.txt), [frontend](frontend.txt), [build](build.txt), [browser](browser.txt) and [CLI](rehearsal.txt) outputs are retained separately, with checkout paths replaced. The known Starlette TestClient dependency deprecation and 501.84 kB main-chunk advisory remain. Final documentation/whitespace checking is recorded in STATUS after the receipt and current-state edits; no new application code followed these final full checks.

## Inspected artifacts and values

[The rehearsal report](rehearsal.json) names actual immutable IDs and rejected actions. The workbook retained three rows: one eligible SOUTH row and two duplicate-key NORTH quarantines. An unsupported recipe operation was rejected. A reviewed recipe produced the separate approved NORTH/SOUTH clinic delivery. [The approved export](exports/approved.json) and [independent consumer output](exports/consumer.json) contain NORTH `6175550100`/extension `007`, SOUTH `6175550200`/extension `008`, and ZIP `02108`. An incomplete later delivery remained a candidate with missing-key/row-drop holds; promotion and candidate consumption were rejected, leaving the prior approved version and export bytes unchanged.

Saved FHIR retained ten entries, one invalid resource, one unsupported resource and one unresolved reference. The controlled two-page capture retained nine entries, one invalid and one unsupported resource; its completed supported graph had no unresolved reference. Completion describes this bounded query only. Seven owned HTTP requests include the successful pages and explicit 429/later-page/unsafe-link/malformed faults. Failed/partial/waiting captures have no published receipt. Optional assistance was explicitly disabled: one unavailable run, **zero model calls**.

The selected [NORTH field JSON](exports/north-fields.json) and [XLSX](exports/north-fields.xlsx) preserve the preferred payer phone `6175550199` with unknown extension. Fourteen contributing original-page references were checked against exact retained bytes and locators. The two complete original pages are retained under [original-pages](original-pages); their digest filenames match the source references. They remain complete shared source context. Selected field source rows exclude SOUTH Location/Role locators while the original Bundle/pages retain them. No local network binding is inferred.

[The NORTH investigation JSON](exports/north-investigation.json) and [XLSX](exports/north-investigation.xlsx) contain one scoped case, two outreach entries, explicit proposal/approval, simulated submission and separate observed mismatch `6175550100`, leaving NORTH reopened. SOUTH remains unchanged. XLSX payloads were decoded and compared with actual JSON objects; field payload equality and investigation case/contact objects were checked. [The dossier index](exports/north-dossier.json) binds the separate scopes/files by digest rather than merging their decisions.

Restart and stopped backup/verify/restore preserve the pinned consumer bytes, field packet and work payloads (excluding only the descriptive work snapshot timestamp). SQLite integrity and foreign keys and all **12 registered artifact hashes** pass. Repeat delivery creates no second logical acceptance. No user's database or runtime was used.

Inspected [desktop](operations-wide.png) and [phone](operations-mobile.png) screenshots show NORTH reopened, distinct SOUTH work, evidence comparison, separate contact history and case downloads. The connected browser tests independently download approved JSON, invoke the consumer CLI, inspect native invalid/compatibility findings, unavailable assistance, selected field origins and NORTH contact exports, then reload and verify the approved pointer. They do not measure unassisted human performance.

## Acceptance audit

| IDs | Evidence and qualification boundary |
|---|---|
| F1 | `tests/test_fhir_intake.py`: byte/entry bounds, supported/unsupported/malformed/empty cases; raw retention checked in native/acquisition suites. |
| F2 | [Pinned validator receipt](../fhir-parser-2026-11-14/README.md): authored mixed Bundle rejected; standalone Location zero errors/two unavailable-terminology warnings. Profile/terminology outcomes stay distinct. Full terminology/conformance is open. |
| F3 | Parser/store tests retain source-scoped identities, duplicate/unresolved/ambiguous references and unsupported modifiers. Saved unresolved scope is also inspected in this report. |
| F4 | `tests/test_fhir_store.py` preserves native resource acceptance without clinic-required fields; full suite preserves clinic validation. |
| F5 | Parser/store/operations tests inspect independent NORTH/SOUTH expectations and exact support paths; no role/location cross-product or network inference. |
| F6 | Native/store/acquisition tests cover acceptance/repeat/stale transactions, restart and no automatic cases/links/promotion; combined held candidate preserves the approved pointer. |
| F7 | Native/field/operations tests inspect actual selected JSON/XLSX and all contributing references; complete shared Bundle context is labeled. |
| F8 | `web/e2e/native-fhir.spec.ts` and `operations.spec.ts` at desktop/phone widths cover findings/review/export/stale/reload. Automated engineering only. |
| N1 | Acquisition replay plus `operations_rehearsal.py` compare parsed acquired/replayed assertions from the same assembled bytes; original-page digests/locators are independently inspected. |
| N2 | `tests/test_fhir_acquisition.py`, source browser scenarios and combined faults cover 429, later-page/malformed/unsafe references and budgets. New source-wide cooldown regressions cover cancellation, completion, exhausted retries and truncated response failure. |
| N3 | Native/acquisition/process-death tests and combined restart/restore inspect single logical results, append-only history and unchanged approved consumer. |
| A1 | Controlled-provider invocation/review/provenance engineering passes. **Actual-model gate open**: previous eight requested cases unavailable, zero invocation attempts/results; current environment still disabled with no configured API key. |
| A2 | Mapping service/transport/browser negative tests preserve deterministic validation, source permission, stale/cancelled/timeout/invalid handling and manual fallback. Combined journey works with assistance disabled. |
| A3 | [Frozen baseline/requested reports](../mapping-assistant-2026-11-14/README.md) retain eight cases and denominators. **Actual-model comparison open**; unavailable is not an evaluated model outcome. |
| E1 | `tests/test_approved_consumer.py::test_candidate_version_and_later_held_delivery_do_not_replace_prior_consumer` and `tests/test_operations_rehearsal.py::test_pinned_consumer_and_unacknowledged_hold_survive_recovery`; actual browser-download/CLI contacts match independently authored expectations. |
| E2 | `tests/test_operations_rehearsal.py::test_scoped_native_and_investigation_downloads_keep_pages_contacts_and_unknowns`, connected browser tests and stopped restore compare actual NORTH field/contact payloads and preserved SOUTH. |
| H1/H2 | **Open**: no actual uncoached participant observed. Browser success and synthetic invariants do not establish usefulness or time savings. |

D1 bounded engineering, D2 controlled engineering, A2 and no-model E1/E2 have evidence. Live payer interoperability remains open after the separate readiness throttling/version mismatch; no new production probe was made here. F2 explicitly retains unavailable checks; no full Plan-Net compliance claim follows. D3 as a whole remains incomplete until A1/A3 actual access/evaluation exists. These are distinct limitations, not a reason to expand the platform.

## Failures and corrections retained

- Initial independent-consumer tests made incorrect fixture assumptions about ZIPs, nested inbox configuration and candidate ID naming. Expectations were corrected against inspected actual producer contracts; no source data was repaired to satisfy them.
- A strengthened rehearsal initially expected a cross-street location candidate. The matcher correctly excludes different streets; the final scenario instead defers the genuine duplicate-native-key workbook candidate. The failed root remains separate from successful runs.
- Initial operations browser downloads were cancelled because download-attribute requests bypassed page-level proxy interception. The harness now owns a real Vite proxy to its prepared backend; focused two-width, then six-scenario integration, then the full suite passed. Failed outputs were preserved separately.
- Completion auditing reproduced a real source cooldown bypass with two failing regressions. Cooldown now derives across captures of the same configured base, survives cancellation/completion and retains Retry-After even after exhausted/truncated terminal failure. Four cases pass in the final suite. A local publication step is exempt because it performs no request. UI/API expose the source-wide due time.
- An intermediate cooldown regression returned precommit detail (`queued`) and a process-death test mixed its frozen parent clock with a real child clock. The writer now commits before reading detail; the child receives the same explicit clock. The intermediate focused run had one failure/33 passes; the corrected focused tests and final 786-test suite pass.
- One documentation patch failed context matching and changed no files; it was reapplied against inspected lines. An inspection command used an incorrect configuration class name; the corrected availability-only check reported disabled/no key without printing secrets.

Earlier successful 782-test/129-frontend/68-browser checks preceded the cooldown correction and are intermediate evidence. The final counts above include it. Failed invocation-owned roots and browser outputs remain preserved locally; this receipt does not relabel them as clean runs. No external message, actual outreach, model request, user-runtime mutation, publication or deployment occurred.

Next: [the actual-model evidence brief](../../../../NEXT.md). Remaining external/human prerequisites are explicit; additional implementation should address a reproduced defect or an approved next scope.
