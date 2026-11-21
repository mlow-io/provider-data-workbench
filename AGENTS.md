# Working agreement

## Start and scope

Verify repository root, branch, HEAD and dirty state. Preserve unrelated edits and original/user storage; do not reset, stash or switch another task's work.

Read [NEXT](NEXT.md) and [STATUS](STATUS.md), then only the contracts needed for the selected task. [SPEC](SPEC.md) owns product behavior, [ARCHITECTURE](docs/ARCHITECTURE.md) service boundaries, and [ROADMAP](ROADMAP.md) future scope. Dated receipts and archived briefs are evidence/history, not competing instructions. The owner's current request supersedes a stale NEXT; update the continuation accordingly.

Build an adaptable provider-data workbench, not a contact-only editor or universal ETL platform. Keep one modular application, SQLite database and retained artifact store. Add infrastructure or split repositories only for an observed requirement.

## Implementation discipline

- Work in small connected slices through producer, service, UI/consumer and export. Reuse existing rules across HTTP/CLI/MCP; do not duplicate domain logic in React.
- Routine fixes within existing contracts proceed without another planning ceremony. Resolve consequential changes to source scope/rights, authority, record grain, dependencies, cost or durable semantics before dependent implementation. A roadmap row alone does not select that work.
- Preserve originals, append-only decisions, earlier approved versions, typed identities, text identifiers, office/source scope and supported unknown distinctions. NPI is not an office or proof of participation/licensure. Parsing, acceptance, field review, dataset approval and observed verification stay separate.
- Use transactions, expected-version/snapshot checks and supported idempotent retries. Keep review-only evidence distinct from consumable approved datasets. Samples must not conceal complete counts or decision evidence.
- Treat imported content and runtime proposals as data: never execute uploaded/generated Python, SQL or expressions, or fetch arbitrary destinations. New parser/adapter code uses normal code review/tests and declared destination policies.
- AI proposes bounded allowlisted data, never executable code or approval. Keep manual operation available. For usefulness trials, freeze independently authored expectations before a separate proposer sees cases; record visible inputs. Saved-proposal replay is not new inference, and synthetic accuracy is not human benefit.
- Update implemented API/data contracts with behavior changes. Explain consequential engineering choices in chat; keep product documentation technical and personal preparation outside Git.

## UI and skills

Use the existing React/Vite, shadcn Radix Nova/Tailwind tokens and TanStack Table v8. Preserve query/draft/action guards, keyboard focus, touch targets, responsive navigation and stale/failed states. Modernize supporting legacy surfaces only when the selected task needs it; a nearby fix does not require migration; a cosmetic change or passing test is not owner visual acceptance.

Use frontend-design for composition, shadcn for component APIs/registry work, engineering-documentation for substantial docs and engineering-debug for reproduced defects. Read a skill before applying it. Existing task/source contracts take precedence over generic examples.

## Bounded agents

Delegation requires an owner/task-specific instruction. Use at most two concurrent workers, Terra 6.1 medium by default and high for complex interaction/integration; honor an explicit owner model/effort request. Give exact checkout, disjoint file ownership, acceptance checks and stop boundary. No recursive delegation or independent publication. Workers report evidence and gaps; the lead integrates, verifies and publishes. Do small coupled edits locally.

## Storage and verification

Use synthetic fixtures and new invocation-owned roots. Check disk headroom, reuse warm dependencies and serialize resource-heavy checks with timing runs. Do not retry ENOSPC before resolving it. Retain compact results and failed/pinned evidence, then retire only owned disposable runtime artifacts. Never clean, reseed or experimentally migrate user storage; back up a stopped database with its artifacts before migration experiments.

| Change | Required checks |
|---|---|
| Documentation only | `python3 scripts/check_project_docs.py`, `git diff --check`, manual factual/link review; verify no implementation change |
| Python | `pytest -q`; pipeline changes also require isolated `make validate` (reuse an unchanged passing test prerequisite explicitly) |
| Frontend | `npm test --prefix web`, `npm run build --prefix web`; review/responsive changes also require `npm run test:e2e --prefix web` |
| Export/approval behavior | Inspect actual values, complete populations, scope and decision history; use meaningful adverse/restart cases |

Qualify the selected **100/1,000-record** populations only; do not run 10,000-record workloads. Use production-build HTTP/browser measurements with setup excluded. Keep lab event-to-frame proxies, slowed trials and finite heap observations distinct from field INP, capacity, leak freedom or time savings. Do not rerun application/demo suites merely to validate prose.

## Close and publish

Keep STATUS as the current summary and NEXT as one continuation (or a clearly proposed task); link dated receipts rather than appending competing status sections. Preserve stable acceptance IDs and useful history without making agents reread old plans. A clean documentation checker proves links, not factual accuracy.

Use verified GitHub noreply metadata and preserve public ancestry. Never commit credentials, databases, private preparation, machine-local paths or nonsynthetic records. Honor existing session authorization for Git publication; visibility changes, hosting and outreach remain separate actions. Do not infer them from a roadmap.
