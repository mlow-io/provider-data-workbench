# R2 provider relationship qualification — 2026-11-14

Local working tree on `feat/provider-data-operations-plan`, public baseline `760acde`. [The contract](../../../FHIR_INTAKE_CONTRACT.md#coherent-provider-graph-r2) froze G1–G4 before implementation. [The manifest](manifest.json) identifies tools/packages; invocation files record arguments, input/JAR hashes and execution bounds. Paths in public copies are replaced with placeholders; original reports remain in owned ignored storage. The graph, exports and failed specimens in this receipt are synthetic.

## G1–G2: coherent graph, validation and selected output

The new eight-resource graph has one clinician, separate clinic/payer organizations, one source Network, NORTH/SOUTH Locations and separate roles. Each declares the exact version-qualified Plan-Net profile. The independent expectations distinguish source version from profile version, role contact from office contact, and source Network from local binding. Original adverse D1/D4 fixtures remain unchanged.

| Check | Observed result |
|---|---|
| First validator run | Exit 1 in 21.81 s: five errors, four informational findings; [original draft](first-invalid-graph.json), [report](graph-validation.json), [invocation](invocation.json) |
| Corrected whole graph | Exit 0 in 25.37 s: zero errors/warnings, one AllOK informational finding; [report](corrected-graph-validation.json), [invocation](corrected-invocation.json) |
| Multiple-Network counterexample | Exit 1 in 23.62 s: one error, three extensions where Plan-Net 1.2 allows one; [report](cardinality-validation.json), [invocation](cardinality-invocation.json) |
| Initial graph tests | Four failed/three passed; [log](before.txt). The later [service rerun](first-service-rerun.txt) exposed an incorrect test expectation about raw display formatting, corrected independently of product behavior |
| Cardinality diagnostic before fix | One failed; [log](cardinality-before.txt) |
| Final graph/parser/store suites | 106 passed; [log](focused.txt) |
| Final `make validate` | 857 passed, one existing dependency warning, 111.50 s; pipeline passed; [log](validate.txt). The earlier 856-pass run remains [separate](intermediate-validate.txt) |

Pinned validation caught a bad sample NPI check digit and missing role contacts. The new positive specimen uses checksum-valid synthetic `1000000004` and a separate role phone. This does not verify registry existence or credentials. Parser v2 recognizes the bare Network profile and exact `|1.2.0` form; unknown explicit versions remain unresolved. Explicit reprocessing creates a new attempt; old v1 observations remain intact across restart. No schema migration/startup reprocessing was added.

[Qualification](qualification.json), [native packet](native-packet.json), [NORTH JSON](north-fields.json) and [NORTH XLSX](north-fields.xlsx) were inspected. Eight resources and two role assertions become eight separately accepted reference observations. Six explicit identity-link decisions and a field decision produce NORTH's raw `617-555-0100` phone; the test independently checks canonical comparison `6175550100`. NORTH locators are 0/1/3/4/6; SOUTH 5/7 is excluded from selected phone provenance while full original context is retained. JSON and XLSX payloads match, restart preserves them, SOUTH is unchanged, and no local network, work case or approved feed version is created. Ordinary imports still report profile validation `not_run`.

## G3: actual source graph and projection limit

The [sanitized live summary](live-qualification.json) records one cancelled discovery page and a filtered role capture: one search page plus three bounded supported reference reads, all HTTP 200. Five total source requests respected persisted spacing; no broad traversal, retries or writes occurred. R1 checked one match/two includes. Four exact response hashes, assembled hash, independent saved parser replay and restart were checked; actual payloads/native IDs/tokens remain outside Git.

The captured role explicitly references three Network Organizations. The declared Plan-Net 1.2 projection supports one; it now explains this cardinality limit and produces zero office assertions. One unsupported HealthcareService reference remains unresolved and was not fetched; twelve unknown extensions remain visible. Six eligible reference resources were separately accepted without creating local networks, cases or feed versions. The old interpretation is preserved. Source documentation advertises Plan-Net 1.0.0: this capture neither validates nor rejects conformance to that version.

## G4 and limits

G1–G4 are qualified within these scopes. The existing 134 frontend tests/build and 72 browser scenarios are the unchanged R1 UI checkpoint; R2 changed no UI. Positive synthetic profile validity is separate from actual-source coverage, application-wide conformance, reviewed identities, human usefulness and actual-model results. Those broader gates remain open. [NEXT](../../../../NEXT.md) advances to R3 installation, then R4 integrated review. No publication or deployment occurred.
