# Provider-data operations demonstration

Contract frozen 2026-11-14 before D4 implementation. [STATUS](../STATUS.md) owns actual verification. This demonstration connects existing intake, recipe, managed-feed, native-source, identity/field-review, investigation and backup services in one new invocation-owned synthetic root. It performs no public payer or model request.

## Small approved-data consumer

`consume-approved` reads a supplied schema-1 managed-feed JSON export without opening the application database or fetching anything. The caller must supply the expected immutable version ID; expected feed ID and whole-file SHA-256 may additionally pin the handoff. A candidate/version-detail response, missing or non-approved decision, unknown schema, mismatched version/feed/digests, hard quality finding, unacknowledged hold, quarantined row inside records, duplicate native key or malformed contact is rejected. An approval/digest is an asserted local handoff and integrity check, not a signature, independent identity verification or freshness guarantee.

Use the existing exact export shape: version_id, manifest, report, report_hash, approval, exception_review, records and quarantine. Verify canonical report/records digests using the producer's version-1 JSON serialization (sorted keys, UTF-8, non-ASCII preserved, default JSON separators, no nonfinite numbers). Approval version must match the pinned version. Report counts must agree with included and excluded rows; every soft hold needs its recorded latest acknowledged disposition. The reader consumes at most 10 MiB, 20,000 included/excluded rows combined, 500,000 JSON nodes and depth 64. These are the bounded reader's limits, not a new producer limit.

This consumer requires nonblank text record_id/location_id/npi/provider_name/address/city/state/zip/phone, ten-digit NPI and phone, two uppercase state letters and five-digit ZIP or ZIP+4. A source with another valid producer representation may need an explicitly reviewed formatting recipe before it meets this contact-reader contract. Optional extension is preserved as absent/null/blank/text; a nonblank value must contain 1–10 digits. Keys are (record_id, location_id), never NPI alone. Project contacts in native-key order, retaining text IDs, leading-zero ZIPs and extension semantics. Return consumer schema/version/feed IDs, input/record/report digests, declared designation, approval context, contacts and a notice that these are pinned source assertions. Do not inspect/change current-version pointers or infer freshness.

CLI interface: `provider-truth-layer consume-approved EXPORT --expected-version ID [--expected-feed ID] [--sha256 HEX] [--report NEW_FILE]`. Default output is stdout; an explicit report destination must be new. Existing inputs, reports and runtime directories are preserved.

## Connected synthetic journey

Use one clinician (synthetic NPI 1000000001), NORTH at 10 Example St and SOUTH at 20 Example St, ZIP 02108, and one source-declared payer network. NORTH clinic phone is 6175550100 with extension 007; SOUTH is 6175550200 with extension 008. The source-declared NORTH payer phone is 6175550199; its extension remains unknown. Keep local network identity/binding unknown unless separately reviewed.

1. Author a workbook with differently named columns, ambiguous phone-header suggestions, a numeric ZIP formatted with leading zeros, formatted phones/extensions and a duplicate NORTH native key. Explicitly choose Office Tel, reject an unsupported recipe operation, approve a valid recipe and accept only eligible rows; retain duplicate quarantine. Record optional assistance unavailable through an explicitly disabled client, without sending a request.
2. Reuse that reviewed recipe in a declared recurring CSV contract. Approve a clean NORTH/SOUTH delivery and export its named version. Run the independent contact reader against actual serialized bytes and inspect both offices/ZIP/extensions.
3. Retain saved FHIR and bounded two-page controlled-HTTP evidence through the same parser. Preserve unsupported content, invalid-resource diagnostics and unresolved saved references. The acquired graph is bounded, not a full directory. Every acquired NORTH field reference must trace to exact page bytes/locator. A local replay of the assembled bytes must reproduce the acquired supported assertions.
4. Review clinician and NORTH/SOUTH location links explicitly. Use the known correct office pairs; retain the workbook's duplicate-key NORTH candidate as explicitly deferred/unapproved. Different street addresses are not in the matcher's same location group. Select the conflicting NORTH source phone with unknown extension. Do not copy it to SOUTH or establish local network membership. Export selected NORTH field evidence in JSON/XLSX.
5. Exercise a persisted 429 wait, later-page failure, unsafe next destination and malformed response on the controlled source. Retain partial/error bodies; do not publish incomplete results or change approved consumer bytes. Deliver a later CSV that changes NORTH to 6175550188 and omits SOUTH. Keep its missing-key/row-drop holds unacknowledged, reject promotion and candidate consumption, and verify the prior approved version/contacts remain unchanged. SOUTH is not closed by omission.
6. Investigate the retained NORTH correction: assign, record no answer and a separate office response reporting 6175550199, triage, explicitly approve a proposal, record simulated submission and a separate observed mismatch 6175550100 that reopens the case. Preserve SOUTH. Export its existing JSON/XLSX investigation handoff.
7. Produce a NORTH dossier index referencing the existing field and investigation exports by digest and their distinct scope/identity-review context. Shared complete receipt/Bundle payloads may contain SOUTH; selected field rows and selected work cases must not label SOUTH as NORTH evidence. This is a file handoff of existing exports, not a new case system or automatic merge.
8. Stop/reopen, verify a repeat delivery creates no second logical acceptance, and exercise stopped database-plus-artifact backup/verify/restore into a new root. Check integrity, foreign keys, all registered artifact hashes, pinned consumer bytes and selected payloads. Comparison of work handoffs excludes only their descriptive snapshot timestamp, never decisions or source evidence.

