# Synthetic combined-workflow fixtures

All names, identifiers, contacts, addresses and networks here are fictional. `nppes.json` is an offline response shaped like NPPES data; it is not a fetched registry result. These are journey inputs, not matching-accuracy evaluation labels.

`ingestion-platform.spec.ts` is the executable reproduction. It creates invocation-owned catalog targets and source namespaces, then uses the real interface to:

1. Upload `clinic.csv`; preview, propose, approve and apply explicit phone/state/ZIP normalization; accept valid rows separately.
2. Upload `payer.csv`; declare payer-network interpretation and select reviewed CEDAR/PINE, NORTH/SOUTH and CLINIC bindings. Upload `nppes.json` using the NPPES response profile, preserving its mailing and two practice paths.
3. Review clinician and office links individually, then select and retain conflicting field evidence.
4. Propose a NORTH phone change and assess the payer delivery: two affected NORTH listings, one unaffected SOUTH listing and one unlinked row that remains not assessed.
5. Explicitly confirm bounded review work, acknowledge receipt independently, inspect complete JSON/XLSX exports, reload, and demonstrate stale dependency handling.

Only catalog/binding fixture setup uses API writes. Source uploads and every recipe, crosswalk, field, proposal, confirmation and acknowledgement decision use UI controls. Read-only API checks verify exact retained scope and exported evidence. The primary qualification separately owns process restart, migration, corpus measurements and preservation rehearsals.
