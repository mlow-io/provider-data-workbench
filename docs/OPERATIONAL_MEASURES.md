# Operational bottlenecks and reconciliation measures

Scheduling note, 2026-11-21: this remains a planned measure contract. [ROADMAP](../ROADMAP.md) places ingestion/contact work first; new reporting belongs to the later operational question that needs it. [NEXT](../NEXT.md) controls execution. No reporting dashboard is required by P0/S1.

Proposed read-only reporting contract, 2026-11-19. These measures are not implemented by this document. It supports [operator experience](OPERATOR_EXPERIENCE.md) and [provider research/exchange](PROVIDER_RESEARCH_EXCHANGE.md); it does not integrate or replace the separate KPI project.

## Decisions supported

Help an operator find the next blocked item, identify recurring source/recipient problems and explain workload. Every reported value must drill through to its exact population and evidence snapshot. Rejection reasons, matching uncertainty, quality holds and pending recipient responses are different problems and remain separate categories.

## Measure definitions

| Measure | Grain and definition | Important limits |
|---|---|---|
| Open actionable work | Distinct cases in a declared status set as of a snapshot | Show deferred/closed separately; source rows are not cases. |
| Delivery quality holds | Distinct candidate versions by hard blocker/soft hold/reason | Several reasons can affect one version. Reason counts can overlap and must not be summed into a total. |
| Recipient row rejections | Distinct exchange items with a selected current rejected disposition, by recipient/reason | Retain contradictory responses. Unresolved correlation and unknown disposition have separate counts; file receipt alone cannot determine row acceptance. |
| Row rejection rate | Rejected items / items with an established selected row disposition in the selected response population | Also show response/correlation coverage, raw numerator/denominator and accepted/pending/unknown counts. Never silently exclude unknowns from the reader's view. |
| Awaiting recipient acknowledgment | Prepared exchange items with an explicit locally asserted sent event and no established selected row response | Prepared-only items are separate. Missing response is not a rejection or proof that a recipient received the file. |
| Waiting age | Elapsed time from a defined event to as-of time for a declared pending population | Event basis must be visible; local asserted send time differs from server-recorded time. Unknown start/timezone means unavailable, not zero. |
| Follow-up due | Distinct eligible open cases whose explicit due time is before the as-of time | No invented SLA. Show unset/unknown due times separately. |
| Reconciliation outcomes | Counts by clinician/office/field comparison status within one pinned source pair | No pooling incompatible source/network scopes. Not-assessed/unavailable is separate from equal or different. |
| Observed correction outcomes | Selected investigations with separately recorded matching/mismatching downstream observation | Submission or recipient acceptance is not observed correction. Local asserted observation remains labeled. |
| Repeated issues | Distinct cases or exchange items with a defined recurring reason within the selected history | State whether counting repeat events, repeated affected rows or unique providers; do not deduplicate all offices by NPI. |
| Research workload | Terminal run state, validated finding/abstention counts, measured latency and available usage/cost | Not a measure of provider truth or human time saved. Failed/partial/unavailable runs stay in the denominator chosen by the report. |

The above definitions are starting contracts. Freeze exact status sets, selection rules, schema and independent expected values before adding an endpoint. A disputed response must not be chosen simply because it has the latest import timestamp. Any reviewer-selected working disposition keeps its source/version and contradiction history.

## Time, scope and SQL

Each response/export declares as-of time, source snapshot/release, relevant attempt/profile/rule revisions, recipient/network filters, included statuses, reason mapping version and count unit. Store original source/effective/actor times separately from server event time. Historical waiting states require actual events; do not reconstruct unsupported transitions from the current row alone. Elapsed waiting time and candidate-computation latency do not establish active staff effort or root cause. Closed-case-only averages cannot describe the age of the open backlog. Physical uploads, logical deliveries, interpretation attempts, source rows and candidate pairs also remain separate units.

Aggregate at the intended grain before joining one-to-many observations, reasons or events. Pin all component queries to one read transaction. Pagination controls displayed records, not total-count denominators. Drill-through retrieves every matching item or explicitly marks a bounded sample. Stale evidence, missing fields and partial source coverage remain visible.

Use the existing SQLite/read-only SQL pattern and versioned report definitions. Add indexes when query plans and measured fixture workloads warrant them. Do not add a reporting warehouse, second event store, predictive model or materialized aggregate table without a demonstrated need.

## Interface and exports

Start with a reason/blocked-state table, waiting-age distribution and actionable list. Each aggregate opens the corresponding filtered records with scope retained. Offer readable CSV/JSON with definitions and source identifiers. Cosmetic KPI cards and unsupported rankings are not acceptance evidence. Avoid inferring rejection causes from correlation; a supplied reason is a source assertion, while an analyst diagnosis is separately attributed.

## Acceptance

- OP1: Exact totals agree across SQL, UI, drill-through and exported population on independently authored fixtures.
- OP2: Repeated ingestion, reordered rows, multiple reasons, several offices, repeated responses and multiple source observations do not inflate counts.
- OP3: Contradictory/uncorrelated/no-response/partial-source cases remain visible and cannot become accepted or rejected by default.
- OP4: Timezone, missing-time, deferred/reopened and as-of cases behave according to the declared clock; unavailable values remain unavailable.
- OP5: Reporting is read-only and does not change assignment, approval, identity, submission or verification state.

Begin with hold/reconciliation/follow-up measures supported by existing data. Add external rejection/acknowledgment measures when the exchange slice provides the required evidence; omit unavailable measures rather than filling them with invented values.