`rehearse-operations --root NEW_DIRECTORY` creates the retained runtime and exports without replacing existing roots. It retains command/fixture results and raises on an unmet invariant. Owned loopback HTTP and synthetic artifacts are the only network/data source used. Actual model access/quality, public-source interoperability, full terminology conformance and observed human usefulness remain separate open evidence gates.

## Run and inspect

After the README source or wheel setup, activate the virtual environment and use a new root:

```sh
mkdir -p .runtime
provider-truth-layer rehearse-operations --root .runtime/operations-demo-NEW
```

Choose a new suffix for every run. Read `operations-rehearsal.json` for the pinned IDs, coverage, rejected actions and recovery results. `exports/approved.json` is the clinic dataset; `exports/consumer.json` contains the independent reader's actual contacts. The dossier index binds the separate NORTH field and investigation JSON/XLSX files by digest. `storage/` contains retained application state; `backup/` and `restored/` retain recovery evidence. Do not mix these files with a user's workbench.

From a source checkout with Node dependencies, inspect the prepared state in the web workbench:

```sh
PYTHONPATH=src python3 scripts/demo.py --root .runtime/operations-demo-NEW/storage
```

Use the report's feed/version IDs in Deliveries to inspect the approved baseline and held candidate. In Receive data inspect the acquired receipt's invalid/unsupported findings and original page links; in Provider records select the report's reviewed clinician/location; in Work queue open its NORTH case. The CLI prepares and verifies the workflow; it does not claim an unassisted person completed it. Follow [the original human walkthrough](INVESTIGATION_DEMO.md) for H1 and retain observed errors/assistance separately for the expanded H2 task.

To use the independent reader on a supplied export:

```sh
provider-truth-layer consume-approved .runtime/operations-demo-NEW/exports/approved.json \
  --expected-version VERSION_ID_FROM_REPORT --report .runtime/consumer-check-NEW.json
```

The [D4 receipt](evidence/canonical/operations-2026-11-14/README.md) maps actual tests, serialized outputs, failure corrections and remaining gates. No source-wide cooldown is bypassed in production; the controlled rehearsal advances its injected synthetic clock after testing a retained 429 wait.

## Portable distribution (R3)

Contract frozen before implementation. The Python wheel and source distribution must carry the small immutable assets used by existing headless commands: default synthetic QA CSV/rules, six operational SQL templates, the original adverse saved-FHIR operations fixture and its independently authored expectations, and the frozen mapping corpus/manifest. Authoritative contributor files remain in their existing locations; a static exact-byte synchronization check detects stale packaged copies. Runtime reads use `importlib.resources`, never a presumed repository ancestor or implicit current-directory fixture. Explicit `--input`, `--config` and `--corpus-directory` paths remain caller-selected overrides. Omitted options use packaged defaults, including when a similarly named local file exists. Frozen corpus bytes/digest/denominators are unchanged.

