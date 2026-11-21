# Five-minute offline operations demonstration

Updated 2026-10-26. This is a synthetic operations demonstration, not organizational policy, licensure verification, payer writeback or a compliance certification.

## Launch and preserve

After dependency setup in the [README](../../README.md), run `make workbench`. It creates a fresh root, prints the input directory, and starts one API on 8000 plus Vite on 5173. Open `http://127.0.0.1:5173/?view=intake`. Ctrl-C retains the root. Resume with `PYTHONPATH=src python3 scripts/demo.py --root <printed-root>`. No startup cleanup or implicit reseed occurs on resume.

## Demonstrate the operator journey

1. In Intake, choose **Synthetic clinic workbook → Load synthetic sample**. The UI explains the patient-contact problem and labels the evidence synthetic. The launcher explicitly enables sample mode; ordinary service startup does not. Header row **2** and worksheet `Clinic roster` are selected. Click **Use suggested columns**, review/edit the mappings below, then **Save mapping and reprocess**. Loading and filling suggestions make no acceptance decision. Samples use the fixed `synthetic-demo` namespace.

   Ordinary uploads remain available: select `<root>/inputs/synthetic-clinic.xlsx` under any explicit namespace, choose header row 2, reprocess and map the columns manually.

| Canonical field | Workbook header |
| --- | --- |
| npi | Registry number |
| provider name | Clinician |
| address | Street |
| city | Town |
| state | Region |
| zip | Postal |
| phone | Listed phone |
| record id | Roster key |
| location id | Site key |
| reference phone | Requested phone |

2. Save mapping: inspect **2 valid, 1 quarantined**. Expand an original/normalized row and show ZIP `02108`. Download the quarantine CSV; the malformed row remains traceable and is not silently accepted. Enter reviewer/reason and **Accept valid rows**. Download original bytes or the full evidence packet.
3. Select **Synthetic clinic CSV → Load synthetic sample**. It has canonical headers and maps automatically. Accept it and explain that its scoped native keys attach later evidence to the same two site cases. The XLSX and CSV artifacts remain separate originals.
4. Open Work queue and search `synthetic-demo`. There is one provider at **NORTH** and **SOUTH**, not one provider-wide phone. For NORTH select `triage`, then `approve` proposal `6175550199`, then `submit` reference `SIMULATED-TICKET-NORTH`, then `verify` observed `6175550199` with an explicitly synthetic observation note. Supply actor/reason for each action. Show `verified` and history.
5. For SOUTH use proposal `6175550198`, submit a simulated ticket, then observe `6175550170`. The case becomes **reopened**, retaining the proposal and failed observation. Assign an owner and follow-up if desired; explain locally asserted attribution.
6. Load **Synthetic clinic workbook** again. Its committed parsing settings are reused, and it is visibly a repeat receipt. Accept it without duplicating work/history. Load **Synthetic changed delivery**: preview new/changed/unchanged/missing-from-this-delivery counts. Accept and inspect later evidence; the original snapshot/status/ownership remain intact. Absence is not termination.
7. For an optional separate reference example, choose **Synthetic NPPES response** and **Synthetic CMS clinician response** from the picker. New reference samples use distinct `synthetic-nppes-reference` and `synthetic-cms-reference` namespaces; previously retained receipts keep their original namespace. Ordinary saved-response upload can instead use a separate namespace such as `offline-reference` and the corresponding explicit profile. These are **synthetic saved-response fixtures**, not live success. Inspect native addresses/taxonomies versus enrollment/group/address grain. Accept valid observations only if appropriate. An explicit location relationship requires selecting the particular native practice location, with reviewer and evidence reason; mailing evidence is rejected. To try candidate review, choose the clinic workbook and the NPPES sample in **Reconcile**, review their entity types, explicitly create a run, and use the search and filtered handoff controls. Creating a run neither accepts the reference nor approves an identity link.
8. Open Sources to explain bounded retrieval metadata and reference limits. An optional live lookup requires network and remains separate from the offline core. Save an asserted source link to show that a URL alone is not fetched or verified.
9. In a selected work case, choose **Download case XLSX**. Inspect Cases (listed/requested/approved/observed values and ownership), Evidence (source/receipt/row locators), and Decisions (every action and assertion). **Download all work XLSX** includes every durable case, regardless of queue filters; shared receipt attempts may contain other source rows. Payloads preserve complete originals and long history details. These exports read one consistent snapshot and change no workflow state. The receipt evidence packet JSON remains available.
10. Ctrl-C the launcher, then restart using the same printed root. Show the same receipt, owner/follow-up, case version and events. Inputs, originals and work are retained; sample reload remains a repeat rather than duplicate work.

