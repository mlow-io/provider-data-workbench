# R1 filtered-response integrity — 2026-11-14

Uncommitted working tree on `feat/provider-data-operations-plan`, based on `760acde`. The renewed independent continuation is defined in ROADMAP; [source policy](../../../PUBLIC_DATA_SOURCES.md#filtered-response-integrity-r1) and Q1–Q4 were frozen before implementation. [Checked files](checked-files.json) identify this checkpoint. Model access and human validation remain separate open gates.

## Implemented boundary and verification

`fhir_search.py` separates conservative match/include/outcome checks from native resource/profile validation. Filtered search pages require exact requested match type/ID, explicit includes and checked source outcomes; error/fatal or malformed outcomes cannot hide inside HTTP 200. Missing mode is recorded as an implicit match and must satisfy the same identity rule. Includes without any match fail at publication; empty or warning/information-only searches can complete as empty evidence. All raw responses remain retained. Unfiltered semantics and already completed receipts remain unchanged.

Publication rechecks digest-verified saved pages, including queued pre-R1 checkpoints and restart, without another request. Immutable receipt metadata and publication events retain version-1 query/count evidence. Counts describe raw pages; identical filtered resources give matching entries precedence while every original page/locator remains retained. Native review shows the check report or explicitly states its absence/unsupported version. Acceptance, resource eligibility, standards validation, reviewed identity and approved data remain separate.

| Check | Actual result |
|---|---|
| Initial new boundary suite | **33 failed, one passed**, reproducing prior gaps; [separate failure log](before.txt) |
| Focused new/source suites | **94 passed** before adding the additional omitted-mode precedence variant; [log](focused.txt) |
| `make validate` | Exit 0; **849 Python tests in 161.36 s**, then pipeline passed; [log](validate.txt) |
| `npm test --prefix web` | Exit 0; **134 tests** in 18 files; [log](frontend.txt) |
| `npm run build --prefix web` | Exit 0; TypeScript/Vite; [log](build.txt) |
| `npm run test:e2e --prefix web` | Exit 0; **72 desktop/phone scenarios in 6.3 min**; [log](browser.txt) |

Known TestClient dependency deprecation and Vite main-chunk advisory remain. These are qualification command timings under local load, not product latency measurements. Documentation/whitespace checks are recorded in STATUS after receipt creation. No application code followed the final required checks.

## Q1–Q4 inspected outcomes

`tests/test_fhir_filtered_response.py` has 35 cases for wrong/case-changed/missing identity, malformed/unknown modes, includes and source outcomes, late-page failure, empty results, both explicit/implicit match precedence, old queued revalidation, unfiltered compatibility and exact approved consumer preservation. The existing acquisition suite's 60 cases remain passing. Component cases cover current, absent and unsupported report versions. Browser cases inspect actual query metadata and independent acceptance, then download/hash an ignored-filter HTTP 200 body while its capture stays failed with no intake link, including after reload.

The retained [owned HTTP rehearsal](qualification.json) used two real loopback requests and actual services. A valid filtered response had one matching NORTH Location, two explicit includes (SOUTH and Organization) and one warning outcome. It published the exact expected report, then separate review accepted three eligible reference resources. [The reference packet](reference-packet.json) preserves the report and source entries. The failed request returned NORTH for `ignored-filter`; [its original body](failed-response.json) remained exact/hash-checked with status 200, failed state and no receipt. [Approved before](approved-before.json) and [approved after](approved-after.json) are byte-identical; no work case or current-version pointer changed. Restart preserved the query report; SQLite integrity/foreign keys passed.

Reproduce from an activated checkout using a new root:

```sh
PYTHONPATH=src:tests python docs/evidence/canonical/filtered-response-2026-11-14/rehearse.py .runtime/r1-replay-NEW
```

This is a source-checkout qualification script using test helpers, not an installed product command. The first rehearsal attempt passed a relative inbox path and was refused by the existing absolute-inbox guard. Its partial owned root was preserved; the corrected script resolves its new root before setup. No product change was needed for that failure.

[An offline audit](prior-live-page-audit.json) also applied the rule to the previously captured actual HAP Location page: one explicit match, no includes/outcomes, original hash verified. It made no source request, new receipt or alteration to the old acceptance/metadata. It does not claim new live freshness or broader source compliance. All public rehearsal packets/screenshots are synthetic; actual source payloads remain outside Git.

Inspected [desktop](ignored-filter-wide.png) and [phone](ignored-filter-mobile.png) screenshots show the failed scope and downloadable response without an acceptance path or horizontal overflow. R1 closes Q1–Q4's engineering boundary. Actual-model A1/A3, human H1/H2 and R2–R4 remain unfinished. Next is the bounded graph qualification in [NEXT](../../../../NEXT.md).
