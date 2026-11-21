# Provider Directory Workbench specification

## Purpose and users
A provider-data operations workbench for an analyst maintaining clinic rosters and comparing them with payer directories and public reference sources. Combine a functional web interface with retained ingestion, repeatable cleaning, quality review, reconciliation, approved datasets and investigation handoffs. The practical job is to turn inconsistent incoming data into a reviewable update and a usable downstream dataset without losing its source evidence.

The primary user is a provider-data or network-operations analyst. A reviewer needs to understand unresolved conflicts and approve changes; an integration engineer needs explicit source contracts, failure states and reproducible outputs. These are workflow roles, not implemented authenticated accounts. The current application remains single-user and local.

Generalization means reusable handling of declared provider-data sources and formats. It does not mean accepting arbitrary documents, inferring every source's meaning, or building a universal ETL platform. The product name remains Provider Directory Workbench.

## Implementation boundary
This specification defines the bounded local product. [STATUS](STATUS.md) distinguishes implementation, automated verification and remaining evidence; [ROADMAP](ROADMAP.md) sequences future work. The [architecture](docs/ARCHITECTURE.md), [spec-driven delivery map](docs/SPEC_DRIVEN_DELIVERY.md) and [FHIR intake contract](docs/FHIR_INTAKE_CONTRACT.md) own component boundaries, acceptance IDs and detailed resource semantics.

| Capability | Current boundary |
|---|---|
| Web operations | Connected intake, cleaning, managed feeds, reconciliation, investigations and exports |
| Heterogeneous intake | CSV/XLSX, explicit JSON envelopes and a saved FHIR R4/Plan-Net subset |
| Network ingestion | Bounded NPPES/CMS reads and one fixed payer FHIR endpoint; retained responses, pagination/reference budgets and replay |
| Cleaning and configuration | Versioned declarative recipes, preview, quarantine and separate acceptance; native resources use resource-specific rules |
| Data management | Immutable evidence, reviewed identities, approved clinic versions and traceable selected handoffs |
| AI assistance | Optional MCP/model mapping proposals through ordinary review; real-model quality evaluation remains open |
| Standards compatibility | Explicit resource/field support and pinned synthetic profile validation; broader conformance unverified |

## Connected product journey
1. Configure a source and its declared scope, delivery identity, parser/profile, mapping revision and quality rules. Distinguish transport from format: an HTTPS request and a local file may carry the same JSON representation.
2. Receive a messy clinic workbook, a recurring CSV delivery and bounded payer-directory FHIR evidence. NPPES or CMS can supply additional reference evidence; none is globally authoritative for every field.
3. Inspect schema, missing identifiers, duplicate native keys, invalid values and ambiguous relationships. Show original and proposed values with row/resource locators. Preserve leading-zero ZIPs, phone extensions and unknown/null distinctions where represented by the source.
4. Reuse a reviewed cleaning recipe or request an optional AI mapping proposal. Preview and review it before application; dataset acceptance remains a separate decision. Useful AI output reduces mapping work without inventing provider facts.
5. Review clinician and location links independently. Compare fields only within the established scope, preserving payer/network participation as a separate source assertion. Show conflicting values, dates and provenance rather than silently choosing a winner.
6. Hold incomplete or failing deliveries, keep the last approved clinic dataset usable, and expose why a candidate cannot be promoted. A bounded payer query is reference evidence, not a complete replacement directory.
7. Investigate selected exceptions, assign follow-up, record contact evidence and review correction proposals. Export a pinned approved dataset for a consumer and a separate scoped exception/investigation packet for a colleague.
8. Repeat after a changed delivery and process restart. Preserve previous versions and decisions; reject stale actions and avoid duplicate logical results.

The demonstration must include a small downstream reader of an approved export, not just successful import screens. It must show which version the reader received and why a held delivery did not replace it.