Distribution qualification must build and install a wheel and an sdist-derived wheel in owned environments outside the checkout with no editable installation, `PYTHONPATH` or user-site fallback. Check installed module provenance and run actual default QA, synthetic operations, version-pinned approved consumption, the eight-case no-model evaluation and allowlisted read-only SQL against retained output. Inspect JSON/XLSX, leading-zero ZIP/extension and NORTH/SOUTH separation, rejected promotion/repeat-root preservation and backup/reopen results. No actual source or model calls occur. Keep failures/reruns and artifact hashes separately; CI must exercise the same boundary.

The Python distribution is the backend/headless toolset. The React workbench remains a source-checkout/Node workflow as documented in README; the wheel does not serve compiled frontend assets. Existing owned output-root rules and storage configuration remain unchanged. No schema migration, global installation, hosted deployment or package publication is part of R3. P1–P4 are owned by NEXT until qualified.

R4 tightens the build boundary: copy only package source/assets, project metadata/README and any repository license into the new owned distribution root, excluding bytecode/egg metadata. Build both artifacts there, recording input hashes. This prevents checkout `build/` leftovers from contributing stale modules and keeps generated build state outside the working tree. Existing local build evidence is preserved/ignored rather than deleted.

## H2 prepared-state observer kit

This kit evaluates an analyst resuming a prepared workload. It does not measure first-time setup, unaided recipe authoring or comparative time savings. H2 remains unobserved until an actual uncoached participant performs the task and the observer retains outcomes. Keep participant notes outside Git; publish only a separately reviewed anonymous summary.

### Observer setup

Run the rehearsal in a new synthetic root and retain its report as an observer answer key. Start the web workbench against its `storage/` root using the command above. Give the participant the local URL and task below, without the report, exported answer files or click-by-click directions. Prepare a private note with start/end times, task outcome, errors, requests for help, assistance supplied and artifact names/hashes. Agree on a session duration beforehand, for example 25 minutes; a timeout is an observed outcome, not a product-performance estimate. Do not alter a user's existing root or send any communication.

### Participant task

You are taking over a clinic-directory workload with NORTH and SOUTH offices. Decide which clinic dataset can be handed to a downstream colleague now, explain the status of the later delivery, investigate the conflicting NORTH office phone and export a NORTH evidence handoff. Show the original source of the disputed phone and explain whether the last attempted correction was verified. Keep SOUTH distinct. Treat any source/network relationship you cannot establish as uncertain.

### Observation and retained evidence

Observe without navigation help. Record where the participant hesitates, misreads a state, confuses source acceptance with dataset approval, or needs assistance; preserve the exact task/result even if incomplete. When help is necessary, record what was supplied and stop describing the remaining result as unassisted. Ask the participant to explain their final choice before revealing the answer key.

Afterward inspect the actual downloaded files and prepared report: the two-office approved version remains current; the later missing-SOUTH delivery remains held; consumer contacts preserve ZIP/extension/office scope; NORTH's preferred source phone differs from the separate mismatch that reopened work. Selected evidence traces to original resources/pages and labels complete shared context. SOUTH is not terminated by omission; no local network binding is inferred from a source Network. Hash the participant's artifacts and record which outcomes were demonstrated, incorrect, assisted or not attempted. Keep observed usability, task correctness, source truth and potential time savings as separate claims. H1 continues to use its original investigation task.

## Portable Python installation

From a checkout with the dev extra installed, build `python3 -m build`. Install the resulting wheel into a separate environment:

```sh
python3 -m venv pdtl-env
source pdtl-env/bin/activate
python3 -m pip install /path/to/provider_directory_truth_layer-2.0.0-py3-none-any.whl
mkdir pdtl-runs
provider-truth-layer rehearse-operations --root pdtl-runs/operations-NEW
provider-truth-layer evaluate-mapping --root pdtl-runs/mapping-NEW
```

Default QA uses bundled synthetic CSV/rules; explicit `--input` and `--config` paths override them. Mapping evaluation uses the frozen eight-case corpus unless `--corpus-directory` is supplied. `--invoke-model` requires the separately configured client and records actual/unavailable outcomes. The Python artifacts contain backend/headless tools; the React workbench uses the documented source/Node setup.

Contributor assets remain authoritative under `config`, `data/raw`, `sql/operations` and `tests/fixtures`. Run `python3 scripts/sync_bundled_assets.py` to check exact packaged copies; after an intentional source edit use `--write` and review both. `python3 scripts/check_distribution.py --root /tmp/pdtl-distribution-NEW` builds and exercises wheel/sdist installs in new owned storage outside the checkout; CI runs the same boundary.
