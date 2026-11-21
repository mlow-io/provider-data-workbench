# Operator workflow and PX0 contract — 2026-11-19

Local UI1 change set based on `52a6f4f7168115719674c19b0b2182abf4cd943c`, branch `feat/provider-operations-ui`. [File hashes](implementation-files.json) identify the final source/test inputs; no publication or hosted deployment is claimed. The [operator contract](../../../OPERATOR_EXPERIENCE.md) and [provider-operations contract](../../../PROVIDER_OPERATIONS_CONTRACT.md) define separate delivered UI and future domain scope.

## Delivered

A shared desktop/narrow-width shell makes daily work primary: Work queue, Receive data, Deliveries and Provider records. Sources and legacy workflows remain accessible with their original route IDs. The default entry is work. Task headings replace slogans; source-row counts do not imply human review.

Delivery review precedes source configuration and processing diagnostics. A bounded typed comparison shows source keys, changed fields, missing keys, unavailable checks and original evidence access. Presence flags preserve absent versus null versus empty text. Interpretation-change notices distinguish mapping changes from source changes. Selected context includes the real delivery period and retained designation/notice. Approval, risk acknowledgment, consumer publication and observed correction retain existing separate service meanings.

PX0 adds a design baseline and independent synthetic response fixtures: exact-key correlation, file/item outcomes, contradictions, repeats, stale context, source-native enrollment/NPPES relationships, shared research budgets and recipient packets. These are not new runtime adapters, endpoints, migrations, model evaluations or live integrations.

## Checks and preserved failures

- Two baseline Chromium captures passed before layout changes, covering feeds/intake/work at desktop and phone widths.
- The first frontend run had 134 passes and two failures caused by duplicate feed-name headings. The [corrected run](frontend-rerun.txt) passed all 136. A later [heading assertion failure](frontend-heading-failure.txt) had 135 passes/one failure; updating the old correction-page wording yielded [136 passes](frontend-final.txt).
- The [full browser suite](browser-full.txt) passed 74 scenarios before the final evidence-display fixes. After those fixes, the [affected run](browser-affected-first.txt) passed 18/22; four correction cases still used the old heading assertion loaded by that test process. The unchanged behavior passes the [fresh four-case correction rerun](browser-correction-rerun.txt). Do not describe the failed 22-case invocation as a complete pass.
- [Final operator-only keyboard/responsive checks](browser-operator-final.txt) passed 2/2 after the skip-link presentation adjustment.
- The [production build](build.txt) passed. The existing large-chunk advisory remains; it is not a build failure.
- Two JSON and four CSV design fixtures parsed with independent expected outcomes and exact eight-column headers; this does not test a response parser or live recipient compatibility.
- Documentation check passed 72 Markdown documents with zero local-link/entrypoint errors; git diff --check passed. Python/pipeline/distribution/profile suites were not rerun for this frontend/documentation-only slice; their older receipts remain historical.

The browser cases inspect actual serialized approved JSON and scoped JSON/XLSX downloads, stale/retry behavior and NORTH/SOUTH isolation. They use invocation-owned synthetic roots, controlled loopback sources/providers and no actual recipient transmission or real-model trial. The new operator case exercises skip-to-content, focus indication, browser back, delivered navigation, primary target height and horizontal page overflow. It is not a full accessibility certification or uncoached usability study.

## Captures and limits

- Baseline: [desktop work](before-work-wide.png), [phone work](before-work-mobile.png).
- Current shell: [desktop work](work-wide.png), [phone work](work-mobile.png), [desktop receive](receive-wide.png), [phone receive](receive-mobile.png).
- Delivery review: [desktop held candidate](held-delivery-wide.png), [phone held candidate](held-delivery-mobile.png).

These are real synthetic runtime captures, not mockups. Long-form workflows still need subsequent provider/case/exchange refinement. H1/H2, actual-model A1/A3, real recipient/source compatibility and measured human usefulness remain open. Original runtime logs, downloads and failure traces are retained outside Git; the linked text copies replace machine-local paths. No personal preparation or conversation content is included.
