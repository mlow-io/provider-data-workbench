# Healthcare Standards & Regulatory Alignment

Provider Data Workbench models real operational workflows shaped by US healthcare directory mandates while explicitly scoping what this local prototype verifies versus what remains external.

## No Surprises Act (NSA) directory accuracy workflows

Under the federal No Surprises Act, health plans must verify provider directory listings at least every **90 days**, process provider-submitted directory updates within **2 business days**, and prevent patients from facing out-of-network balance billing caused by inaccurate in-network listings.

How the workbench models these controls:

- **SLA & freshness visibility:** Work Queue cases surface high-risk patient-facing contact discrepancies (`phone`, `directory_visible`) and follow-up deadlines; the Provider Directory view tracks last-verified dates per clinician-location.
- **Anti-ghost-network quality holds:** A partial clinic roster missing an entire site (such as `FRNK-WEST`) triggers `missing_keys` and `row_count_drift` holds rather than silently deleting active clinic listings.
- **Accountable outreach & verification:** Phone corrections follow an explicit state machine (`new` → `triaged` → `approved` → `pending_verification` → `verified`), keeping local office outreach distinct from observed payer directory confirmation.

## CMS National Directory (NDH), FHIR R4 & Plan-Net 1.2.0

The workbench supports a documented **FHIR R4 (4.0.1) / Da Vinci PDEX Plan-Net (1.2.0) subset** for saved searchset Bundles alongside **CMS NPPES Registry API 2.1** lookups:

- **Supported resources:** `Practitioner`, `Organization`, `Location`, and `PractitionerRole`, preserving resource paths (`$.entry[i].resource`) and network extensions.
- **Conservative graph interpretation:** Unresolved references, unsupported extensions/modifiers (`modifierExtension`, `implicitRules`), and ambiguous multi-location or multi-network `PractitionerRole` bindings are retained as explicit findings rather than guessed.
- **Explicit non-conformance scope:** Built-in parsing checks structure and relationship cardinality; full HL7 FHIR validator / terminology server conformance requires attaching external `OperationOutcome` validation evidence.

## CMS NPI check-digit validation

10-digit National Provider Identifiers are validated against the official CMS ISO 7812 Luhn algorithm (`80840` prefix) via `provider_network_intake.is_valid_npi`. Check-digit validity verifies numeric structure, not live NPPES enumeration, state licensure, or CAQH credentialing.

## HIPAA-safe AI governance

When optional AI mapping assistance (`provider-network-intake` MCP server or OpenAI-compatible / local Ollama endpoint) is enabled:

1. Direct API prompts include **headers, field counts, and curated guide excerpts only** — never row-level values.
2. External agents can inspect deliveries and submit mapping proposals, **but have no review or dataset-approval authority**.
3. Once a human analyst reviews a variant, repeat deliveries execute deterministically in Python with zero model invocations.
