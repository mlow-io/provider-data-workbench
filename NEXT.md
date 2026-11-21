# Proposed next task: Tennessee licensing-source specification S2

The reviewed correction/export engineering slice and independent external-agent mapping challenge are complete. Read [STATUS](STATUS.md), [S1.3](docs/FIELD_MATERIALIZATION_SPEC.md), [its receipt](docs/evidence/canonical/correction-export-2026-11-21/README.md) and [the mapping evaluation](docs/AI_MAPPING_EVALUATION.md) before changing behavior. The actual-model client and uncoached-human evidence remain open; saved proposal replay is not a fresh inference trial. Preserve private drafts and the public repository's clean ancestry.

## Proposed planning scope, awaiting owner selection

Freeze S2 before implementing licensing/expanded identity features. Produce a small source/contract/design packet:

1. Name a Tennessee licensing source and inspect its actual supported access method, terms, scope, freshness and stable identifiers. Distinguish a licensing-board assertion from an NPPES registry entry. Record absent access or absent samples as a prerequisite, never synthetic success.
2. Define credential grain: clinician versus organization, issuing jurisdiction/board, license number, status, relevant dates and retained source locator. License status is distinct from office contact accuracy and network participation. NPI alone cannot choose an office or establish a credential match.
3. Define conservative matching candidates, separate review decisions, stale/conflict/unknown handling and an explainable two-provider synthetic flow. Preserve originals and earlier decisions; no automatic identity merges, provider removal or contact overwrites.
4. Reuse existing intake/profile, comparison, reviewed-link and decision/export services. Identify the smallest additions and their exact API/schema/migration effects. Avoid another canonical store, arbitrary scraping runtime or generic connector platform.
5. Add acceptance IDs, independent expected fixtures, UI flow and required checks, plus a privacy-safe source-evidence policy. Return a reviewable S2 spec and next implementation brief; planning alone does not authorize new production adapters, migrations, scraping/model calls or hosting.

S3 provider/payer/product/network relationships remain a later named revision. Bulk/address corrections, recipient templates and case research remain in ROADMAP. Owner visual feedback and participant walkthroughs retain separate gates; an engineering receipt does not close them. Use bounded Terra workers under AGENTS only when an explicitly selected task benefits from disjoint work.
