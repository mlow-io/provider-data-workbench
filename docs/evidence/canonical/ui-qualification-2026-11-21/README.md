# UI and performance qualification

2026-11-21. Selected scope: approved delivery review, bounded workbook preview, evidence selection, list/detail return and complete workbook handoff at **100 and 1,000 synthetic records**. No 10,000-record performance qualification was run. [The protocol](../../../UI_QUALIFICATION.md) defines method and limits; [performance.json](performance.json) retains raw trials, measurements, actual build hashes and environment without machine-local paths.

| Records | Median first useful page | Row selection p95 | Tabs p95 | Filter typing p95 | Preview body | Slowed load |
|---|---|---|---|---|---|---|
| 100 | 876 ms | 31.5 ms | 31.7 ms | 31.6 ms | 10,964 B | 1339 ms |
| 1,000 | 858 ms | 31.5 ms | 31.5 ms | 32.0 ms | 10,976 B | 1545 ms |

Reference: Apple M4, 16 GiB RAM, macOS release 27, Chromium 151, production build and loopback API. Five fresh-context cold loads per population; 30 trusted-pointer row selections and 30 tab changes; 43 filter keystrokes. Feedback timing is event-to-second-animation-frame, a lab proxy rather than field INP. The 4× CPU/150 ms latency/5 MiB/s case is one separate diagnostic trial per population. It is not a statistical capacity or throughput estimate.

Full JSON bodies were 201,042 bytes at 100 and 1,993,949 bytes at 1,000; sampled bodies were 10,964 and 10,976 bytes. Preview and complete export tokens/counts matched. The server still constructs/hashes the full consistent snapshot, so transfer bounds do not imply constant server work. Work queue typing uses the pooled 1,100-case fixture; its API returns all work and its UI shows up to 200 matches after filtering. It is not a population-isolated work-queue throughput test.

Both API and actual narrow-browser XLSX downloads were independently opened with openpyxl: 100/1,000 Directory rows, complete population and preserved leading-zero ZIP strings. The actual touch context measured 44 px primary actions. Arrow Right on the focused preview frame now scrolls the actual table; delayed return focus respects an operator who already moved to another control. Keyboard return-to-list and Enter-to-detail focused the inspector; reduced-motion operation worked. Checked desktop/intermediate widths and narrow reflow showed no page-level overflow. Five issue rows remain samples, not the unresolved population.

No >50 ms long tasks were observed during the recorded fifth cold load/selection/tab windows. After 20 workspace switches, forced-GC retained heap grew roughly 2.2 MB while another route and its modules/caches loaded. One before/after diagnostic cannot prove leak freedom or long-session stability. The report retains exact values.

## Checks and failures

- Python: **907 passed**, using `PYTHONPATH=src pytest -q -o tmp_path_retention_policy=failed`.
- Frontend: **144 passed**, production build passed.
- Browser regression: **74 passed** in the full stable run. **16 final affected scenarios passed** after the keyboard scrolling/focus refinement.
- Primary button hover strengthened from 80% to 90% color opacity; browser regression checks rendered normal/hover text contrast and mobile target size.
- Initial fixture setup and a full Python run encountered disk exhaustion/I/O errors. Disposable scratch/evidence was archived and verified outside Git; the successful rerun retained only failed-test scratch. Those failures remain environment evidence, not passing checks.

## Inspected synthetic flows

[100-record delivery](delivery-100-desktop.png) · [1,000-record delivery](delivery-1000-desktop.png) · [100-record narrow export](export-100-narrow.png) · [1,000-record narrow export](export-1000-narrow.png).

The separate browser-local CRUD reference was inspected through its source and recent chat. Compact tables, explicit export scope, keyboard-accessible row actions and local conflict feedback informed this review. Its browser-local persistence and best-effort concurrency were not copied into the provider ledger. No private Site identifiers, account metadata or source files are published here.

## Boundaries

This closes the selected automated engineering checks at the declared populations. Owner visual approval and uncoached-human usefulness remain separate open evidence gates. Supporting legacy tool styling is not exhaustively retired; no broad WCAG conformance, source-wide validity, production-model benefit, multi-user hosting or beyond-1,000 scale claim follows. Correction-candidate and coached AI-evaluation drafts are excluded from this release following the owner's UI/performance-first direction. No schema change, actual-model invocation or source acquisition accompanied this slice.

Final interaction refinements have independent checks: a deterministic focus-race component test and browser/production-harness checks for keyboard horizontal scrolling. An initial linked-dependency dev run could not serve local fonts through Vite's filesystem allow list; installed dependencies were cloned locally without version or permission changes before the full 74-scenario run. Raw invocation stores are disposable after compact results and important captures have been verified; preserve failed/pinned evidence separately.
