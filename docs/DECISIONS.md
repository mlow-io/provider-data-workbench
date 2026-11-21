# Architecture decisions

Original decisions begin 2026-10-23; product-scope decision added 2026-11-14. Earlier entries describe their implementation checkpoints. The dated scope revision below is a target decision, not implementation or healthcare compliance evidence.

## ADR 001: Retained evidence and transactional work

Accepted. `IntakeStore` separates artifacts, deliveries, interpretation attempts, native observations, relationships, work projections, later evidence, and events. An original case snapshot never changes after creation; later observations attach separately even when a discrepancy disappears. Approval, simulated submission, observed verification, and failed-verification reopen remain distinct decisions. QA resolution is not correction verification.

Acceptance commits all valid observations and linked work together under `BEGIN IMMEDIATE`. HTTP acceptance requires the attempt that was previewed; repeated acceptance of the same attempt is idempotent. Work events require the expected case version and update the projection and append history in one transaction. Database triggers prevent work-event update/delete through ordinary SQL. Actor/reason are asserted locally, without authentication.

Legacy QA/remediation IDs, tables, and events remain intact. Legacy QA detail still depends on the current generated batch; missing historical originals are not reconstructed. The new durable Work queue is the intake path. Preserving this compatibility boundary avoids falsely relabeling old snapshots as original artifacts.

## ADR 002: Explicit identity and coherent location evidence

Accepted. SHA-256 identifies bytes, not providers. A repeat artifact creates another receipt and can reuse a committed interpretation. A changed mapping creates a new attempt. Scoped native provider/location/listing identity reuses work across reordered or changed deliveries. Inadequate native identity remains unresolved.

An exact NPI supports a provider relationship, while a supplied source location key or human-reviewed crosswalk establishes operating-location scope. Multi-address public records retain their source grain; linking requires selecting one native practice address. Mailing evidence cannot establish an operating site. Address components stay together. There is no automatic merge, inferred termination, or cross-location field assembly.

Initial 2.0 operational comparison is a location phone requested-versus-listed discrepancy using explicit `reference_phone`. This is deliberately narrower than a generalized multi-source field reconciliation engine. The existing synthetic payer-precedence workflow remains available in compatibility views.

## ADR 003: One local API and bounded synchronous work

Accepted. `intake_api.create_workbench` composes existing review/remediation routes with intake/work/source endpoints on port 8000. Vite on 5173 proxies to it; a configurable API origin supports isolated browser tests. React has persistent navigation, URL-backed work filters, bounded evidence samples, and conflict recovery that retains draft inputs.

Parsing runs in a request worker thread with a persisted processing-attempt marker. Restart marks unfinished attempts interrupted and permits explicit replay. This replaces the proposal's separate persistent worker with a smaller equivalent recovery model. Measured 20,000-row CSV acceptance took about ten seconds locally; a separate queued worker is a revisit point if real workloads need progress/cancellation or longer asynchronous work. Multiple HTTP requests can parse concurrently; SQLite serializes acceptance writes. No throughput guarantee for concurrent writers is asserted.

## ADR 004: SQLite and artifact recovery

Accepted. `storage.py` configures foreign keys, WAL, and a ten-second busy timeout per connection. Numbered transactional migrations add the intake schema (v1) and native location crosswalk index (v2); future versions fail explicitly. SQLite backups precede legacy/v1 upgrades, and tests rehearse preservation, rollback, restart, integrity and foreign-key checks.

Artifact writes use generated digest keys, fsync and atomic rename. The ledger registers finalized bytes. Startup reports staged/unregistered/missing files to `artifact-recovery.json`, retaining them for inspection instead of deleting or accepting them. This favors evidence preservation over automatic garbage collection. Original files and working databases remain outside disposable test/demo roots.

## ADR 005: Explicit public adapters and offline replay

Accepted. Pure flat/NPPES/CMS adapters return original/native/normalized evidence and locators without database writes. The shared intake service handles HTTP uploads and public reads. Bounded owned-host HTTPS fetches cap records/bytes, enforce timeouts and bounded transient retries, retain request scope and CMS dataset metadata, and distinguish API failures from empty successful responses. Error bytes are retained when available, explicitly flagged if capped.

