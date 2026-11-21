# D3 mapping assistance engineering — 2026-11-14

Local uncommitted working tree on `feat/provider-data-operations-plan`, based on `760acde`. [Checked file digests](checked-files.json) identify implementation, fixtures and checks. D3.0 contract selection is complete; D3.1 client/service/web engineering has controlled-provider evidence. Actual-model A1/A3 and measured usefulness remain open. This is not a successful real-model evaluation.

## Implemented path

One optional OpenAI Responses client, disabled by default, pins a clinic receipt/attempt and an explicitly permitted bounded source sample. The selected model/configuration and dated rate assumptions are in [SOURCE_ONBOARDING](../../../SOURCE_ONBOARDING.md#d30-selected-model-invocation-contract), with primary documentation links. Source cells have no instruction authority. The request has no tools, conversation, streaming or background task, uses store=false, and enforces request/output/response/time/reservation bounds. Non-synthetic data requires server-configured exact source permission as well as explicit run consent. Credentials and Authorization headers are excluded from retained/exported bodies; authentication-error bodies are not retained because they can echo key fragments.

Schema 13 adds a separate run/event ledger. Each invoked run reserves 80,000 micro-USD against a 1,000,000 micro-USD local lifetime allowance, including uncertain outcomes; usage-based estimates remain conservative dated-rate estimates, not invoices. There are no automatic provider retries. Unknown interrupted calls fail without replay; journaled responses resume locally. Revision/attempt checks fence stale and cancelled publication. A valid response creates only a proposed recipe, atomically with its success event/result pointer. Separate existing approval, application and acceptance actions remain necessary.

The lazy optional panel queues locally, offers exact request inspection, explicitly invokes, permits refresh/cancellation while a call is pending and exposes retained failure/unavailable states. A successful proposal appears in normal recipe review. Partial response prefixes are labeled separately from complete original responses. Accepted data and evidence packets retain run/model/prompt/schema/sample/artifact/usage provenance. Non-model exports retain their prior shape. Stopped schema-11/12 backup verification/restore is preserved, and schema-12 migration retains a pre-v13 database backup.

## Verification

| Command/check | Result | Evidence boundary |
|---|---|---|
| `make validate` | Exit 0; **753 Python tests in 45.46 s**; pipeline passed | 12 records, 11 findings, six discrepancies, isolated roots |
| Mapping service/evaluation/transport test files | 27 + 5 + 8 tests in the full suite | Proposal authority, source permission, sample limits, schema validation, actual-process crash/recovery and fixed HTTP boundary without external calls |
| `npm test --prefix web` | Exit 0; **129 tests**, 18 files | Unavailable fallback, uncertain creation identity, pending-call refresh/cancel, budget refresh and partial-response labeling |
| `npm run build --prefix web` | Exit 0 | Final TypeScript/Vite build; 501.84 kB main-chunk advisory remains |
| `npm run test:e2e --prefix web` | Exit 0; **66 desktop/phone scenarios in 2.3 min** | Full regression with controlled response-to-review and rejected-output/manual-fallback journeys |
| `npm run test:e2e --prefix web -- mapping-assistant.spec.ts` | Exit 0; **four scenarios in 11.9 s** | Final focused current-client/server integration after response-prefix labeling correction |

The focused successful browser path downloaded its exact request and checked SHA-256 against the ledger, confirmed store=false/no tools/no credential in the body and one sampled synthetic row, then ran the controlled transport. No observation or new attempt appeared after proposal success. Recipe approval and application required distinct actions; source acceptance required another reviewer/reason. The accepted export retained ZIP 02108, phone extension 007, run ID and response digest after reload. A deliberately unexpected tool result failed with no saved recipe; deterministic/manual phone rules still previewed a valid row. Both widths asserted no horizontal overflow.

Service tests also cover changed request IDs/content, explicit external-processing permission, source namespace allowlists, stale attempts before/after invocation, concurrent cancellation and discarded body retention, malformed/duplicate/nonfinite JSON, invented/duplicate columns, unsupported operations, missing unresolved requirements, wrong model, missing/over-budget usage, request/response bounds, conservative accounting on rejected results, transport timeout, rate-contract drift and artifact corruption. Real subprocess exit during invocation consumes its reservation and does not retry; exit after proposal insertion rolls the transaction back, leaving response_ready to publish exactly one proposal without another provider call. HTTP-boundary tests verify the fixed destination, no redirect/retry, header-only key, excluded 401/403 bodies and labeled capped/incomplete prefixes.

Inspected screenshots show controlled synthetic behavior: [desktop proposal](desktop-mapping-proposal.png), [phone proposal](phone-mapping-proposal.png), [desktop failed response](desktop-mapping-failed-manual-preview.png), [phone failed response](phone-mapping-failed-manual-preview.png). The explanatory text explicitly identifies the controlled browser fixture; it is not actual model reasoning.

## Frozen evaluation and access result

The [eight-case corpus](../../../../tests/fixtures/onboarding/mapping-assistant-v1.json) and [manifest](../../../../tests/fixtures/onboarding/mapping-assistant-manifest-v1.json) were authored/frozen before any actual model trial. They cover canonical and messy headers, voice versus fax, ambiguous contacts, ISO/ambiguous dates, missing phone and instruction-like source cells. Corpus SHA-256: `2ea25f58152ccbd5875ddfa19108c5296a257f4846155b66c071f51e6568589c`.

The offline CLI command `provider-truth-layer evaluate-mapping --root NEW_ROOT` retained the [baseline report](baseline.json). Existing alias-only suggestions with no transformations matched **63 of 74** authored binding/abstention expectations, requiring **11 field corrections**; **seven of 13** selected cleaned-value checks disagreed. This is a deliberately bounded challenge set and recipe-editor baseline, not a population accuracy estimate or measured human effort. Gold-cleaned expectations are coherent with existing explicit transform semantics; wrong fax/date results are counted even if schema-valid.

The explicit `--invoke-model` command retained [the requested-trial report](requested.json): all eight runs unavailable, **zero provider invocation attempts and zero completed model cases**. Server API access was not configured. Both modes created zero approved recipes, observations or feed versions. No actual model output, comparison benefit, latency/cost measurement, human correction effort or time-saving result is claimed. Actual-model trials must use the frozen corpus and retain raw outcomes when access exists; the feature remains experimental/disabled meanwhile.

## Failures, limits and continuation

An intermediate production build failed because a new Testing Library unit-test query included Playwright's unsupported `exact` option. Removing that test-only option corrected the type check; the final build and unit suite passed. An intermediate patch context mismatch made no changes and was reapplied against inspected lines. Earlier successful 746/752-test backend and four-scenario browser checkpoints are intermediate evidence, not the final counts above. During final evidence review, incomplete response prefixes received explicit metadata/UI labels and a regression; the final checks include this correction.

Documentation checking caught an incorrect new NEXT heading anchor; it was corrected before final validation. Final documentation validation passed across 55 Markdown files; `git diff --check` passed.

The known TestClient dependency deprecation warning and Vite chunk advisory remain. Active-call overruns are rejected; a blocked read can still take one socket timeout to return. Local dollar reservations use dated rates, not a provider-side invoice cap. Live payer interoperability, full terminology conformance, actual-model A1/A3, D4 combined qualification and human H1/H2 remain separate gates. No user runtime, actual provider data, payer writeback or publication was touched.

Next: [D4 combined no-model-capable qualification](../../../../NEXT.md), while actual model access/evaluation remains explicitly open.
