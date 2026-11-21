# HAP live boundary and bounded query qualification — 2026-11-14

Local uncommitted working tree on `feat/provider-data-operations-plan`, based on `760acde`. This supplements D2 and the [combined D4 receipt](../operations-2026-11-14/README.md), preserving every earlier failure and qualification. [Checked file digests](checked-files.json) identify the current code, tests, contracts and evidence.

## Observed defect and bounded change

[HAP's official documentation](https://api.hap.org/providerdirectoryapi) publishes the fixed production gateway, unauthenticated reads throttled to a few calls per minute, and Plan-Net 1.0.0. The earlier readiness call returned 429. A later real worker request returned HTTP 200 with one Location but advertised its next link on `fhir-prov-dir-r4.api.hap.org:443` with `_pretty=true`. The original strict worker retained the page and failed before requesting that off-origin link. Both names resolved to the same HAP gateway during investigation; this observation alone was not used to authorize an alternate fetch destination.

The source contract was changed before code. Only the exact declared HAP alias/default-443 authorities normalize back to the published HTTPS origin; no request is sent to an alternate host. Unknown hosts, schemes, ports, userinfo, fragments, encoded paths and unsupported queries remain rejected. `_pretty` permits only one true/false value. Routed nodes/bodies/events retain advertised `source_url`; actual request URLs remain in raw-page origins. Derived direct-reference `fullUrl` retains advertised source identity. Relative references use their resource's declared REST base, matching the pure parser; an unsafe base does not silently redirect to the configured source. All byte/page/time/request/retry/cancellation bounds remain.

Page size alone does not limit total results. An optional source-native `resource_id` now becomes one validated `_id` search parameter through create/API/Sources. It is included in filtered receipt query/scope metadata; old unfiltered scope hashes/shape stay unchanged. This adds no schema migration, source family, arbitrary filter language or background fetch.

## Actual source observations

[The Location summary](live-location-summary.json) records public status/artifact hashes and a digest of the native resource ID, without copying actual provider bytes/identities into Git. A new ID-filtered intent completed in **one request, one page**, yielding one supported/eligible Location, zero invalid/unsupported/unresolved resources and no clinician/role assertion. Original page bytes and requested ID were inspected; derived resource content matched the retained original. A separate local reference acceptance created one observation, no work case and no approved clinic version. Exact saved-byte parser replay matched persisted resources, references, assertions, coverage and findings. Restart preserved the observation; a repeat completed worker pass sent no request or duplicate result.

[The pagination summary](live-pagination-summary.json) records a separate two-request live transport probe. Both actual pages returned HTTP 200 through the published origin; the routed response retained its original alias URI and both raw hashes matched. After exactly two pages the intent was explicitly cancelled, leaving partial evidence and **no intake receipt or acceptance**. It is not a completed directory capture. Default 30-second source spacing was honored; no rate limit was bypassed and no automatic retry loop ran. This follow-up made four actual source requests total: the pre-fix page, filtered page and two transport pages, all in an owned workbench. Earlier probes remain separate.

Actual source bytes, native IDs, pagination tokens, database and artifacts remain in ignored invocation-owned storage. Source-advertised Plan-Net 1.0.0 and parser-target 1.2.0 subset remain distinct. The actual Location was not run through target-profile validation and is not certified conformance, independent provider truth, reviewed identity or network participation. Live PractitionerRole/network graph interoperability remains unverified. The [synthetic online terminology controls](../fhir-terminology-2026-11-14/README.md) are a separate evidence category.

## Final checks

| Check | Result |
|---|---|
| `make validate` | Exit 0; **814 Python tests in 59.83 s** and pipeline passed |
| `tests/test_fhir_acquisition.py` | **60 passed** in the full suite; focused run 60 passed in 32.03 s |
| `npm test --prefix web` | Exit 0; **131 tests**, 18 files |
| `npm run build --prefix web` | Exit 0; TypeScript/Vite build |
| `npm run test:e2e --prefix web` | Exit 0; **70 desktop/phone scenarios in 2.7 min** |

Retained logs: [Python/pipeline](validate.txt), [source tests](source-tests.txt), [frontend](frontend.txt), [build](build.txt) and [full browser](browser.txt). TestClient dependency deprecation and the 501.84 kB main-chunk advisory remain. No new code followed these final checks; subsequent edits update evidence/contracts/status. Documentation and whitespace results are recorded in STATUS after final receipt creation.

The parameterized controlled source tests cover absolute and relative alias references, preserved advertised identities, published-only fetch URLs, response origin hashes, separate acceptance, foreign-base nonfetch, default ports, malicious hosts/schemes/paths/fragments/query values, injected-source isolation, filter request identity/grammar, scope changes and unchanged unfiltered metadata. API tests reject invalid filters before fetching. The component validates an ID before queueing; browser tests complete one filtered capture, inspect actual query metadata, reload selected scope and separately accept its one synthetic reference without creating a case. Inspected [desktop](filtered-wide.png) and [phone](filtered-mobile.png) screenshots show the native-ID controls and exact selected scope without horizontal overflow.

N1/N2/N3/F3/F6 retain their prior synthetic engineering evidence and now include these source-boundary regressions and specific live observations. E1/E2 continue passing in the full suite. This does not broaden A1/A3 or human H1/H2 claims.

## Failures retained separately

- [Initial alias tests](alias-before.txt): four failed/ten passed, reproducing missing production alias routing. The first corrected source suite passed 46 tests.
- [Relative-reference control](relative-before.txt): one failed/one passed because the advertised REST base was lost under transport routing. The final code preserves it and rejects an explicitly foreign base.
- [Filter controls](filter-before.txt): two failures reproduced absent native-ID support and foreign-base relative fetch behavior. Final source suite passes 60 cases.
- [First browser attempt](browser-before.txt): four scenarios passed/two failed because the new assertion expected a nested `receipt` envelope; the existing packet is flat. The test was corrected against the actual API implementation. The final full 70-scenario run passes; the failed result directories remain preserved separately.

The original actual failed capture stays failed and unaccepted. No actual payload was turned into a committed synthetic fixture. No user's runtime, model invocation, external communication, payer update, publication or deployment was involved. The remaining required actual-model evaluation depends on approved API access; [NEXT](../../../../NEXT.md) owns that bounded task.