A lookup can reuse a retained response for fifteen minutes, producing another receipt with `retained_response` provenance. Explicit `refresh` bypasses reuse. Saved JSON uses the same parser/acceptance contract, but remains a replay, not live success. Publication, source update, retrieval, and human verification retain separate meanings. This initial decision deferred FHIR; the later D1/D2 decisions add its bounded reference path.

## ADR 006: Verification without destructive setup

Accepted. `PDTL_ROOT`/`PDTL_DB` configure owned paths across services and CLI. Service startup does not seed; validation gets a new directory each run. The demo launcher defaults to a fresh directory and resumes only when an explicit root is supplied. Browser setup uses new storage, no unknown-server reuse, sequential mutable scenarios, and separate synthetic source scopes. CI runs the same browser suite and retains failure traces. No checks require working runtime deletion.

## ADR: reviewed recurring mappings and a single accepted baseline

Keep recurring files in the existing receipt/attempt/observation service. Schema v3 adds immutable templates rather than rewriting previous mappings or creating another import subsystem. Every application of a template creates a retained attempt; source/profile/scope checks prevent accidental reuse across feeds. Header drift blocks acceptance, while unknown columns remain original evidence.

A preview selects one accepted attempt and records its ID. Acceptance rechecks that ID in `BEGIN IMMEDIATE`, which serializes the baseline check with observation/case writes. This avoids accepting a comparison that went stale after another delivery. Repeats do not create a new baseline; interpretation identity excludes the preview context but includes mapping revision. Prospective changes use valid unique rows, with invalid known identities explicitly blocked and unresolved rows unable to hide absence. Existing native public-reference comparison semantics remain separate.

## ADR: explicit source-bound participation identity

Use a small create-only organization/network/location catalog and append-only typed source bindings. Equal labels remain distinct opaque IDs. A reviewed binding references exactly one existing target through SQLite FKs; correcting it appends a revision with expected-current protection. Every network interpretation retains the binding snapshot and mapping revision in its fingerprint. The accepted row preserves the source codes/labels/dates and the local references separately.

A participation key includes source dataset, native record key, provider, local practice location and local network. This prevents one NPI or native key from collapsing multiple sites/networks. A fixed network is explicit configuration; a contradictory row is unresolved rather than evidence of presence in that default network. Unknown bindings stay quarantined. Baselines require equal declared network scope, and acceptance checks both baseline and binding freshness in the same transaction. No historic clinic evidence is silently converted into membership.

## ADR: source comparison work without fabricated membership

Keep accepted participation observations separate from missing/quarantined comparison evidence. Known scoped invalid identities and missing baseline keys create distinct QA case kinds, with original row/baseline locators and incoming receipt links; unknown bindings stay receipt quarantine. Cases without an accepted observation are legitimate review work and expose that absence explicitly. Repeats preserve identity, and source evidence cannot verify/reopen/close human decisions.

Read-only exports select all durable work, one case or one network in a single SQLite snapshot. Operational participation/catalog/binding rows are scoped; complete receipt/attempt payloads remain labeled shared source context. Dataset equality also constrains repeated-byte receipt discovery and automatic mapping reuse, preventing identical files from silently carrying interpretations across unrelated feeds. The SQL runner uses the full network/provider/location/native key and rejects incompatible declared scope.

Shared writable connection contexts commit or roll back and then close deterministically; backup targets close explicitly too. Python's native SQLite context manager alone does not close a connection. Closing each completed request prevents retained connections/late WAL checkpoints; read-only exports and SQL queries still use their own explicitly closed snapshot connections.

## Declarative onboarding and shared agent operations

Accepted for schema 5. Recipes are versioned data containing allowlisted mappings and operations. Both read-only previews and real intake attempts use `interpretation.py`; the recipe cannot relax application-required fields or duplicate-key checks. Per-field transformation lineage is stored separately from normalized values, so recipe metadata cannot become a business-field difference. Proposed/approved recipes are immutable; approval and source acceptance remain distinct.

The web interface and local MCP adapter call `OnboardingService`. MCP exposes proposals but not approvals or acceptance, and attributes those proposals explicitly. It attaches via `IntakeStore.open_existing` without startup migration/recovery, avoiding interruption of another process's active attempt. The optional SDK dependency is bounded to the tested 1.x API; migration to SDK 2 is separate. This keeps the existing local Python/SQLite architecture and avoids a second ingestion backend.

