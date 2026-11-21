# Workbench UI qualification protocol

Selected 2026-11-21: qualify the actual review/export workflow at **100 and 1,000 records**, finish bounded previews and fix observed interaction issues before correction features. Do not run 10,000 records. [The dated receipt](evidence/canonical/ui-qualification-2026-11-21/README.md) owns observed results and captures; the [migration contract](UI_WORKBENCH_MIGRATION.md) retains broader visual requirements.

## Reproduce

Install the documented project Python dependencies and frontend dependencies, with the existing Playwright Chromium runtime available. From the repository root:

```sh
npm run build --prefix web
node web/qualify-performance.mjs /tmp/provider-ui-qualification.json
PYTHONPATH=src pytest -q -o tmp_path_retention_policy=failed
npm test --prefix web
npm run test:e2e --prefix web
```

Run the benchmark without concurrent heavy test suites. It creates an invocation-owned root, builds two synthetic CSV/profile/feed/approval fixtures using actual services, starts a loopback API and serves the production bundle through a preview proxy. It never reuses user storage. The Python fixture helper rejects existing roots. The runner closes only its browser/server processes and retains measurements/captures/downloads in its owned root. The output JSON path is explicit; keep raw machine-local runtime paths outside Git. Preserve failure evidence and resolve disk/setup failures before interpreting results.

## Method and budgets

- Five fresh browser contexts per population: time navigation to the populated approved-delivery heading and available preview action. Setup is excluded. Report all trials, median and range; reference maximum target 3 seconds.
- Thirty actual row selections and thirty evidence-tab changes: capture pointerdown through two animation frames. Typing uses trusted keyboard events and the same two-frame proxy. Reference p95 target is 200 ms for these local interactions. These are lab responsiveness proxies, not field INP or asynchronous completion latency.
- Measure complete versus bounded-preview HTTP bytes/timing, exact complete counts, matching tokens and actual workbook values. Independently open API and touch-browser downloads; five displayed rows must not truncate 1,000 exported rows.
- Record long-task durations and forced-GC heap before/after 20 workspace switches. Lazy-route/module warming and caches can explain retained growth; a finite sample is not a proof of no leak. Work-queue typing is explicitly over the pooled fixture, with a 200-match rendering cap after filtering.
- Run one diagnostic cold load with 4× CPU slowdown, 150 ms latency and 5 MiB/s bandwidth. Keep this separate from normal trials and avoid deriving capacity from one sample.
- Inspect desktop/intermediate/narrow views, an actual touch context, 44 px primary actions, keyboard list/detail focus, reduced motion and complete downloads. The browser regression checks hover contrast after transitions settle and verifies Arrow Right on the focusable preview scroll frame. Delayed list-focus restoration must not override the operator moving to another control. No page-level overflow; wide tables scroll within their regions.

After capturing and checking results, stop the owned servers and retire the invocation storage directory; keep important compact JSON/captures/downloads and failed or pinned evidence. Reuse the installed dependencies and production build until inputs change.

HTTP endpoint timing uses five sequential warm requests after loading the page; it is separate from the cold-page trials. Transfer sizes describe decoded JSON bodies, not compressed network payloads.

The runner exits nonzero on population/token/export mismatch, required interaction failure or failed declared load/feedback/overflow budgets. It records expected limitations rather than replacing them with a score.

## Requirement disposition

| Requirement | Engineering disposition |
|---|---|
| WM-01–06 | Shared shell/task, state guards, primary control states, responsive navigation and complete pinned output covered by component/service/browser checks and actual populated captures |
| WM-07 | Primary migrated controls isolated from old selectors; specialized source/remediation styling remains an explicit supporting-surface limitation |
| WM-08 | Captures are reviewable; owner visual acceptance is still open |
| WM-09 | Actual 100/1,000 HTTP/browser reference and diagnostic measurements retained, including bytes and finite heap observation |
| WM-10 | Bounded response declares samples; full counts/hash and complete JSON/XLSX remain authoritative; no client paging changes filter or export scope |
| WM-11 | Selected task checked for responsive/keyboard/touch/reduced-motion/contrast behavior; exhaustive accessibility audit and actual browser-zoom conformance are not claimed |
| WM-12 | Agent rehearsal and discoverable flow retained; uncoached participant outcomes remain open |

## Flow and preview semantics

Choose a source and exact delivery → inspect candidate/approved state and blockers → inspect evidence → open the workbook preview → read complete counts and explicitly sampled rows → download with the expected full snapshot token → inspect complete Directory, Unresolved issues and source details. A stale token clears eligibility and requires a new preview; unknown and unresolved values remain visible. On narrow screens, Back to deliveries restores list access; Enter on a selected version restores inspector focus.

`review-preview` bounds transfer to five rows per section by default, with a maximum requested limit of 50. Counts and snapshot token describe the full export. Section samples are independent, not a complete evidence graph. Rendering limits do not justify calling the server work constant-time; it still constructs the full SQLite snapshot. See [the workbook contract](REVIEW_WORKBOOK_CONTRACT.md).

Correction approval remains separate from dataset approval. This qualification does not implement corrected-candidate materialization. Supporting source tools, broader data semantics, real-model evaluation and human observation continue under their own contracts. Roll back frontend and backend together to the preceding qualified revision if necessary; preserve data/artifacts. This slice adds no schema migration.
