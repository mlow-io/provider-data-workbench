# D2.1 bounded FHIR acquisition — 2026-11-14

Local uncommitted working tree on `feat/provider-data-operations-plan`, based on `760acde`. [Checked file digests](checked-files.json) identify implementation/test contents. D2.0 selected-source reasoning and live limits remain in the [readiness receipt](../fhir-network-readiness-2026-11-14/README.md). This receipt maps N1–N3 to controlled-source engineering checks; it establishes neither live provider interoperability nor human usefulness.

## Implemented boundary

One fixed production HAP source, Location/PractitionerRole queries, provider-only destination validation and explicit one-step execution. Schema 12 adds a capture/checkpoint ledger and append-only events, reusing existing artifacts and the shared local OS worker lock. Raw page/reference/error bytes remain distinct from the derived searchset. Resource/field origins retain raw artifact hashes, request URLs, original entry locators and retrieval times. Successful bounded traversal publishes one deterministic native receipt/attempt transactionally, still requiring separate reference acceptance.

The Sources workspace shows configuration/version/limits, queue/run/refresh/cancel, durable state/partial coverage, future retry times, history and original downloads, then links to native review. Creation/refresh/startup perform no source request. Stable unchanged creation IDs recover uncertain responses. Stale cancellation preserves the draft. No incomplete acquisition publishes a ready receipt or replaces approved clinic data. Final native review labels an assembled searchset separately from original response bytes.

## Checks and observed outputs

| Command/check | Result | Boundary |
|---|---|---|
| `make validate` | Exit 0; 712 Python tests in 44.32 s; pipeline passed | 12 records, 11 findings, six field discrepancies; invocation-owned storage |
| `pytest -q tests/test_fhir_acquisition.py` | Exit 0; 28 tests | Controlled loopback HTTP, independent synthetic expected evidence |
| `npm test --prefix web` | Exit 0; 125 tests in 17 files | Creation retry identity, read-only mount/refresh, unavailable configuration, persisted throttle and stale cancellation |
| `npm run build --prefix web` | Exit 0 | Final selector/CSS build; main chunk 501.55 kB advisory remains |
| `npm run test:e2e --prefix web` | Exit 0; 62 scenarios in 2.3 min | Full desktop/phone regression, including four controlled-acquisition journeys |
| `npm run test:e2e --prefix web -- fhir-acquisition.spec.ts` | Exit 0; four scenarios in 8.7 s | Final responsive sizing and explicit viewport-overflow assertions |

The controlled capture fetched exactly two pages in two requests; a later no-network step published the derived intake. Downloaded first-page bytes hashed to their event's retained SHA-256 and contained three original entries. Receipt observations/cases were empty before separate reference acceptance. Repeated identical capture reused accepted logical evidence while retaining its own receipt and decision. Reload retained the selected capture. The 429 route retained its body and due time; refresh caused no extra source request; cancellation survived reload and created no intake result. Browser HTTP fixtures are injected only by the isolated test launcher; production accepts no endpoint input.

Service tests separately exercise typed direct-reference reads, safe redirects, unsafe hosts/paths/include queries, partial later-page and malformed responses, pagination cycles, page/request/reference/entry/byte/time bounds, transient exhaustion, future Retry-After without sleeping, busy locking, in-flight cancellation fencing and artifact integrity. Real subprocess death during fetch releases the OS lock and resumes with at most a repeated read; death inside final publication rolls back partial receipt inserts and resumes to one result without another fetch. An approved clinic export's serialized content and current version pointer remain exactly unchanged. Schema-11 upgrade and stopped backup verification/restore are tested; migration occurs only on opening the restored copy, preserving archive bytes.

## Failures and corrections

An early backup regression fixture left a SQLite connection open after rewriting its schema marker, so verification correctly detected uncheckpointed WAL. Closing the fixture connection explicitly corrected the test; focused backup/acquisition reruns passed. No production verification bypass was added.

The first acquisition browser run had one pass and three failures: both throttle journeys timed out using an exact label selector for a select, and the phone repeat expected `committed` instead of the valid `duplicate_delivery` reuse result. The test now uses the combobox role and explicitly verifies accepted observation reuse. The subsequent full 62-scenario suite passed. Screenshot inspection then found the retained-capture selector could overflow the phone viewport; its sizing was corrected and explicit no-horizontal-overflow assertions added. Final focused responsive qualification passed all four desktop/phone scenarios in 8.7 seconds, including the overflow assertions. Earlier failures remain distinct from successful qualification.

Inspected screenshots: [desktop completion](desktop-capture-complete.png), [phone completion](phone-capture-complete.png), [desktop throttle](desktop-capture-throttle.png), [phone throttle](phone-capture-throttle.png). These show synthetic loopback fixtures, not a public payer response.

## Limits

No public source request was made by these implementation checks. The live HAP readiness query previously returned 429. Its advertised Plan-Net 1.0.0 and the parser's 1.2.0 subset remain separate/unverified, and complete terminology validation is open. Socket/request/byte/page budgets bound acquisition; a process dying during a request can repeat that read before response journaling. A completed query is not a transactionally consistent full directory. Actor identities are local assertions; no scheduler, hosted team operation, payer writeback, actual model invocation or human observation is claimed. TestClient retains its known dependency deprecation warning.

Documentation validation passed across 54 Markdown files; `git diff --check` passed.

Next: [D3.0 mapping-assistance readiness](../../../../NEXT.md), then the no-model-capable combined consumer/recovery rehearsal. No API credential variable was configured in the inspected shell; actual model access/evaluation remains unestablished.
