# D1.1 headless parser evidence — 2026-11-14

Baseline `760acde`, uncommitted work on `feat/provider-data-operations-plan`. The native parser and CLI are implemented; this is not evidence of durable intake, web UI, payer connectivity or overall Plan-Net conformance.

## Implemented and checked

`src/provider_directory_truth_layer/fhir_intake.py` provides a pure bounded UTF-8 searchset parser, within-Bundle resolver, resource/findings retention, scope-aware role/location assertions and exact contributing field locators. It rejects excessive bytes/entries/depth/nodes, duplicate JSON keys and nonfinite numbers. It retains ambiguous/external references and blocks unsafe automatic projections. No network or database functions are called.

`provider-truth-layer inspect-fhir INPUT [--report NEW_FILE]` exposes the parser offline. File reads cap at the artifact bound plus one byte; report creation refuses overwrite. The report distinguishes structural inspection from profile/terminology checks, both of which remain `not_run` in ordinary parser output.

Focused command: `.venv/bin/python -m pytest -q tests/test_fhir_intake.py` — 77 passed. Authored expected NORTH/SOUTH values, ZIP fidelity, locators, unsupported resources, ambiguous/missing/external/URN references, cross-host relative resolution, multi-location roles, unknown modifiers/extensions, malformed shapes, contact ambiguity, depth limits, input preservation and CLI/no-database/overwrite behavior are covered.

Full command: `.venv/bin/python -m pytest -q` — 662 passed in 22.46 seconds with the existing Starlette TestClient deprecation warning. Documentation checks passed across 50 Markdown files; `git diff --check` passed. No frontend/pipeline behavior changed, and no browser run is claimed.

## Pinned validator results

[The manifest](validation-manifest.json) records JAR/input/report SHA-256, JVM, package versions and installed package-metadata hashes. Both reports are retained verbatim OperationOutcome JSON; machine-local logs and package cache stay under ignored runtime storage.

- [Mixed Bundle report](north-south-validation.json): exit 1, four errors, eleven warnings and two informational issues. The authored Network lacks mandatory type/parent, causing two further reference-profile errors. This is intentional retained invalid-input evidence, not a passed standards gate.
- [Standalone Location report](profile-location-validation.json): exit 0, zero errors, two warnings concerning unavailable USPS terminology. The second invocation used `-no-http-access` and `-tx n/a` against the prepared cache. Structural/profile diagnostics contain no errors, but complete terminology validity remains unverified.

The default Java launcher had no runtime registration; the existing Homebrew OpenJDK 21 executable ran validator 7.0.5. No JVM installation or global configuration change was needed. Package acquisition was isolated with Java `user.home` under the owned runtime directory. Dependency versions discovered by the pinned validator are recorded; metadata hashes do not claim complete archive/content verification.

## Open gates and continuation

F2's complete terminology check remains open. Continue with D1.2 storage/API/comparison integration using the `not_run`/unavailable validation states defined by the contract; this does not require claiming profile conformance. D1.1 has implementation and local validation evidence, but its broad standards gate is not fully qualified. F4/F6/F7/F8 and D1's overall qualification remain open. No source data or previous approved datasets were changed.