## ADR: explicit candidate decisions and typed retained crosswalks

At schema 7, an identity review decision names an exact persisted candidate and pins current source baselines, comparison rule, both current typed link revisions and the previous pair decision. `BEGIN IMMEDIATE` rechecks that snapshot and appends the decision and any two approved link revisions atomically. A caller-provided request ID and full-content hash make uncertain identical retries return the original result; reusing an ID with changed content conflicts. The saved result remains retryable after later source changes.

Approving a clinician pair creates/selects an opaque clinician identity. Approving a location pair explicitly creates/selects a practice-location catalog ID. Neither implies the other. Both retained references are linked only by that explicit approval; other candidates and later deliveries remain unlinked. Reassigning a retained reference appends a revision and retains the old target's history. Existing operational provider, source binding, case and network keys are never rewritten.

Reject/defer records a pair review decision; it does not revoke a previously approved crosswalk. The interface states this consequence. A reviewer may explicitly approve a same-type conflicting candidate after reviewing its evidence; clinician approval requires explicit clinician type on both sources and location approval requires explicit practice-address purpose. Unknown or incompatible types must be resolved before approval; eligibility is not an authorization policy or identity certification. New identity labels are local reviewer assertions; identifiers remain source evidence. This keeps a manual correction path without silently treating rule ranking as ground truth.

## ADR: scoped field preferences with separate evidence and review snapshots

Use current reviewed clinician links for names/NPI; phone/address views require their exact intersection with current address-specific location links. Preserve each source/network assertion independently. Store one source reference/value or an explicit unresolved conflict per field; keep phone/extensions and address components together. Arbitrary edits and precedence inference are outside this decision surface.

Evidence snapshots include relevant link revisions, source interpretation states/baselines and comparison rules. A separate reviewed-view snapshot additionally includes current field-decision IDs, preventing an unexpected intervening decision from changing a write/export. Field staleness compares evidence snapshots, so selecting an address does not stale an unchanged phone preference. All writes use immediate transactions, exact idempotency keys and immutable revision chains.

Exports use one read transaction and an explicit expected view snapshot. Scoped assertion records remain separate from complete original-row context, which can contain other native addresses. JSON is authoritative; the XLSX includes readable review sheets and lossless JSON text chunks for long/control/type-safe evidence. Stale preferences remain history and are not presented as active selected values. Explicit null/blank preferences remain source assertions rather than certified absence.

## ADR: explicit change intent and conservative known-dependency impact

A typed proposal pins the current reviewed field context and explicitly selected retained inputs; a proposed value never updates evidence. Keep original and canonical target values, prior selection/conflict evidence, input/rule/baseline pins and immutable revision ancestry. No arbitrary expressions or unreviewed type inference are introduced.

Assess only current explicit clinician/location links over the retained scope. Different known clinician/office or already-equal values are unaffected within that scope; absent/ambiguous/stale links and excluded/unknown network scope are not assessed. Names/NPI target one retained clinician row regardless of native-address count. Phone/address target an exact address reference. Distinguish selected receipt/attempt lineage from reused accepted-observation lineage when traversing work. Never infer existing native-address work scope from an observation row alone.

Preview is read-only and deterministic for the dependency snapshot, including current reviewed links/source states/field context and related work versions. A separate explicit I2 confirmation must persist the assessed plan and create/associate follow-up atomically; rendering a preview cannot create work. Synthetic scoped precision/recall is reported together with unassessed coverage and does not establish external directory completeness.

## ADR: atomic follow-up confirmation and independent receipt acknowledgement

Schema10 freezes complete impact/action plans under one immediate transaction and one immutable confirmation per proposal. A request-ID-independent full intent hash permits safe identical-intent recovery with a new UUID; altered intent conflicts. Recheck source/link/field/work freshness before the first confirmation. Plan rendering remains read-only.

Group only explicit unique source-native identities inside typed/network/source-location scope; use retained-reference fallback for missing/duplicate IDs and CMS. Preserve all grouped evidence refs. Reuse one eligible open case without touching its owner/status/proposal/evidence/history; require explicit resolution of multiple open matches. Closed work remains closed; new work is QA review, not an approved correction. Keep association scope separate from source participation and expose it consistently in queues/details/exports.

