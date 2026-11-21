# Working agreement
Read SPEC.md, ROADMAP.md, STATUS.md, and NEXT.md before editing. Follow the active brief and its acceptance cases. Read supporting API/data/decision documents only as needed.

For D1–D4, use docs/ARCHITECTURE.md and docs/SPEC_DRIVEN_DELIVERY.md to identify affected boundaries and acceptance IDs. Keep one active slice in NEXT. Resolve durable-data contract changes before dependent code, integrate producer and consumer within the slice, and update implemented API/data references with code. Planned contracts and intended checks are not implementation or verification receipts.

Preserve original artifacts, retained observations and append-only history. Keep clinician, location and network identities distinct. Record acceptance, proposal, submission and observed verification as separate decisions. Use expected-version checks and transactions for case changes.

Use synthetic committed fixtures and invocation-owned runtime/test directories. Never reseed or clean a user's database. Back up a stopped database together with its artifacts before migration experiments. Keep private preparation and real records outside Git.

For Python changes run pytest -q; pipeline changes also require make validate. Frontend changes require npm test --prefix web and npm run build --prefix web; review-console or responsive changes require npm run test:e2e --prefix web. Preserve failures and reruns separately. Inspect real export contents, not just status codes.

Update SPEC for changed contracts, ROADMAP for milestone gates, STATUS for verified outcomes, and NEXT for the single active brief. Do not restate current status in historical documents. Keep decisions in docs/DECISIONS.md. Explain engineering choices in chat; keep repository documentation professional.

Develop from public ancestry in this repository. Use verified GitHub noreply metadata for outgoing commits. Never merge private preparation history or commit databases, local paths, credentials or nonsynthetic records. Use focused commits and inspect staged content and metadata before publication.
