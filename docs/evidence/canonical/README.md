# Verification records

The latest implementation qualification is [the 2026-11-15 integrated review](integrated-review-2026-11-15/README.md): 869 Python tests/pipeline, 134 frontend tests/build, 72 browser scenarios, inspected exports and both installed distribution journeys. [STATUS](../../../STATUS.md) owns the current summary. Dated records retain their exact revisions, failures, reruns and scope; earlier counts below describe the earlier candidate.

| Area | Record |
|---|---|
| FHIR parser and standards | [Initial validation](fhir-parser-2026-11-14/README.md), [online terminology controls](fhir-terminology-2026-11-14/README.md), [whole-graph qualification](provider-graph-2026-11-14/README.md) |
| Native integration | [Intake/acceptance/export](fhir-native-intake-2026-11-14/README.md), [web journey](fhir-web-2026-11-14/README.md) |
| Source acquisition | [Readiness](fhir-network-readiness-2026-11-14/README.md), [controlled capture](fhir-acquisition-2026-11-14/README.md), [limited live capture](fhir-live-boundary-2026-11-14/README.md), [filtered response checks](filtered-response-2026-11-14/README.md) |
| Optional assistance | [Client engineering and frozen evaluation](mapping-assistant-2026-11-14/README.md); actual-model evaluation remains open |
| Complete operations | [Consumer, selected evidence and recovery](operations-2026-11-14/README.md), [portable installation](portable-distribution-2026-11-14/README.md) |

## Historical M0–M4 candidate

Application integration: 396aaf0. Canonical contracts: 0a295f8. The connected second-delivery rehearsal is in 409fbd8. This candidate descends from public main 572f891; private ancestry and runtime records are excluded.

## Completed local checks
- Fresh virtual-environment setup with editable dev/MCP installation and npm ci.
- Initial assembled application: 579 Python tests and pipeline validation passed; 114 frontend tests and production build passed; full desktop/phone browser suite passed 54 scenarios.
- Focused outreach API/export regressions passed. An initial two-viewport test attempt used an incorrect exact label locator; the corrected role locator passed both widths. The application did not record an action during that failed test setup.
- The retained complete investigation now includes an incomplete second delivery, two NORTH observations, two outreach entries, simulated submission, a separately observed mismatch/reopen, unchanged SOUTH and preserved state after restart. The restored phone-review report matches the original. JSON and XLSX were inspected; formula cells were absent.
- Existing challenge/held-out/generated matching metrics remain unchanged. The supplemental authored fixture has 11 address records and eight candidates: all three authored clinician pairs are retrieved, two satisfy strict eligibility; one known nonlink and one unresolved clinician pair remain suggestions for review. Partial labels do not support overall precision.
- Matching and impact summaries, the investigation receipt and inspected synthetic [desktop](investigation-wide.png)/[phone](investigation-mobile.png) screenshots are retained alongside this file.

## Final candidate qualification

[GitHub CI run 41723418456](https://github.com/mlow-io/provider-directory-workbench/actions/runs/41723418456), head 5848d6e, passed 580 Python tests, pipeline validation, documentation checks, 114 frontend tests, production build and all 54 desktop/phone browser scenarios. This includes the connected second-delivery investigation. Application/rehearsal code is unchanged in the follow-up evidence/status commit.

The final local Python attempt had 579 passes and one existing receipt-stage crash-test subprocess timeout under severe machine load. The isolated test passed in 6.02 seconds and pipeline validation passed afterward. A concurrent local browser attempt encountered a timeout and was explicitly interrupted; the strengthened focused investigation subsequently passed both desktop and phone. These failures and the initial full 54-pass run remain separate evidence. Full final candidate qualification comes from the remote run above.

The retained complete-investigation root contains two source artifacts. Backup, verify and restore passed, and the restored SQL phone-review report matches the source. Its two open cases remain one report row each; selected NORTH lineage includes both retained source rows. The complete workbook was inspected and contains no formula cells. Browser screenshots show the matching-verification branch; the retained CLI rehearsal demonstrates the contradictory-observation/reopen branch.

The first candidate CI run [41721168687](https://github.com/mlow-io/provider-directory-workbench/actions/runs/41721168687) had 53 browser passes and one mobile overlap failure. The trace identified overflowing target-search controls; the responsive sizing fix and explicit horizontal-overflow regression passed the focused mobile journey before the clean full CI above.

One upstream Starlette TestClient deprecation warning was observed with the fresh dependency installation; it did not fail qualification. Contact/response/submission/verification identities remain local assertions. All data is synthetic; no actual outreach or payer update occurred. No human usability walkthrough has been observed.
