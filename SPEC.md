# Provider Directory Workbench specification

The product is a local provider-data workbench for importing inconsistent sources, reviewing office discrepancies, and releasing usable datasets without erasing their evidence. The long-term direction includes licensing and provider/network operations. [STATUS](STATUS.md) describes implemented and verified behavior; [ROADMAP](ROADMAP.md) holds future scope. The current owner request and [NEXT](NEXT.md) select work.

## Users and operating boundary

The primary user is a provider-data operator maintaining clinic rosters and comparing them with directory/reference sources. Reviewers inspect evidence and approve changes; integration users consume pinned exports. These are workflow roles, not authenticated accounts. The application is single-user and local.

Use one modular application: Python/FastAPI, React/TypeScript, SQLite and retained artifacts. A new layout usually needs a reviewed mapping, not another parser or service. Supported syntax is not evidence that arbitrary documents or healthcare semantics are understood.

## Implemented workflow

1. Receive CSV/XLSX, a declared JSON profile, or the supported saved/bounded FHIR directory subset. Retain source bytes, scope, native identifiers, delivery and interpretation provenance.
2. Inspect schema and quality findings. Map columns manually, reuse a compatible approved recipe, or review an optional mapping proposal. Parsing, recipe approval and acceptance are separate actions.
3. Review clinician and office links independently. Compare source assertions only in the established scope; keep dates, unknowns and disagreements visible.
4. Select an office-phone assertion with its extension. Explicitly create a complete roster candidate from the current approved feed version, then separately approve it. Candidate creation leaves the prior approved roster available.
5. Preview and download a pinned approved JSON/XLSX handoff with correction and source lineage. Inspect complete quality evidence before deciding a candidate; bounded UI samples do not define export scope.
6. Receive a later delivery, investigate exceptions, and resume after restart. Keep earlier approved versions and decisions readable. An incoming source that conflicts with a local correction requires explicit risk review before separate dataset approval.

## Data and decision invariants

- **Retain evidence.** Preserve original artifacts, receipt/attempt references, native row/resource locators, source scope and interpretation versions. Keep text identifiers, leading-zero ZIPs/extensions and supported absent/null/unknown distinctions.
- **Keep entity meanings distinct.** Clinician, organization, office, license, payer, product and network are different grains. NPI identifies neither an office nor global participation. Similar names or identifiers create review candidates, not automatic merges.
- **Keep decisions distinct.** Parsing, recipe approval, source acceptance, identity linking, field preference, candidate creation, dataset approval, simulated submission and observed verification are separate facts. Local approval does not establish provider truth or update a payer.
- **Pin correction scope.** Materialization requires the current approved base, fresh reviewed links and field decision, and exactly one eligible linked row. Reject stale, conflicting, ambiguous, unlinked and no-op selections. Phone and extension remain one assertion. Other rows and originals stay unchanged.
- **Reject stale writes.** Shared services enforce expected-version/snapshot checks and transactions across HTTP/CLI/MCP entrypoints. Supported identical retries recover the same logical result. Derived correction jobs cannot be reprocessed as source deliveries.
- **Explain quality evidence.** A correction candidate inherits its base's quality report and acknowledgments, explicitly labeled. Later source-to-source comparison remains separate from comparison against approved corrections. Acknowledging a hold is not approval. Missing from a delivery does not prove closure or termination.
- **Separate review from consumption.** Complete candidate quality reports are review evidence, not approved roster exports. Consumable dataset exports require approval. Preview arrays are samples with full counts/tokens; complete downloads retain the selected population. Spreadsheet cells are literal text, with explicit overflow handling.
- **Preserve clocks and scope.** Retrieval, source update/effective time, reviewer action, contact time and independent observation are different. A selected NORTH handoff must not silently acquire SOUTH operational evidence; shared originals are labeled.

## Investigation acceptance case

A clinician has NORTH and SOUTH offices. A later roster changes NORTH and omits SOUTH. Hold/review incomplete coverage while keeping the previous approved version usable. Investigate NORTH, record accountable contact assertions and a correction proposal, then record a simulated submission and separate observation. A mismatching observation reopens the case. Restart and export NORTH; SOUTH and original evidence remain intact. See [the walkthrough](docs/INVESTIGATION_DEMO.md) and [operator flow](docs/OPERATOR_EXPERIENCE.md).

## Source and assistance limits

Network acquisition uses declared sources, destination allowlists and finite request/page/record budgets, with retained failures and replay. A bounded query is not a complete directory; failed acquisition is different from an empty successful response. New transports or sources require their own semantics and access contract.

FHIR support is a documented **R4 4.0.1 / Plan-Net 1.2.0 subset**, not a conformant server or general FHIR engine. Unsupported resources and unresolved relationships remain visible. NPPES license fields are registry assertions, not licensing-board verification. Existing scoped network intake/review does not establish comprehensive network analytics or globally verified participation.

Optional model or external-agent assistance proposes allowlisted declarative recipes. Manual/deterministic mapping remains available. Source cells are data, never instructions. AI cannot execute generated code, approve recipes, accept datasets, merge identities, invent missing facts or mark verification. Recorded external-agent challenges, controlled transports, production-model behavior and human usefulness are different evidence categories.

## Detailed contracts

| Concern | Authoritative detail |
|---|---|
| Ingestion breadth and stable AI-01–10 requirements | [Adaptive ingestion](docs/ADAPTIVE_INGESTION_SPEC.md) |
| Reviewed phone candidates and subsequent delivery drift | [Materialization S1.3](docs/FIELD_MATERIALIZATION_SPEC.md) |
| Approved JSON/XLSX, counts, tokens and correction lineage | [Review workbook format 2](docs/REVIEW_WORKBOOK_CONTRACT.md) |
| Typed source identity and reconciliation | [Reconciliation](docs/RECONCILIATION_CONTRACT.md), [FHIR intake](docs/FHIR_INTAKE_CONTRACT.md) |
| Implemented HTTP and persistence | [API reference](docs/API_REFERENCE.md), [data dictionary](docs/DATA_DICTIONARY.md) |
| UI flow and measured qualification | [Operator experience](docs/OPERATOR_EXPERIENCE.md), [UI protocol](docs/UI_QUALIFICATION.md) |
| Component/service ownership | [Architecture](docs/ARCHITECTURE.md) |

## Deferred product work

Source-specific Tennessee licensing, expanded identity/network analysis, bulk/address corrections, recipient-specific exchange, case research and an independent consumer/deployment design follow named revisions in [ROADMAP](ROADMAP.md). Existing research/exchange designs are proposals. Hosting, authenticated teams, autonomous outreach, payer writeback, patient identity and full claims processing are outside the current implementation. Owner visual acceptance and uncoached-human outcomes cannot be inferred from automated checks.