## Preserved investigation requirements
1. Retain exact supplied bytes and source scope; interpret through versioned mappings and normalization. Invalid rows remain inspectable. Explicit acceptance is separate from parsing.
2. Compare retained deliveries and sources at the correct clinician/office/network grain. Missing from a delivery is not proof of termination. Similar records are candidates until reviewed.
3. Investigate a scoped case with original evidence, later observations, owner, follow-up and accountable history.
4. Record outreach as a local assertion with actor, reason, contact time including timezone, method and outcome. Server-recorded time remains distinct. Response details and a reported phone may inform review but never approve a proposal or verify a listing automatically.
5. Explicitly triage, approve a phone proposal, record simulated submission, and record observed verification. A mismatching observed phone reopens the case. QA disposition remains separate.
6. Export a selected investigation in readable JSON/XLSX with complete scoped evidence, contact history, current assignment and last submission/verification. Label shared receipt context and local assertions.
7. Resume after restart; preserve prior evidence and decisions under repeat deliveries. Reject stale decisions atomically. Verify and rehearse stopped database-plus-artifact recovery.

## Preserved investigation acceptance case
A synthetic clinician has NORTH and SOUTH offices. A later roster changes NORTH and omits SOUTH. Review the incomplete delivery without silently replacing an approved version or closing SOUTH. Investigate conflicting NORTH phone evidence; record no answer and then an office response; explicitly propose and submit a correction. A separate observation either verifies it or reopens the case. Restart and export NORTH; SOUTH and original source bytes remain unchanged.