## Recovery and rollback

Before creating or opening demo storage, the launcher checks whether ports 8000 and 5173 are available. An occupied port returns a nonzero exit with an actionable message; it never reuses that service. If the API or UI exits unexpectedly (including exit 0), the launcher stops its own service groups and returns failure while retaining storage. Ordinary Ctrl-C is a successful stop. `--prepare-only` needs no free service ports and starts no services.

A failed parse stays visible: correct header, encoding, delimiter or mapping and save a new attempt. Rejecting a failed/needs-mapping submission records an explicit decision. A stale case version returns a conflict; refresh the evidence and retry with the retained draft. No action automatically closes work from later source observations.

If interrupted while processing, restart and reprocess the receipt. Atomic acceptance leaves either the entire accepted batch or none. Startup reports staged/orphan/missing artifacts without deleting them. Keep the database and matching artifact root together. Before manual restoration, stop services and restore a SQLite backup plus its corresponding artifact root into a **new** directory; inspect integrity/FK checks before selecting it. Do not overwrite originals to rehearse restoration.

### Back up and restore a stopped local workbench

The commands below require a **quiescent** current-schema source: stop the application, every API process and feed worker, and any other writer first. The tool checks for nonempty WAL/rollback-journal files and detects some changes during copying, but it cannot prove that all writers have stopped. Do not run it against a changing root. The source database and matching `artifacts/` directory must belong to the same workbench. For a separately configured `PDTL_DB`, add `--database /path/to/that-directory.sqlite3` to the backup command.

Choose two **new, disjoint directories** with existing parents. These examples are placeholders; replace them with paths you own:

```sh
PYTHONPATH=src python3 -m provider_directory_truth_layer.storage_backup backup \
  --source-root /path/to/stopped-workbench --destination /path/to/new-backup
PYTHONPATH=src python3 -m provider_directory_truth_layer.storage_backup verify \
  --backup-root /path/to/new-backup
PYTHONPATH=src python3 -m provider_directory_truth_layer.storage_backup restore \
  --backup-root /path/to/new-backup --destination /path/to/new-restored-workbench
```

The backup uses SQLite's backup API and retains every regular file in `artifacts/`, including staged and unregistered files. It checks database integrity, foreign keys, each registered artifact's digest and size, and source/copy inventories. A manifest stores checksums and schema version; the read-only `verify` command checks an existing stopped backup without restoring it, and restore performs the same checks before and after copying. Verify again after transferring or storing a backup, with no writers accessing it. These checks detect mismatches, not malicious tampering, and do not replace a restore rehearsal. Backup and restore refuse existing or nested targets and symlinked artifact files; they never delete the source or an incomplete destination. If an operation fails after creating a target, inspect it and choose a different new path; a backup without its completed manifest cannot be restored.

The database and artifacts may contain private records. The new backup and restored directories are created with owner-only permissions, subject to filesystem behavior; store and share them accordingly. Generated `exports/`, demo `inputs/`, inbox directories, configuration outside the database, and application dependencies are **not** included. Restore does not replace the source or automatically start a service. Feed settings—including absolute inbox paths and enabled state—remain as recorded in the database: **review and, if appropriate, reconfigure those paths before running any restored worker**, so it does not inspect an unintended live inbox. Review pending jobs and use isolated inputs for a rehearsal. Opening the restored root for normal work changes it and it is no longer the immutable backup; keep the backup separately.

