# Documentation and code audit — 2026-11-21

Baseline: public `2ca2219`. Two bounded GPT-6.1 Terra reviewers at extra-high effort inspected active documentation/authority and intake–review–export/mapping code paths. The lead reconciled their evidence and implemented the changes below. This is a targeted audit, not exhaustive security, standards or codebase certification.

## Findings and disposition

| Finding | Change |
|---|---|
| Completed P0/UI planning still described as active | Rewrote current entrypoints and labeled stage plans historical; current request/NEXT selects work |
| Several competing “latest” results and old evidence index | STATUS owns one current summary; README/index link dated receipts instead of repeating old counts |
| Repeated process and future-stage boilerplate | Consolidated working rules in AGENTS and behavior in SPEC; ROADMAP holds proposed scope, not automatic authorization |
| Candidate discrepancy after entry 50 unavailable before acknowledgment | Added a complete quality-report attachment for all version states; retained approved consumer-export gate |
| Evaluation synthetic reviewer ignored unscored extra target fields | Reject undeclared fields before creating replay storage; original frozen proposals/results remain unchanged |
| Discovery rebuilt the same field view twice per scope | Reuse it inside the same read transaction; creation/approval still reconstruct fresh evidence |
| Demo runtime prefix carried preparation terminology | Renamed new default roots to `workbench-demo-*`; existing roots remain resumable |

Historical receipts, failed/rerun observations, stable acceptance IDs and PROJECT_STATE redirects were retained. Git already preserves earlier prose; no duplicate archive copy of every rewritten entrypoint was added.

## Concrete checks

`tests/test_feed_quality_report.py` seeds 51 already-corrected synthetic keys, then processes a real later delivery. Its only changed key is after the first 50 displayed entries. The complete HTTP report exposes that key before approval, retains version/report pins, changes no database/current pointer, and does not enable candidate consumer export. The seeded baseline does not claim a new 51-decision materialization qualification.

For `tests/test_independent_mapping_evaluation.py`, a replay proposal adds the supported `reference_phone` field from Fax while all nine scored fields remain correct. The pre-audit runner was observed accepting it as 9/9 and committed; the new runner rejects it before storage. This is evaluation-review hardening, not evidence that the original model trial included an extra field or that production AI could approve datasets.

The correction browser journey now downloads the complete candidate report through the UI before separate dataset approval. Complete comparison values are review evidence, not a confidentiality boundary or an approved roster envelope.

## Verification

- Python: **920 passed** in 99.60 seconds with invocation-owned fixtures.
- Frontend: **155 passed**; production TypeScript/Vite build passed.
- Browser: **76 passed** in the full desktop/mobile run; after existing download-link styling, the two affected correction journeys passed again.
- Pipeline: `make -o test validate` passed, reusing the immediately preceding unchanged Python test result.
- Frozen replay: 54/54 versus aliases' 47/54 remains unchanged; no model call occurred during replay.
- Wheel/sdist: clean installed journeys passed. Documentation link checks and `git diff --check` passed.

The five active entrypoints (AGENTS, README, STATUS, SPEC, ROADMAP) were shortened by approximately 56% using whitespace-separated word counts against the baseline. This measures reduced reading burden, not correctness. The demo root prefix change preserves explicit resume paths. No live provider acquisition, dependency version change or 10,000-record workload was part of this audit.

The actual report download was exercised before candidate approval. Populated captures: [desktop](quality-review-wide.png), [narrow](quality-review-mobile.png). Screenshot inspection is distinct from owner visual acceptance. Tests used new owned storage and warm dependencies; failed setup expectations were kept separate from successful results.

## Remaining work

- Owner visual acceptance, uncoached participant outcomes and production-model client usefulness remain open evidence categories.
- Tennessee licensing-source S2 is still proposed; expanded network analysis, bulk/address changes, recipient exchange and hosting remain later scope.
- Full snapshot construction and per-scope evidence reconstruction still have data-dependent cost. The duplicate call was removed, but no new speedup, leak-freedom or capacity claim was measured. Profile a demonstrated bottleneck before adding caches/infrastructure.