## Outreach interface
The implemented request/response contract belongs in [the API reference](docs/API_REFERENCE.md#structured-outreach-and-investigation-handoff). Preserve separate contact/server times, explicit response evidence, expected-version checks and append-only history without automatically changing correction state or assignment.

## Ingestion and source contracts
Each adapter separates acquisition, interpretation and acceptance. Retain exact response/file bytes, digest, source and delivery identity, scope, retrieval time, parser/mapping version, source timestamps and completeness. Failed acquisition must remain a failure; a successful empty response is a different outcome. Replays name their retained provenance and never claim a fresh network read.

Reuse existing adapters and managed-feed machinery. Add a narrow FHIR adapter rather than a connector marketplace, a workflow language or a second persistence system. Existing clinic recipes remain allowlisted data, not executable code. Quality policies and mappings are versioned; changes do not reinterpret previously approved versions in place.

New network reads must enforce endpoint allowlists, HTTPS, response/page/record/time bounds and bounded retries. Validate redirects, pagination and reference destinations before each request; do not fetch arbitrary URLs embedded in source data. Retain failed-page evidence, rate-limit responses and partial scope. Reference resolution must be bounded and must not become a crawler. Restart or replay cannot promote a partial result or duplicate a completed logical delivery. An endpoint changing between pages is not a transactionally consistent national snapshot.

The Sources workspace exposes the configured payer capture, query limits, retained progress, retry due time, cancellation and original response history. An optional source-native resource ID scopes a specific query; page size alone does not limit total results. Before a filtered capture becomes reviewable intake, check returned match identities against that request and distinguish included resources and source outcomes. Retain an ignored-filter or source-error response as failed evidence rather than a matching result. Source-specific routing preserves advertised resource identity separately from the actual allowlisted network destination. Queueing and refresh are local operations; an explicit capture step performs at most one request or final publication. Completion links to separate native-reference review. Original response bytes and assembled interpretation artifacts must have distinct labels.

HTML/PDF scraping, OCR, SFTP and object-storage transports are deferred. Add one only for a named source and demonstrated coverage gap. A future extraction adapter must retain the original document, parser version, exact field locators, uncertainty and explicit review; scraping is not needed merely to demonstrate network programming.

## Healthcare semantics and standards target
The first interoperability target is **FHIR R4 4.0.1 with Da Vinci PDex Plan-Net 1.2.0**, as a bounded directory consumer. CMS lists FHIR/Plan-Net in its Provider Directory API guidance; Plan-Net describes payer-directory exchange. These sources justify the target, not a claim that this local application meets payer obligations. See [CMS API standards](https://www.cms.gov/initiatives/burden-reduction/overview/interoperability/implementation-guides-standards/application-programming-interfaces-apis-relevant-standards-implementation-guides-igs) and the [versioned Plan-Net guide](https://hl7.org/fhir/us/davinci-pdex-plan-net/STU1.2/).

The initial declared subset is saved JSON search-result Bundles containing Practitioner, Organization (including Network), Location and PractitionerRole. The implementation brief must enumerate supported fields, references and extensions. InsurancePlan, OrganizationAffiliation, HealthcareService and Endpoint are retained as unsupported resources unless explicitly brought into a later slice; their presence must not imply their semantics were processed. Plan and network are never interchangeable.

| Domain concern | Required representation and checks |
|---|---|
| Provider identity | Keep identifier system/value and individual/organization type. NPI shape/checksum validation is distinct from registry existence, licensure or credentialing. The current intake's ten-digit check is not checksum validation. |
| Location | Preserve source-specific location IDs, address components, purpose and resource references. A provider NPI is not a location identifier. |
| Role and participation | Keep PractitionerRole's explicit practitioner/organization/location/network relationships, periods and source scope. Do not make an NPI globally in-network or collapse multiple offices. |
| Specialty | Preserve code system, code, display and available version. Do not substitute free-text specialty names for validated terminology or claim complete NUCC validation. |
| Unknown and incomplete data | Retain absent/null/unknown distinctions supported by the source. Missing resources, fields or pages create findings; absence from a bounded search does not prove termination. |
| Time | Separate retrieval, source update, effective period, reviewer action and observed verification. FHIR `meta.lastUpdated` is not a human verification date. |

See [Plan-Net resource definitions](https://hl7.org/fhir/us/davinci-pdex-plan-net/STU1.2/artifacts.html) and the [NPPES qualification warning](https://npiregistry.cms.hhs.gov/). FHIR resources must not pass through a clinic-row validator that requires every record to have NPI, phone and address. Valid resource structure, usable comparison evidence and eligible operational data are separate judgments.

Retain full Bundles, `fullUrl`, resource type/id, available version/profile metadata, reference paths and unrecognized extensions. Resolve only declared supported references, preserve unresolved references and avoid invented cross-products among roles and locations. Version-specific parsing and validation produce an inspectable support report. Test profile validation with a pinned validator/package setup and retained diagnostics; document unsupported requirements and terminology-resolution failures. Parsing FHIR-shaped JSON alone does not establish Plan-Net conformance.

Detailed field support, unresolved-reference behavior, profile-specific acceptance and F1–F8 acceptance cases are owned by [the FHIR contract](docs/FHIR_INTAKE_CONTRACT.md). Source-native references and human-reviewed identity links must remain separate.

The first release exports the existing approved dataset and evidence formats. A conformant FHIR server, FHIR writeback and profile-conformant FHIR export are separate deferred work.

## Optional AI assistance
The first task is suggesting column mappings and existing allowlisted normalization operations for clinic CSV/XLSX/flat JSON. Reuse `OnboardingService`, recipe preview and the existing MCP proposal boundary. Deterministic header suggestions and manual mapping must work without a model. Model assistance is not part of the trusted parser or a requirement for ordinary imports.

Use a small invocation interface with one configured model provider or an MCP-connected agent; do not build a plugin marketplace. A web-initiated task must have visible pending, succeeded, failed and unavailable states and return a proposal into the normal review surface. If an external agent supplies the result, show that attribution; do not present it as an in-app model call.

Record provider/model identifier, prompt/schema version, exact bounded input references and sample policy, structured output, validation findings, timing, available usage/cost, and reviewer disposition. Secrets stay outside source/exports. Configure source-specific permission for external processing; default public demonstrations to synthetic data and send only the fields/samples required for the task. Source cells are untrusted data, never instructions. Enforce schema/allowlist validation, time/token/cost bounds, cancellation and failure recovery.

AI cannot approve a recipe, accept a dataset, merge identities, invent missing values, certify participation, submit changes or mark verification. A malformed, stale, ambiguous or adversarial result must fail or remain an unresolved proposal without changing approved data.

Evaluate against current deterministic suggestions on a frozen, held-out set of messy and ambiguous inputs. Report correct mappings, invalid proposals, abstentions, reviewer corrections, latency and actual available usage/cost with model/configuration and denominators. Compare accepted cleaned values with hand-authored expectations. Predeclare an engineering gate of zero invalid operations reaching acceptance and zero incorrect automatic state changes; do not invent a quality improvement threshold after seeing results. If assistance does not improve reviewed mapping outcomes or measured effort, keep it experimental/disabled. Human time savings require observed comparable tasks.

## Web interface and data-management requirements
Source setup, received delivery, interpretation preview, quality findings, reviewed links, dataset approval, investigation and exports must be reachable through the existing navigation with selected source/version context intact. Each screen states the current scope, next useful action and blocked/partial/stale state. A reviewer can trace an exported value to its original resource/row, applied rule and decision without using SQL.

Expose approved versus candidate versions, rejected/quarantined rows, unresolved conflicts, current assignments and history. Keep data editing as reviewed proposals and immutable decisions rather than unrestricted grid overwrites. Preserve draft input after recoverable errors and version conflicts. Use meaningful empty/loading/error states; avoid duplicate legacy and new workflows competing for the same task. CLI, HTTP and MCP paths share service validation.

## Expanded acceptance demonstration
Use synthetic inputs for one clinic, two offices (NORTH/SOUTH) and one payer network. Include differently named workbook columns, leading-zero ZIPs, formatted phones/extensions, a duplicate source key, an ambiguous mapping, a saved Plan-Net Bundle and a second incomplete delivery.

1. Receive, profile and preview the workbook; compare manual/deterministic and optional model suggestions. Reject an intentionally invalid proposal, approve a correct recipe and accept only eligible rows.
2. Parse the saved Bundle and inspect typed resources, explicit role/location/network references, unsupported content and unresolved references. Show a bounded HTTP acquisition against a controlled test server using the same parser; record any public-endpoint smoke separately.
3. Review NORTH identity/location links and a conflicting phone. Leave an ambiguous candidate unresolved. Do not inherit NORTH's phone or participation into SOUTH.
4. Exercise rate limits, a later-page failure, malformed resources, unsafe next/reference URLs and process restart. Show failed/partial attempts and retained evidence without changing the approved consumer version.
5. Receive the incomplete clinic delivery. Hold promotion as required by the configured quality contract; the consumer still reads the previous approved version. SOUTH's omission does not close its case or establish termination.
6. Perform the preserved investigation case, then inspect actual approved-dataset and NORTH handoff downloads for values, scope, source locators, decisions and uncertainties. Reopen storage and reproduce the same pinned output.

## Engineering, evaluation and evidence
Retain Python/FastAPI, React/TypeScript, SQLite and hashed artifacts in one local application. Use small adapter/service boundaries; extract affected parsing or UI components when necessary rather than rewriting the system. Transactions, expected versions, controlled dataset approval, job retry/fencing and read-only SQL remain core. A bad delivery must not erase the last usable dataset.

Every claimed result names its revision, fixture, command and boundaries. Matching candidate retrieval, strict eligibility and human-reviewed links are separate measurements. Synthetic correctness, live endpoint interoperability, model quality and human usefulness have separate receipts. Measure review corrections and unresolved coverage alongside success counts. Test totals alone are not product value.

H1 remains the uncoached investigation walkthrough in [the existing kit](docs/INVESTIGATION_DEMO.md); run it when a participant is available. The expanded journey also needs an observed analyst/participant review before claiming usability or time savings. Evaluation requires a reproducible system, documented tradeoffs, inspected outputs and traceable results, including the documented agent-assisted development process.

## Limits
Single-user local operation; actor names and contacts are assertions. No actual outreach, payer writes, authenticated shared operation, automated identity merge, national ingestion or compliance certification. Provider directory information is not patient eligibility, credentialing or clinical data. Do not ingest patient/claims data as part of this scope. Synthetic tests do not prove customer adoption or real-provider accuracy.

The workflow is intended to be relevant to a healthcare operations team, but team deployment requires a separately scoped authorization, security, audit/retention, operational ownership and concurrency design. Hosting, microservices, a graph database, a distributed queue and a broad plugin system are outside the present scope.