If a nonempty WAL or rollback journal remains after shutdown, do not remove it. Preserve the database and all sidecars together, investigate or recover a separate owned copy using SQLite, and only then make a verified backup from the stopped, recovered copy. The tool does not checkpoint or repair the original. See the tests in `tests/test_storage_backup.py` and the restored-job recovery test in `tests/test_managed_feed.py` for supported boundaries; concurrent writers and arbitrary damaged databases are not qualified.

Legacy QA and Corrections views remain available for the original deterministic payer-precedence demonstration. They use current generated QA evidence and original remediation snapshots rather than the new intake identity/version contract. See the [API compatibility reference](../API_REFERENCE.md).

## Recurring clinic rehearsal

1. Receive a synthetic canonical clinic CSV. Review valid/quarantined rows and the column mapping. Expand **Save this validated mapping as a revision**, enter name, mapping reviewer and mapping reason, and save. This does not accept rows.
2. Enter the separate acceptance reviewer/reason and accept valid rows. Upload a later CSV with reordered known columns and a changed phone under the same source namespace.
3. Select **Saved mapping revision → Apply saved mapping and reprocess**. Expand the comparison and inspect the named prior accepted delivery, raw/unique counts and old/new values with locators. Filter changed, missing and blocked-invalid separately.
4. Accept explicitly. If another accepted delivery makes the comparison stale, **Refresh comparison**, review new previous values and retry. A missing required header blocks acceptance until a new mapping is reviewed; extra columns stay in the retained source.
5. Download the evidence packet to inspect complete comparisons and revision IDs. Stop/resume the printed demo root; originals, revisions, work ownership and human history persist. Repeat delivery reuses the same accepted interpretation.

## Guided multi-file network demonstration

Start `make workbench` in a fresh root, or resume the printed root with `PYTHONPATH=src python3 scripts/demo.py --root .runtime/operations-demo-REPLACE_ME`. Resuming retains existing inputs/database/artifacts; it does not reset work. Existing clinic/reference samples remain available.

1. Complete the unfamiliar clinic workbook path above: choose header row 2, review suggested columns, save a mapping revision, inspect **2 valid / 1 quarantined**, then accept valid rows explicitly. Clinic location evidence and network participation are distinct; this demo does not infer a cross-source membership or compare the feeds by NPI alone.
2. Click **Prepare synthetic network catalog** in the offline sample panel. The explicit action creates a versioned synthetic codebook: one payer, CEDAR/PINE, one clinic and NORTH/SOUTH. It imports/accepts/verifies no rows. Repeated setup is idempotent; a binding that an operator subsequently reviewed differently is preserved and setup returns a conflict rather than overwriting it. Use a fresh demo root for an untouched codebook.
3. Choose **Synthetic network baseline CSV**, load it, and click **Use suggested network scope**. This fills the form only. Open **Column mapping and parsing**, inspect network/location/clinic bindings and save mapping/reprocess. There are **3 valid** distinct assertions: CEDAR/NORTH, CEDAR/SOUTH and PINE/NORTH for the same synthetic clinician.
4. Save a named mapping revision with mapping reviewer/reason. Apply it, then use the separate acceptance reviewer/reason to accept the three assertions. Loading, saving, applying and accepting are separate actions. Source-listed status is not human verification.
5. Load **Synthetic changed network CSV** and apply that revision. The file reorders rows/columns and retains a new unmapped delivery_note. Inspect **5 raw rows / 3 unique resolved identities**, **2 valid / 3 quarantined**, one changed, one new, two blocked duplicate/conflicting rows, one unresolved and one missing baseline record. The baseline is the named previous accepted delivery; it is never synthesized from several historical files. Accept valid rows explicitly. The missing CEDAR/SOUTH and contradictory PINE/NORTH create QA comparison work; unknown network code remains receipt quarantine. No membership is removed or verified automatically.
6. Open Work, choose **Network filter** and optionally organization/practice location. Open accepted, validation and missing cases, inspect source status/dates and separate comparison evidence, assign an owner/follow-up and explain the action. Existing case status/owner/history/initial source values survive later deliveries.
7. Download the selected network or case as XLSX/JSON. Check the named scope, Cases, Participations and Review evidence. Catalog/Bindings project only selected operational references. Complete receipt/attempt payloads may contain other rows as clearly labeled shared context. All-work XLSX ignores the filters.
8. Load **Synthetic network header drift CSV** and apply the original revision. Required header `phone` is absent, so acceptance is blocked. In column mapping review `phone → Published phone`, reprocess, and save/apply a new named revision with a header-change reason. Accept **2 valid / 3 quarantined** explicitly. The old revision, input bytes, initial cases and human actions remain inspectable.
9. Repeat an accepted file using the same mapping revision. It creates a visible duplicate delivery without duplicate work. Stop the launcher with Ctrl-C, resume the same root, and confirm revisions, original artifacts, work ownership/history and scoped exports. A fresh source file after a binding change requires renewed review; stale baseline/binding acceptance returns 409.