Receipt acknowledgement is its own immutable version-checked chain and never changes case state. Pinned complete exports include frozen intent and current work/acknowledgement separately, plus assessment/prior-field/initial-work source context. Literal-text workbook payloads preserve exact JSON. This avoids treating confirmation, receipt, acceptance and verification as the same event. Qualification (historical reference retained separately).

## 2026-10-30 — One SQLite-backed managed feed and atomic dataset promotion

Use the existing Python/SQLite/React architecture for one weekly clinic CSV inbox feed. Immutable contract revisions reference reviewed normalization recipes; they do not introduce another transformation language. The producer supplies a finalized manifest, source delivery identity, period/scope/as-of and digest. Byte identity, delivery identity, execution attempts and approved dataset versions remain distinct.

Jobs persist stage IDs, claim tokens/leases, heartbeat, retry times and append-only events. One nonblocking OS file lock serializes local worker execution across CLI and explicit HTTP passes. The lock prevents overlap inside existing intake operations; token/expiry checks fence result publication after cancellation/reclaim. Processing occurs outside short claim transactions. At-least-once execution is acceptable because retries reuse stage IDs and database uniqueness prevents duplicate logical results. There is no distributed queue or installed system scheduler. This relies on a local filesystem and SQLite; network/distributed workers are unsupported.

Expose intake acceptance as a caller-owned transactional operation. Dataset approval validates pinned report/current/config/contract and accepts valid source observations plus the approved-version pointer in one write transaction. Receipt ownership blocks manual mapping/acceptance bypass. Consumer exports read immutable version snapshots, never a receipt's latest interpretation. Explicit exception acknowledgement accepts soft risk only; hard blockers and quarantined rows cannot be waived into valid output.

Compare managed quality against the previous approved feed attempt (dereferencing reused accepted interpretations), preserving legacy manual-intake baseline behavior. Config/baseline changes require a new processing job/report; old versions and decisions remain intact. Schema 11 is additive with a SQLite backup; populated upgrade and interrupted transaction/process tests cover preservation. Reviewer identities remain local assertions. See the managed-feed qualification receipt for actual evidence and limits.


## Connected operations context — 2026-10-31

Keep selections in additive URL parameters and durable evidence/decisions in existing SQLite records. Feed/version identity is validated before reconciliation preparation; the approved seed is pinned and cannot be replaced with a newer interpretation under the same provenance label. Cross-scope proposal/follow-up references are rejected. Saved follow-up is restored through read endpoints independently of a newly requested impact preview.

Exact historical intake reads add optional `attempt_id` to the existing detail endpoint. One read transaction pins selected preview/observations/case links; no migration or new domain entity is required. URL restoration never approves or creates domain records. Asynchronous selection and action continuations are guarded against navigation, and cached follow-up reads include proposal scope in their keys.

The product remains a dependable local operator tool. Complete the connected workflow, then improve evaluated reconciliation misses and review effort before adding sources. Preserve optional MCP while deferring agent enhancements and hosted multi-user operation. Public adoption requires reviewed public ancestry and safe generated metadata; that external gate does not block isolated local development.

## ADR: Structured outreach within the existing case

Use work_event payload JSON for contact evidence and the existing expected-version transaction. A contact is an assertion and cannot change correction state or assignment. This keeps one investigation history and avoids a second case or communications subsystem. Render readable contact history and derive scoped investigation exports in the same read snapshot as source evidence. Retain historical payload compatibility; no database migration.

## 2026-11-14 — Provider-data operations with bounded interoperability and assistance

Accepted as product direction; implementation planned in D1–D4. The investigation workflow is a valuable review loop, but an investigation-only purpose omits existing ingestion, normalization and controlled-dataset capabilities. Restore those as first-class product responsibilities and connect them through one clinic-to-payer evidence journey. The qualified application and H1 evidence remain intact.

Supersede ADR 005's indefinite FHIR deferral, the connected-operations deferral of agent enhancements, and the H1-only restriction on new work with the explicit sequence in [ROADMAP](../ROADMAP.md). Preserve their other constraints: original evidence, separate decisions, shared service validation, public ancestry and single-user local operation. This documentation revision does not implement the additions.

