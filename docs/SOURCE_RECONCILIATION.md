# Source reconciliation

The canonical candidate descends solely from the public core. Current application changes were reviewed as file content; private Git ancestry, conversations, internal prompts and runtime records are retained separately. Existing public branches remain available; no branch deletion is required.

| Public source | Revision | Identical application paths | Updated paths | Branch-only paths |
|---|---|---:|---:|---:|
| main | 572f891 | 46 | 19 | 0 |
| feat/publish-operational-sql | 936a9b0 | 48 | 23 | 0 |
| feat/recurring-imports | 4d138b0 | 52 | 26 | 0 |
| feat/network-storage | 88bc851 | 57 | 27 | 0 |
| feat/network-review | 20a7e2b | 65 | 26 | 0 |
| feat/guided-network-demo | f0c592c | 71 | 24 | 0 |

The integrated source supersedes the overlapping operational SQL and network snapshots. Updated paths were reconciled against the current implementation and tests; any branch-only application paths must be resolved before cutover. Historical public documentation is retained in docs/archive/public-baseline; private milestone receipts and images remain in the private archive. New canonical qualification is independent of historical totals.