A later accepted baseline contains that delivery's valid observations only. Older observations remain durable evidence but are not silently backfilled into the next baseline. Missing means absent from a declared delivery, including a full empty snapshot when explicitly accepted as absence evidence; it never means terminated. The final receipt (historical reference retained separately) records measured checks and exact operator/recovery evidence.

## Extended three-source ingestion and follow-up demonstration

This 2026-10-30 scenario uses the [synthetic combined-workflow fixtures](../../web/e2e/fixtures/ingestion-platform/README.md). NPPES-shaped JSON is an offline fictional response, not a fetched registry result. Allow time to inspect the explicit decisions; the original five-minute scenario above remains a shorter entrypoint.

1. Launch a fresh `make workbench` root. Click **Prepare synthetic network catalog** to establish synthetic CEDAR/PINE, NORTH/SOUTH and CLINIC code bindings. This prepares catalog assertions only. Use separate source namespaces for clinic, payer and reference inputs; for the built-in codebook use `synthetic-network-demo` for the payer upload.
2. Upload fixture `clinic.csv` as a flat file. Open **Profile and normalize**, use suggested columns and explicitly choose phone/state/ZIP rules. Inspect `2125550101` plus extension `004`, ZIP+4 and original strings. Save a proposed recipe with reviewer/reason, approve it, then apply the approved revision. Inspect and separately accept the two valid rows. Each action has a different decision boundary.
3. Upload fixture `payer.csv` as flat input. Open mapping/parsing, choose payer-network interpretation, map its provider/contact/participation columns and explicitly select CEDAR/PINE network, NORTH/SOUTH location and CLINIC organization bindings. Save/reprocess. Three rows are valid; the missing-NPI row remains quarantined/unlinked. Do not accept the payer rows for this scenario: retained evidence can be reviewed without inventing accepted observations or membership.
4. Upload fixture `nppes.json` using **NPPES API response** profile under a separate namespace. Inspect the mailing address and two practice addresses. Keep their paths and contacts distinct. This source also remains unaccepted.
5. Open **Reconcile**, select the three retained deliveries and create the candidate run with actor/reason. Inspect comparison values, contradictions, unknown evidence and native address purpose before deciding. Candidate ranking does not establish identity.
6. Explicitly link the six known clinician rows through five pair reviews to one labeled clinician identity, leaving the missing-NPI row unlinked. Separately approve the four NORTH address references through three pair reviews to the reviewed NORTH catalog target, and the three SOUTH references through two reviews to SOUTH. Mailing is not an operating-location target. Inspect each exact pair; equal NPI or transitive candidate chains never approve the other references automatically.
7. Open **Reconciled field evidence**, choose that clinician and NORTH. Expect three contributing sources and four approved source records. Select the clinic phone with actor/reason/acknowledgement, then append an explicit retained phone conflict to preserve disagreement. Select the coherent clinic address independently. Download field JSON/XLSX: scoped field records contain NORTH only; original NPPES row context can still contain SOUTH and mailing and is labeled shared context.
8. Open **Provider-change impact preview**, propose phone `2125550111`, extension `004`, and explicitly select the payer delivery. Save the attributed proposal and run read-only preview. Expect **2 affected / 1 unaffected within assessed scope / 1 not assessed**. CEDAR/NORTH and PINE/NORTH differ; SOUTH is a different reviewed office; the unlinked row has no current clinician link. Preview creates no work.
9. Open **Bounded follow-up plan**, preview actions and inspect two individually scoped QA targets. Enter actor/reason, acknowledge the bounded plan and explicitly confirm. The saved receipt has two new QA cases, no approved correction or observed verification. Acknowledge receipt of the CEDAR target with a separate actor/reason; case owner/status/version stay unchanged. Download complete follow-up JSON/XLSX and inspect frozen assessment, sources, events, associations and acknowledgement history. XLSX Payload equals complete JSON and cells are literal text.
10. Reapprove one NORTH native-address pair after reviewing the evidence. Refresh the saved receipt and rerun impact: dependencies are visibly stale, while the original confirmation/history remains readable. Reload the page and reopen the saved proposal/receipt; no duplicate confirmation or work is created. A changed intent requires renewed evidence review and a new proposal revision.
11. Stop the launcher with Ctrl-C before a process-recovery rehearsal. Resume the same root with the normal launcher and inspect the same history. A repeat upload gets a separate receipt and must not inherit reviewed crosswalks automatically. For an automated owned-copy rehearsal, use the command below; it requires quiescent current-schema synthetic storage, a default-choice confirmation and a new disjoint destination. It rejects pending WAL data instead of changing the source. New output files live in a fresh evidence directory; prior downloaded artifacts are preserved.

