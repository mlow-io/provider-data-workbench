# Provider-data operations case study

## Problem and useful outcome
A provider-data analyst receives inconsistent clinic rosters and payer-directory evidence. Cleaning a phone column is insufficient: the analyst must know which office it belongs to, why a new delivery is incomplete, which version a downstream user received, and what evidence supports a correction. Missing SOUTH from a later roster must not silently terminate it.

Provider Directory Workbench connects intake, reviewed cleaning, quality holds, source comparison, an approved-data consumer and a scoped investigation in one local web application. It targets a bounded provider-data operations task rather than a universal data platform.

## Implementation and decisions
Python/FastAPI retains exact source bytes and versioned interpretations in SQLite plus hashed artifacts. React exposes acceptance, cleaning recipes, managed versions, separate clinician/location review and correction decisions. CSV/XLSX and explicit JSON profiles share intake services; a narrow FHIR R4/Plan-Net parser retains typed resources, unresolved/unsupported findings and field locators. Bounded network capture preserves original pages separately from its assembled interpretation and retains source-wide cooldown across cancellation and terminal failures.

The approved-data reader independently validates a named export's approval, digests, quality findings, native keys and contact representation without opening the application database. A bad candidate cannot replace the approved version. Evidence comparisons remain separate from source assertions and human-reviewed identities. Transactions and expected versions reject stale decisions without partial history.

Optional model mapping creates proposals into the existing recipe-review boundary. Manual/deterministic operation works without it. Source permission, bounded samples, strict operations and retained invocation history limit what the assistant can do; it cannot approve data or invent provider facts. Actual model benefit remains unmeasured.

## Reproducible demonstration and evidence
Run [the synthetic operations rehearsal](OPERATIONS_DEMO.md#run-and-inspect). It accepts one eligible workbook row while retaining two duplicate-key quarantines, reuses a reviewed recipe for a clean two-office CSV, and ingests saved and two-page controlled-HTTP FHIR. NORTH's conflicting payer phone retains its original-page locators; SOUTH remains distinct. A later incomplete CSV is held, and the independent consumer retains the approved NORTH/SOUTH values, ZIP 02108 and extensions.

The NORTH investigation records no answer, an office response, explicit correction approval, simulated submission and a separate observed mismatch that reopens the case. Selected JSON/XLSX exports retain source context, decisions and uncertainty. Restart and stopped backup/restore preserve the consumer and scoped payloads. [The combined receipt](evidence/canonical/operations-2026-11-14/README.md) records actual outputs, required checks, failures and acceptance coverage. [The original investigation walkthrough](INVESTIGATION_DEMO.md) remains available.

Existing matching fixtures have partial labels: unlabeled pairs are unassessed and overall precision is undefined. Generated exhaustive labels support synthetic precision only. Candidate retrieval/eligibility remains distinct from a reviewed identity link. Frozen mapping evaluation records deterministic disagreements and unavailable model runs rather than inventing results.

A later [live HAP qualification](evidence/canonical/fhir-live-boundary-2026-11-14/README.md) completed one native-ID-filtered Location import and separate reference acceptance, and verified two gateway-routed pages before cancelling the partial query. This exposed and corrected the difference between network routing and source identity, and between page size and a bounded target. Actual payloads remain outside Git. Separately, [pinned online terminology controls](evidence/canonical/fhir-terminology-2026-11-14/README.md) accepted the standalone Location without warnings and retained distinct state-warning/status-error controls. These results establish their observed scopes, not source-wide conformance.

The [filtered-response follow-up](evidence/canonical/filtered-response-2026-11-14/README.md) also rejects a server ignoring the requested ID despite HTTP 200. Matching resources, included context and source warnings stay distinct; an incomplete or erroneous capture has no acceptance path and cannot change the approved consumer. Saved pages are rechecked before publication after restart.

The [R2 graph qualification](evidence/canonical/provider-graph-2026-11-14/README.md) adds a whole synthetic Plan-Net 1.2 graph with zero external-validator errors/warnings, independent NORTH/SOUTH expectations and inspected JSON/XLSX provenance. A bounded actual role capture exposed three Network references beyond the declared projection cardinality and one unsupported HealthcareService reference. The workbench retains that evidence and explains the limit rather than selecting a network arbitrarily. Synthetic validation and useful actual-source projection remain separate claims.

[Portable distribution qualification](evidence/canonical/portable-distribution-2026-11-14/README.md) runs the real consumer, held delivery, no-model evaluation, SQL and backup/recovery from wheel and sdist installs outside the checkout. Packaged immutable assets remove source-tree dependencies; a drift check keeps their authoritative fixtures and queries aligned.

## Development and limits
This personal learning project uses agent-assisted implementation with human direction and review. The repository exposes design decisions, source, tests and reproducible evidence. Production matching accuracy and customer benefit remain unmeasured.

The supported deployment is single-user and local. Contacts, submissions and observations are local assertions; no actual outreach or payer update occurs. Controlled HTTP and browser evidence do not establish live payer interoperability, full Plan-Net/terminology conformance or human usability. Actual-model evaluation and uncoached H1/H2 tasks remain open. Hosting, shared authentication, payer writeback and additional transports need separate scope decisions.
