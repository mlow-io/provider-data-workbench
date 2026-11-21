# D1.0 readiness and roadmap receipt — 2026-11-14

Baseline: public-ancestry application `760acde40001a4c66614b21979381767795e8e97`, with the current uncommitted roadmap/design/checker changes on `feat/provider-data-operations-plan`. This is local evidence, not a new commit, publication, browser qualification or FHIR conformance receipt.

## Completed scope

- Bounded D1–D4 roadmap with scope ceilings, dependencies, acceptance IDs, fallback decisions and a defined local release-candidate finish.
- Selected D1.0 design: reuse schema-11 artifacts/attempts/observations; retain native reference data in versioned preview JSON; carry per-field supporting references; use explicit reference-resource acceptance without clinic work or dataset promotion.
- Authored nine-resource synthetic NORTH/SOUTH input, independent expected outcomes/negative variants and proposed interface examples. No FHIR parser, new profile, service payload or migration is implemented.
- Documentation checker now validates Markdown heading anchors as well as file destinations, ignores fenced examples and retains existing canonical-entrypoint checks. CI already invokes this script; no workflow configuration change is necessary.

## Verification

`.venv/bin/python -m pytest -q tests/test_project_docs.py`: 5 passed. Cases cover a removed heading in an existing file, local/duplicate/encoded anchors, fenced examples, explicit anchors and missing destinations/entrypoints.

`.venv/bin/python -m pytest -q`: 585 passed in 24.08 seconds, with the existing Starlette TestClient deprecation warning. No Python failure or rerun occurred in this invocation. No dependency replacement was performed.

The existing `scripts/rehearse_investigation.rehearse` function ran in a new `tempfile.mkdtemp`-owned root and preserved that root afterward. Result: NORTH reopened on observed mismatch, two outreach events, two retained observations, SOUTH unchanged and restart preserved. This was a headless service rehearsal, not a human or browser usability test.

The generated JSON contained one selected case and two contact events. The XLSX was opened and contained Read me, Cases, Evidence, Receipts, Attempts, Decisions, Relationships, Investigation, Outreach and Payloads sheets; Cases had one data row, Evidence two and Outreach two. SQLite integrity was `ok`, foreign-key violations were zero, and retained artifact hashes matched their bytes. Original user storage was not opened or changed.

The authored FHIR fixture was inspected independently for nine resources, the two distinct office phone strings, leading-zero ZIP `02108` and locations without NPI identifiers. Expected outputs are hand-authored contract targets. Validator execution and profile-validity claims remain open for D1.1.

## Evidence identities

These hashes identify the locally checked code and contract examples despite the uncommitted working tree. Documentation changes are reviewable in the Git diff.

| File | SHA-256 |
|---|---|
| `scripts/check_project_docs.py` | `8748107bf2dfeb549698b988c63e70434b053b90d0ede7ea2c2e4ef8c4499ceb` |
| `tests/test_project_docs.py` | `afecf6873903d1005d35aed0346d2cef5dfeb3d3a27c3c785e1d50a36f8cef59` |
| `tests/fixtures/intake/fhir-plannet/north-south.json` | `3b01a66d81d89565223f8c0bd61cf616511713a5375c714d4efcd011bc29a6eb` |
| `tests/fixtures/intake/fhir-plannet/expected.json` | `440840d684281c34053696a321912b6f0ede1ca04ff114921899ca9f3a8f3af3` |
| `tests/fixtures/intake/fhir-plannet/interface-examples.json` | `962d33a28850648b59425c302f1456666d460e4456ce89bf017f4dd1388a3078` |

## Remaining work

[The next brief](../../../NEXT.md) is D1.1 parser/resolver/fixture implementation and pinned validation. D1.2 connects persistence, comparison and exports; D1.3 connects and qualifies the UI. D2–D4 and H1/H2 remain open as described in ROADMAP. No live endpoint lookup, model invocation, frontend change, deployment or publication occurred in this run.