```bash
PYTHONPATH=src python3 scripts/rehearse_ingestion_recovery.py \
  --source-root .runtime/YOUR_STOPPED_DEMO_ROOT \
  --root .runtime/NEW_RECOVERY_COPY
```

The combined qualification (historical reference retained separately) records actual browser/download inspection, independent matching/impact scope, populated migration and separate-process recovery. Repeat/reinterpret/restart are preservation checks, not external update or production-scale claims. The executable UI reproduction is `npm run test:e2e --prefix web -- ingestion-platform.spec.ts` with the repository dependencies available.

## Managed recurring clinic feed demonstration

This is an offline synthetic source-to-consumer demonstration. Use a **new** root; preparation rejects existing roots. It prepares originals and an explicitly labeled approved normalization recipe, but registers no feed and accepts no dataset.

```bash
PYTHONPATH=src python3 scripts/prepare_managed_feed_demo.py --root .runtime/my-managed-feed
PYTHONPATH=src python3 scripts/demo.py --root .runtime/my-managed-feed
```

1. Open `http://127.0.0.1:5173/?view=feeds`. Enter a reviewer and decision reason. Expand **Register a clinic CSV feed**, select **Synthetic weekly clinic**, enter the absolute inbox printed by preparation, owner and first period `2026-10-05`. Register the disabled feed.
2. Select the compatible recipe under **Recipe for new contract** and propose it. Inspect required headers, 20% row-count policy and recipe ID. Approve the contract, then explicitly **Enable with this contract**. These decisions accept no observations.
3. Choose **Check deliveries and process one job**. The baseline manifest is already in the inbox. Open its candidate; expect 3 raw/valid unique keys, no quarantine and an explicit first-baseline warning. Inspect original/normalized rows and approve the dataset version with a reason. Download its exact approved JSON.
4. Copy `changed.csv` from `later-deliveries/` to `inbox/`, then copy `changed.manifest.json` last. Check deliveries. Its candidate has 3 valid rows and one changed phone. The consumer retains the original approved version until you approve the new one. Earlier version downloads stay unchanged.
5. Copy `row-drop.csv`, then its manifest last. Check deliveries: 1 valid row, 2 missing prior keys and a 66.7% raw-count drop. Approval stays disabled. Defer a hold to retain it, or acknowledge each exact-report risk with a reason; quarantined/absent rows never become valid. Explicitly approve only if that incomplete source coverage is acceptable for the synthetic demonstration.
6. Copy `header-drift.csv`, then its manifest last. Check deliveries and open the candidate: `phone` is absent from the contract. Raw count is retained; interpretation counts are not assessed. This hard blocker cannot be acknowledged. Reject the candidate or supply corrected bytes under a new delivery ID; retain the original. The prior approved dataset remains available.
7. Stop and resume the launcher on the same root. Review job/exception/decision history and repeat the delivery check: previously discovered deliveries are reused. Do not run preparation again on the retained root.

