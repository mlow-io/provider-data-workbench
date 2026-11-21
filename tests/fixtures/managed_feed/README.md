# Synthetic managed-feed fixtures

All names, identifiers, addresses and phone values here are synthetic test data. Ten-digit NPIs satisfy the existing structural validator only; no registry lookup or provider-truth claim is made.

`expected.json` freezes independently authored counts against `baseline.csv` before managed-feed implementation. Each later file compares with that baseline independently, not with the previous file in directory order. Baseline itself has no earlier version. Identity is `(record_id, location_id)`: `SYNTHETIC-001` intentionally reports the same clinician at NORTH and SOUTH.

| Fixture | Raw | Valid | Quarantined | New | Changed | Missing |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline.csv | 3 | 3 | 0 | 3 | 0 | 0 |
| clean_update.csv | 3 | 3 | 0 | 0 | 1 | 0 |
| row_drop.csv | 1 | 1 | 0 | 0 | 0 | 2 |
| invalid_phone.csv | 3 | 2 | 1 | 0 | 0 | 0 |
| duplicate_key.csv | 4 | 2 | 2 | 0 | 0 | 0 |
| header_drift.csv | 3 | Not assessed | Not assessed | Not assessed | Not assessed | Not assessed |
| empty.csv | 0 | 0 | 0 | 0 | 0 | 3 |
| reordered_repeat.csv | 3 | 3 | 0 | 0 | 0 | 0 |

Header drift is a structural contract failure before row interpretation, so later counts are `null`, not invented zeroes. Empty snapshot counts describe the evidence if comparison is performed; the empty full snapshot still blocks approval. Both conflicting duplicate copies are quarantined, while the key remains present and does not become a missing baseline key. A bad phone with a known key is blocked-invalid rather than changed. A row drop opens both the greater-than-20% raw-count drift hold and the missing-prior-key hold; missing is absence evidence only, never termination.

Fixture expectation labels such as `row_count_drift` are semantic labels for the planned managed-feed policy, not assertions that those API codes already exist. Files contain no deliveries/manifests tied to machine-local paths or wall-clock dates. Tests should create source-issued delivery IDs, periods and SHA-256 manifests in owned temporary inboxes; identical bytes in another period and an older period can reuse these files to exercise repeat and out-of-order behavior without changing their frozen row expectations.
