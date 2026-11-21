# R4 integrated review — 2026-11-15

Implementation commit `d09b66403bc9ae6e68e78133da5fc761e66a519e` on `feat/provider-data-operations-plan`, descending from verified public baseline `760acde40001a4c66614b21979381767795e8e97`. Current contracts/status are committed separately from implementation and retained evidence. Publication/deployment remain outside this continuation. V1–V4 below were frozen in NEXT before the final fix; their final disposition is recorded here.

## V1: consistent retained JSON

Direct supported-reference reads previously decoded with ordinary JSON before checking identity and assembling a normalized Bundle. Duplicate original properties could disappear before strict native parsing. [Three initial failures](json-before.txt) reproduced this. A small shared `fhir_json.py` now enforces the existing strict saved/search rules on every reference and digest-verified retained body before publication: duplicate properties, non-JSON/nonfinite numbers, excessive depth/nodes/bytes fail; UTF-8 BOM remains accepted. Native resource/profile/projection semantics remain v2. Old completed receipts/observations are untouched.

The extraction initially failed an existing test that deliberately monkeypatches the parser byte limit: [81-case first rerun](json-first-rerun.txt), [combined rerun](combined-first-rerun.txt) with 210 passes/one failure. The parser now explicitly passes its limit to the shared decoder. [Corrected 88-case run](json-corrected.txt) passed. Ten reference cases cover duplicate identity/type/nested properties, constants/overflow/depth/node limits, old queued publication revalidation, restart and BOM preservation. They all pass in the final full suite. The old queued case recreates prior acquisition decoding only; publication rejects its exact ambiguous original without a new request.

[Retained HTTP qualification](qualification.json) ran after a complete synthetic operations journey. Two loopback requests ended in HTTP 200 with [this exact duplicate-key body](failed-reference.json), hash verified, failed capture and no intake receipt. Restart made no further request. Receipt/observation/feed/version/decision/work/recipe counts remained unchanged. [Approved export](approved.json) stayed byte-identical and current, with [consumer contacts](consumer.json) and [NORTH evidence](north-fields.json) preserving SOUTH separation. The [source-checkout script](rehearse.py) reproduces this with a new root:

```sh
PYTHONPATH=src python docs/evidence/canonical/integrated-review-2026-11-15/rehearse.py .runtime/r4-review-NEW
```

## V2: final integrated qualification

| Check | Observed result |
|---|---|
| `make validate` | **869 Python tests**, one existing TestClient dependency warning, **91.47 s**; pipeline passed ([log](validate.txt)) |
| `npm test --prefix web` | **134 tests in 18 files**, exit 0 ([log](frontend.txt)) |
| `npm run build --prefix web` | TypeScript/Vite exit 0; existing main-chunk advisory ([log](build.txt)) |
| `npm run test:e2e --prefix web` | **72 desktop/phone scenarios in 2.8 min**, exit 0 ([log](browser.txt)) |
| Final isolated wheel and sdist | Both actual installed journeys passed; [distribution result](distribution-result.json), [commands](distribution-commands.json), [wheel](wheel-result.json), [sdist](sdist-result.json) |

After session handoff the prior test handles were missing, no pytest/browser processes remained, and [Python](interrupted-validate.txt)/[browser](interrupted-browser.txt) logs were truncated without completion. They remain incomplete evidence, not passes. The fresh final runs above reached completion. Test timings under local load are not product-performance measurements. No application-code changes followed these final gates.

Builds now use an owned source copy, excluding bytecode/egg metadata and checkout build caches. Final distribution input hashes were compared with current source/README/metadata before the implementation commit. Both archives contain the exact twelve checked assets; installed modules came from their own site-packages with no editable/PYTHONPATH/user-site fallback. Each exercised default QA, operations/holds, independent consumer, JSON/XLSX, read-only SQL, unchanged eight-case no-model baseline and backup/restart/restore. Logs and binaries remain in owned storage; selected public logs replace local paths with placeholders. Python artifacts contain the headless/backend toolset; React remains a Node/source workflow. No remote CI run is claimed.

## V3–V4: review, history and handoff

Review covered native parser/acceptance versus clinic rules, schema-12/13 additive ledgers and old backup restore, transaction/revision fencing, acquisition origin/query/cooldown limits, raw-versus-derived provenance, explicit source/identity/field/dataset decisions, proposal-only model authority, selected export scope and portable defaults. R1/R2 receipts preserve the filtered-response and graph/cardinality findings. The original adverse fixture, frozen corpus, old observations/history, private preparation and all earlier failed/successful runtimes remain retained.

The public-content audit checks tracked/untracked/staged paths, recognizable credential/private-path patterns, forbidden database/key/runtime files, whitespace and XLSX XML; it is supplemented by source/evidence review, not presented as a general sensitive-data certification. Actual HAP payloads/native IDs/tokens remain ignored; only bounded sanitized count/hash summaries are public. GitHub confirmed the public baseline SHA and account ID 225331421, matching `225331421+mlow-io@users.noreply.github.com`; local commits use that metadata. No private ancestry, publication, push, payer write or external message was introduced.

Current SPEC/ROADMAP, architecture/area contracts, API/data references, STATUS and NEXT distinguish implementation, automated evidence and open claims. The existing operations guide now includes an H2 prepared-state observer kit; no participant result is invented. R1–R4 independent headless work is complete. Actual-model A1/A3 still need approved configured access; uncoached H1/H2 and broader actual-source/profile coverage remain unverified. Additional source families, hosted teams, FHIR writeback and model frameworks remain deferred. The goal is a bounded demonstrable provider-data workflow, not automatic certification or a production deployment.

[Completion audit](completion-audit.json), [local commit metadata](commits.json), [final model-access flags](model-access.json), [public-content audit](public-content-audit.json), [documentation/asset checks](checks.txt) and [checked file hashes](checked-files.json) make the final disposition inspectable. The evidence commit is the commit containing this receipt; its hash is intentionally not embedded in itself. These files record the available headless boundary, not completion of external/model/human claims.

Raw tool reports intentionally preserve CRLF/trailing spaces and terminal blank lines. The first staged whitespace check surfaced those retained bytes; its diagnostic remains in ignored storage. Scoped `.gitattributes` disables EOL conversion/whitespace lint only for evidence JSON/text/log reports, preserving recorded digests. Source and authored Markdown checks remain enforced; no historical report was rewritten to satisfy formatting lint.