To run recurring discovery without pressing the one-pass button, use a second terminal against the initialized root:

```bash
PYTHONPATH=src python3 -m provider_directory_truth_layer.feed_worker --root .runtime/my-managed-feed
```

Ctrl-C stops that worker without deleting storage. Add `--once` for one discovery/processing pass. It attaches without migration or blanket recovery. One worker lane owns execution; persisted claim tokens/heartbeats and fenced publication protect retries. Reopen the workbench first after a future schema upgrade. An application process must be running to process deliveries; no OS scheduler or external notification is installed.

For failures, inspect discovery issues and job errors. Failed/cancelled jobs may retry pinned inputs with actor/reason; changed contract/current baseline requires a new **Reprocess with current contract** job. Older-period/as-of candidates cannot regress current approval. Original source assertions, approved consumer datasets and clinic correction verification remain separate. This demonstration sends no payer updates and publishes nothing.


## Connected managed delivery to follow-up

Use a fresh launcher-owned root (`make workbench`) for practice. The default page is Managed feeds; Intake remains available for first-source setup. Existing roots can be resumed explicitly and must not be reseeded or cleaned.

1. In Intake, receive the synthetic `web/e2e/fixtures/ingestion-platform/clinic.csv` under a deliberate clinic namespace and dataset scope `connected-operations`. Profile the file, review the suggested columns, explicitly apply `phone_us`, `state_us` and `zip_us`, inspect the preserved extension/ZIP+4, and propose/approve the recipe. Applying the recipe and accepting its rows remain separate actions. The extended three-source procedure above describes these existing controls.
2. Register a managed feed for the same source/scope and a new owned inbox. Propose its contract using the approved recipe; separately approve and enable the approved contract revision. Follow the managed-feed manifest procedure above. The demonstrated baseline has both NORTH and SOUTH rows; the next period changes NORTH's phone but omits SOUTH. Keep filenames/delivery IDs distinct and finalize each manifest after writing its CSV.
3. Explicitly process and approve the baseline. Process the partial second delivery: one missing prior key and the 50% row-count drop produce review holds. Confirm that the previous approved JSON remains available and byte-identical; absence is not evidence that SOUTH closed. Reject the partial candidate. Deliver a corrected full roster that retains NORTH's changed phone and includes SOUTH, inspect it, and explicitly approve that version.
4. Bookmark the selected feed/version. Back/forward and reload restore that exact selection. **Inspect this version's retained evidence** opens its exact receipt/attempt read-only; a newer interpretation is flagged, never silently substituted. Use **Open current receipt workspace** only when intending to inspect or reprocess the current attempt.
5. Receive the synthetic payer CSV and saved NPPES-shaped JSON using the extended three-source procedure. Return to the approved feed version and choose **Prepare reconciliation from this approved version**. That clinic interpretation stays pinned. Reconcile refreshes its source list on entry; wait for the refresh to finish and retry if it fails. Choose the other two source receipts, using receipt ID and time to distinguish repeated filenames, inspect their evidence and supported entity types, then explicitly create the run. Search for the synthetic clinician's identifier, export the filtered candidate evidence, reload the bookmarked search, then clear it before reviewing the full set. Search and export make no decisions. An invalid or stale approved-version context requires renewed selection rather than switching its attempt silently.
6. Review clinician and NORTH/SOUTH location links independently. Open reconciled field evidence, select the reviewed clinician/NORTH location, retain or resolve the phone conflict, and explicitly propose the NORTH phone change. Run the read-only assessment against chosen payer/native inputs. Review affected CEDAR/PINE NORTH listings, unaffected SOUTH within selected scope, and unlinked evidence that remains not assessed.
7. Preview and explicitly confirm the bounded follow-up plan, acknowledge receipt independently, and inspect complete JSON/XLSX. **Open work case** carries the originating review context; its return link restores the saved follow-up. Reload restores the same saved receipt without creating another plan or rerunning an impact preview. A later link/source revision visibly stales dependencies while retaining history.

