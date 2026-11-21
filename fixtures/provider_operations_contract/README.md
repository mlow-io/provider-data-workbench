# Provider operations contract fixtures

Hand-authored synthetic design examples for [contract v1](../../docs/PROVIDER_OPERATIONS_CONTRACT.md). No file contains real provider, payer, patient or client data. The NPI is a fictional example identifier, not a validated or queried provider record. Symbolic storage IDs must be seeded into an isolated test database with computed artifact/export digests before runtime tests; these files do not bypass normal acceptance.

- outbound-manifest.json: one fictional clinician and two distinct office items, pinned to a symbolic approved version/context.
- response-baseline.csv: file received, NORTH item accepted and SOUTH item rejected.
- response-contradictory.csv: a different message accepting SOUTH; this creates disagreement until explicit review.
- response-unknown-item.csv: a nonexistent exchange item that must remain unresolved.
- response-conflicting-duplicate.csv: two incompatible rows for one message/item; retain both and block that item's correlation.
- expected-outcomes.json: independent expected transitions, totals, scope and negative-case mutations.

The CSVs are a proposed application-specific synthetic profile, not an industry payer format. Tests should preserve their bytes, separately exercise equivalent reordered copies, and inspect selected output contents. Passing synthetic cases does not establish live compatibility, provider identity accuracy, billability or human usefulness.