Choose saved FHIR R4/Plan-Net evidence before bounded network acquisition because resource/relationship correctness can be tested offline independently of transport failures. Support a named subset and produce validation diagnostics; do not flatten every resource into the clinic-row required-field contract or claim general FHIR conformance. Preserve a consumer's prior approved dataset under partial or failed imports.

Use the existing recipe proposal interface for one evaluated model-assisted mapping task. Model output is untrusted input to deterministic validation and human review. A tool-enabled MCP server alone is not proof of a useful AI product; retain actual invocations and compare with current non-model suggestions. Defer other AI tasks until this task demonstrates benefit.

Retain the Python/React/SQLite architecture. Network protocol support already exists through NPPES/CMS; add a source-specific Plan-Net adapter, not a generic crawler or plugin framework. Scraping and additional transports need a concrete source gap. Authenticated team deployment and FHIR serving/writeback require separate contracts.

## 2026-11-14 — Contract ownership and incremental integration

Use [ARCHITECTURE](ARCHITECTURE.md) for shared C1–C6 boundaries and [SPEC_DRIVEN_DELIVERY](SPEC_DRIVEN_DELIVERY.md) for ordered work packages and acceptance traceability. Keep product behavior in SPEC, one active slice in NEXT and verified outcomes in STATUS. Existing area/API/data references remain their authoritative homes; the new FHIR contract owns only the new native-resource behavior.

Begin D1 with one bounded readiness pass because current acceptance assumes clinic fields and current comparison references assume row/address evidence. Resolve persistence, multi-resource provenance and profile-specific acceptance before implementing dependent code. Integrate backend, UI and exports within D1; D4 is the final combined rehearsal, not deferred integration. Keep later endpoint/model interfaces provisional until their own readiness slices. No application implementation is recorded by this documentation decision.

## 2026-11-14 — D1 native evidence reuses retained attempts and observations

Selected for implementation, not yet implemented. At the bounded 1,000-resource scope, retain source-native resources in attempt rows and reference/assertion/coverage data under a versioned native preview envelope. Reuse observations with nullable provider/location projections and a profile-specific `reference_resources` acceptance branch. No schema migration or second ingestion database is planned. Do not run automatic clinic work/participation generation for these resource observations.

Anchor derived clinician/location comparisons to Practitioner/PractitionerRole locators, carry explicit per-field supporting resource references through decisions and exports, and keep raw Network references separate from reviewed local network IDs. Limit initial office-phone projection to Location telecom. Full native data remains retained even where a comparison is unsupported.

This trades broad graph-query capability for bounded, auditable reuse of existing storage. Revisit indexing only with evidence that bounded reads/exports need it. Acceptance, retry/conflict behavior, interface examples and validator pins are frozen in [the FHIR contract](FHIR_INTAKE_CONTRACT.md). Old profiles keep their existing semantics; D1.2 must prove compatibility and no unintended work or dataset promotion.

## 2026-11-14 — Continue native integration with explicit incomplete validation

The offline parser and inspection CLI are implemented. Pinned validator 7.0.5 rejected the authored mixed Bundle and found no errors in the standalone Location, with two unavailable-USPS-terminology warnings. Retain both reports and the exact limits. D1.1's broad standards gate remains open; do not label profile/terminology validation complete. D1.2 may proceed through independent storage/API work, preserving `not_run`/unavailable statuses and existing human review boundaries. This changes execution ordering only; D1 and D4 cannot claim conformance or qualification from parser tests.

## 2026-11-14 — Native review panel and headless browser qualification

Expose FHIR resource semantics in a separate lazily loaded Intake panel while retaining the existing navigation and Reconcile field decisions. Native acceptance owns a stable request ID per exact intent, retains drafts after uncertain errors and exposes explicit reprocessing/read-only history. Keep resource coverage and unresolved scope visible; collapse resolved-reference detail. Do not route native resources into clinic mapping or validated-dataset controls.

D1.3 passed component/build and full desktop/phone headless browser checks, with inspected downloads and screenshots. This verifies the implemented synthetic journey, not human usefulness or complete standards conformance. The D2 source-readiness pass records reachable HAP R4 metadata, provider-query throttling and a source-advertised version mismatch; bounded controlled transport work may proceed while real provider-data interoperability stays open.

## 2026-11-14 — Persist bounded FHIR acquisition before derived intake