The actual desktop/phone regression is `web/e2e/ingestion-platform.spec.ts`; it uses owned source inboxes, original synthetic fixtures, normal processing/approval services and real interface decisions. Run it after installing the existing dependencies:

```sh
source .venv/bin/activate
npm run test:e2e --prefix web -- ingestion-platform.spec.ts
```

The browser fixture owns its database/artifacts and does not use a working demo root. Unknown feed/version/receipt/attempt, mismatched proposal/follow-up and missing references must show recoverable errors. Navigation does not approve, link, create follow-up or verify provider facts. Source data, approvals, identity links, change proposals and acknowledgements keep their separate meanings.

## Evidence-reason triage

Open a saved Reconcile run. Choose candidate type and review eligibility, then use **Evidence reason** to isolate a recorded question such as **NPI missing** or **NPI conflict**. Each option's count covers the complete current type/eligibility selection, before reason filtering and paging; a pair may carry several reasons. The visible summary shows filtered versus selected-subset totals.

Open a candidate and inspect its original evidence, contradictions and missing fields. Use the existing explicit identity review to record an evidence-supported decision or defer unresolved inputs; a filter is not a link approval. Missing identifiers do not establish agreement, and conflicting identifiers remain visible. **Clear evidence reason** restores the complete subset. Changing candidate type or eligibility clears its reason. Bookmark/reload/back and the follow-up work-case return path preserve run/filter context.

The synthetic qualification (historical reference retained separately) distinguishes candidate retrieval from strict eligibility. It demonstrates focused review views without claiming fewer total cases, faster human review or improved real-world matching accuracy.


### Find and hand off a filtered queue

Enter a provider name, NPI or source-native ID in **Find a provider or identifier**, then choose **Search candidates**. The applied search looks at both sides of every saved candidate, including candidates on other pages; it does not infer a match. Candidate summaries identify each side's source, available source location label and row locator so similar names can be distinguished before expansion. Location candidates can also show their exact source address/path; clinician summaries avoid presenting an arbitrarily selected address as the person's reviewed location. This context is not an approved identity or location link. Reason counts reflect the search and the selected type/eligibility before the reason filter. Clear or resubmit the search as needed. Applied search text is retained in the address, browser history and bookmarks; draft edits are not applied until submitted. Treat links and filtered exports as potentially sensitive when they include names or identifiers.

Choose **Download filtered candidate evidence (JSON)** to save all pairs in the applied selection, not just the visible page. Its scope records the selected filters and its records retain the comparison evidence for each selected pair. Identity review decisions and the full run export are separate. The file contains source evidence and the applied search term, so check its contents and intended destination before sharing.