D2 uses schema-12 acquisition/checkpoint and append-only event tables, existing hashed artifacts and the existing local worker OS lock. This permits durable page/error retention and delayed retries without placing acquisition state inside human-review decisions or adding another queue system. Store exact response artifacts and an explicitly derived searchset with resource-to-page origins. Publish receipt, parsed attempt and acquisition result atomically; ordinary reference acceptance remains separate. Default source configuration is fixed and provider-resource paths are allowlisted. A test-only injected loopback source supports real controlled HTTP tests without exposing arbitrary URL configuration through the API. Full bounds and states are owned by PUBLIC_DATA_SOURCES.

## 2026-11-14 — Preserve previous backup readability across schema 12

Keep verification and restore support for schema-11 archives when adding schema 12. The manifest's declared supported version must match the actual stopped database; hashes, artifact inventory, integrity and foreign keys remain checked. Restore copies to a fresh root and leaves the original archive untouched. Only opening the restored workbench performs the additive migration and creates its pre-upgrade backup. New backup creation still requires the current schema. This prevents the acquisition extension from invalidating the preceding qualified recovery workflow.
## 2026-11-14 — D3 optional mapping invocation

Use one explicit, bounded OpenAI Responses request and the existing recipe proposal/review boundary. The model proposes only declared column bindings and existing operations. Keep run context and raw artifacts in an additive schema-13 ledger, because a proposal alone cannot explain input permission, uncertain calls, cancellation, usage or failed validation. Reuse the shared worker lock and artifact store rather than a new queue or plugin framework. Do not automatically replay a call with an unknown external outcome; resume journaled response processing locally. Default to disabled, require source-scoped external-processing permission and retain deterministic/manual operation. The detailed pre-implementation contract, selected model/rates, budgets and frozen evaluation rules are in [SOURCE_ONBOARDING](SOURCE_ONBOARDING.md#d30-selected-model-invocation-contract). Actual model access and benefit are unverified.
## 2026-11-14 — D4 consumer and dossier

Add one small read-only file consumer for the existing pinned managed-feed export. Validate its declared approval, schema, counts, native keys and digests against an explicit expected version; require canonical contacts rather than silently repairing values. It is an integrity/representation contract, not a trust or freshness authority. Rehearse the combined journey in a fresh synthetic root and hand off existing scoped field/investigation exports with a digest index. Keep their different decisions and shared receipt context explicit rather than inventing another case store or merging unrelated evidence. [OPERATIONS_DEMO](OPERATIONS_DEMO.md) freezes the reader and expected journey before implementation.

## 2026-11-14 — Source-wide cooldown survives capture intent

The D4 audit reproduced two ways to bypass source spacing: cancel a throttled acquisition or finish one and start another. Derive the configured base's cooldown from immutable request/response history and existing retry checkpoints; retain Retry-After even on exhausted/truncated failures. Expose the source due time and block new source requests without charging their budgets. Allow local publication immediately because it sends no request. This reuses schema 13 and the shared worker lock, with process-death, cancellation and separate-operation regressions rather than a new rate-limit service.

## 2026-11-14 — Keep source identity separate from gateway routing

A real HAP searchset advertised pagination on `fhir-prov-dir-r4.api.hap.org:443` although its documentation publishes `provider-directory-r4.api.hap.org`. Preserve the failed strict capture. Add one pinned HAP alias/default-port normalization back to the published origin, never a request to an alternate host or user-configurable alias. Preserve the advertised URI and actual request separately; directly fetched references use advertised identity in the derived Bundle so relative/absolute references remain faithful. Resolve relative references under the resource's declared REST base, with unsafe bases left unresolved. Allow only the observed true/false formatting parameter under unchanged budgets.

Add an optional source-native `_id` filter through the existing create/service/Sources flow. Page size does not cap total results, so a complete small live query needs a declared target. Validate IDs as FHIR ID text, include them in filtered scope/metadata and preserve old unfiltered semantics. This introduces no new schema, query language or source family. Tests and live receipts retain rejection and partial-cancellation behavior; an actual accepted Location is not proof of a complete directory or a reviewed identity.

## 2026-11-14 — Validate filtered response meaning before publication

A recorded `_id` query and HTTP 200 do not establish that returned matches satisfy the request. Apply a conservative page rule for filtered captures: exact type/ID on matches, separate explicit includes, and validated source outcomes. Recheck retained pages at publication so old queued checkpoints cannot bypass the rule after restart. Keep successful empty results distinct from failure and omission from termination. Preserve existing completed decisions and unfiltered semantics.

Store the versioned check/count report in immutable receipt metadata and the publication event, not a second source of mutable counters. Counts describe actual page entries; duplicate filtered copies give match semantics precedence while all raw origins remain retained. Surface the report or its absence in native review, preserving explicit acceptance and approved consumer isolation. This uses existing storage and service boundaries without a schema migration or a conformance claim.

## Portable Python defaults (R3)

Use `importlib.resources` for twelve immutable defaults required by installed commands. Keep authoritative contributor files in their existing locations and enforce an exact-byte sync check in CI. This small duplication preserves fixture history and SQL documentation without depending on checkout ancestors or adding a configuration/asset framework. Omitted CLI inputs use bundled synthetic defaults; explicit paths override them. Wheel and sdist must pass the actual operations/consumer/evaluation/SQL journey from isolated installations outside the source tree. Python artifacts do not bundle/serve the React frontend.

## Strict FHIR bytes and isolated distribution builds (R4)

Share strict decoding and bounded traversal between saved Bundles, search pages and standalone references. Reject ambiguous original keys before identity checks and revisit digest-verified raw bytes at publication; do not rely on a normalized assembly to prove its originals were unambiguous. Keep native resource/profile checks separate from decoding, preserve parser-v2 output semantics and old completed receipts, and retain exact failed responses. Build Python artifacts in an owned source copy with recorded input hashes so checkout build caches cannot silently supply stale files.

## Proposed ADR: scoped research, adaptive interpretation and exchange evidence

Proposed 2026-11-19; not an implemented decision. Reuse the current SQLite ledger, immutable artifacts, reviewed links and shared approval services for the [research/exchange extension](PROVIDER_RESEARCH_EXCHANGE.md). Adaptive interpretation produces versioned declarative mappings for known profiles. Case research has its own finite execution context and proposed findings, with all delegated work consuming one durable parent budget. External recipient acknowledgments remain separate from internal follow-up acknowledgments and observed directory state. Preserve source-native enrollment relationships instead of creating a second provider master or adopting a graph database.

This keeps integration and rollback bounded and makes source/decision lineage inspectable. The trade-off is explicit adapter work for genuinely new source semantics and a narrow connector set. Revisit storage or concurrency architecture only for measured workload or an actual hosted/team requirement. Acceptance and source access precede connector implementation.

## Selected operator-workflow cleanup

Selected 2026-11-19. Apply [the operator contract](OPERATOR_EXPERIENCE.md) before extending the interface: a task-based shell, work-queue entry, delivery decisions ahead of configuration, and readable evidence before raw payloads. Preserve existing routes, action/version guards and service boundaries. Do not expose empty research/exchange/report pages. Keep operational measures in [a separate contract](OPERATIONAL_MEASURES.md) so report populations, clocks and outcomes cannot be inferred from decorative counters. This permits focused component extraction without a service rewrite or generic UI framework.

## 2026-11-21 — Ingestion-first direction and scheduled spec revisions

Selected product direction: adaptable provider-data ingestion, explicit cleaning semantics, reusable reviewed profiles and preserved decisions. Contact review is the first practical application; licensing, expanded identity and provider/network operations follow. This supersedes the immediate PX1-first sequence without discarding its contracts or fixtures. The new ROADMAP maps legacy work and schedules explicit S1–S5 revision gates. S1.0 is a draft; P0 produces the source/workflow/UI/interface review packet. No implementation approval is asserted by this documentation revision.

## 2026-11-21 — Modular application before project extraction

Keep one application/database/artifact store with ingestion/adaptation, provider-domain and application/review boundaries. Shared services enforce HTTP/CLI/MCP decisions. Extract ingestion as a library only for a second real consumer; a future public explorer can consume an approved export or read-only API. Independent service/repository deployment requires a concrete need and compatibility/failure design. This preserves atomic approval and keeps learning focused on explicit contracts rather than additional infrastructure.

## 2026-11-21 — Reviewed adaptation and inspectable output

Learning initially means retrieval/reuse of approved mappings, profile versions and reviewed corrections, not fine-tuning or automatic truth updates. Runtime model/agent proposals are bounded declarative data; new parser code requires ordinary development review and tests before registration. Reuse the existing onboarding, recipe and assistance services. Define proposal provenance, example eligibility, drift and stale-input behavior in S1.2 before implementation.

The proposed first output is a pinned review workbook with Directory, Unresolved issues, and Sources and export details, retaining machine-readable evidence. A later recipient profile follows a named recipient's exact contract. P0 must resolve field-decision-to-dataset propagation and exact workbook semantics. React/TanStack remains the frontend baseline; shadcn/ui is a P0 candidate requiring compatibility/design review, not a completed dependency decision.

## 2026-11-21 — Authorized integrated implementation and private-history preservation

The owner authorized implementation, bounded GPT-6.1 Sol delegation, Git commits and public results, superseding P0's earlier planning-only stop. Current scope is implemented in connected slices under S1.1 with existing approval boundaries. Keep product documentation technical and exclude private preparation. Existing Git history includes personal author metadata; preserve that repository privately and publish a sanitized clean-history release with noreply metadata. Public release status does not imply completion of later roadmap or actual-model/human gates.

## 2026-11-21 — Explicit component-system migration after incremental release

The current release improved custom React/CSS screens but did not adopt the proposed UI library. Prioritize UI-W0 planning for a workbench migration using React/Vite, shadcn/ui/Tailwind and existing TanStack libraries, with an official sidebar block as a proposed starting point. Select base/theme/versions in the isolated populated spike, then migrate complete tasks and retire replaced CSS. Retain Table v8 initially because the current official table guide targets v9. No dependency or backend change is made by this planning revision. The prior field-materialization task is preserved for continuation after UI-W2.

## 2026-11-21 — Visual quality and responsiveness are migration acceptance criteria

Retain the React/Vite and shadcn/Tailwind proposal with existing TanStack libraries. Use a precise, calm operations aesthetic and make the source/decision inspector the distinctive product interaction. Freeze typography, semantic color, density and populated adverse states in UI-W0; do not treat template installation as visual acceptance. Add proposed reference/stress workloads and response/rendering/bundle measurements before production migration. Prefer bounded paging, scoped requests and measured lazy loading over a new grid or state stack. Full JSON exports currently used as small previews need explicit measurement and, if required, a separately specified bounded-preview contract preserving snapshot semantics. This review changes documentation only and reports no measured performance improvement.

## 2026-11-21 — Component-system implementation

Owner authorized migration after reviewing the visual/performance plan. Select official shadcn Radix Nova primitives, Tailwind 4, Lucide and locally served IBM Plex Sans; compose the inspected Sidebar pattern with actual application navigation. Preserve Table 8, routing and all approval services. Move major workspaces behind lazy boundaries, explicitly layer legacy CSS and retire competing primary control selectors as touched. Keep small-preview/full-export payload behavior visible as a performance follow-up. Bounded workers now default to GPT-6.1 Terra medium, with high for interaction/integration complexity, following the owner's corrected preference.

## 2026-11-21 — Qualify the existing UI before correction features

The owner prioritized UI/performance completion at 100 and 1,000 records and explicitly excluded 10,000-record testing. Isolate the correction and coached agent-evaluation drafts from the qualification release. Add a bounded sample endpoint over the existing full read-only export snapshot; retain full tokens/counts and complete JSON/XLSX behavior. Record production browser timing, finite heap and slowed-condition observations rather than inferring speed from bundle sizes. Strengthen primary hover contrast and coarse-pointer targets, and retain actual download/keyboard checks in the flow. The separate static CRUD reference informed interaction clarity; its storage, account data and code were not copied.

## 2026-11-21 — Explicit corrected candidates and inspectable export lineage

Owner selected correction/export completion after UI/performance qualification. Use the existing feed-version/approval transaction and immutable row manifests rather than another entity store or migration. Materialize one explicitly selected current office-phone assertion into a complete candidate; pin source/link/decision/base and retain extensions. Separate dataset approval rechecks those pins. Label inherited quality evidence and prohibit source reprocessing of derived jobs. Use review format 2 for a readable correction ledger and selected-source closure; keep original roster source references and prior approved exports. Uncertain HTTP outcomes reuse the exact request payload/key. Licensing, networks, bulk/address corrections and independently measured model usefulness remain separate work.
