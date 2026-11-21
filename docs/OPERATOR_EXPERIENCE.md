# Operator experience and product cleanup

Updated direction, 2026-11-21: [S1](ADAPTIVE_INGESTION_SPEC.md) and P0–P4 supersede the former exchange-first UI sequence. Sources, import breadth, reviewed mapping and quality are central to the next release. The following historical observations remain useful; they do not establish a completed new design. P0 must produce a populated proposal for owner review before production UI implementation.

Historical selected contract, 2026-11-19. This defines the UI and clarity work accompanying the [research/exchange extension](PROVIDER_RESEARCH_EXCHANGE.md). The observations below describe the pre-UI1 React baseline. Interactive browser access was unavailable during initial planning; invocation-owned local Chromium captures were subsequently used for UI1. [STATUS](../STATUS.md) records implemented changes and checks; automated captures do not establish human usability.

## Product job

Help an analyst receive provider data, link the correct clinician and office, reconcile conflicting assertions, follow up on rejected or unresolved changes, and hand off a usable result. Column mapping, entity matching and field reconciliation are distinct operations. A proposed clinician link is not an office link or verified participation.

The interface must answer: What am I reviewing? Which provider/office/source/version does it concern? What is blocking progress? What evidence supports the decision? What useful action can I take next?

## Pre-UI1 source observations

| Source | Observation | Requirement |
|---|---|---|
| App.tsx | Primary navigation includes Intake, Managed feeds, Reconcile, Work queue, Sources, Legacy QA and Corrections; absent view defaults to feeds | Establish one operator navigation model and entry task; place compatibility workflows under secondary tools without removing stored history or deep-link access. |
| App.tsx | Legacy overview uses a slogan as its main heading; its API-failure screen tells users to run make demo | Use task/context headings and actionable service/storage errors. Error recovery must not suggest reseeding an unknown runtime. |
| App.tsx | A batch row count is labeled records reviewed, while open items use the filtered loaded population | Label batch records, returned/filtered cases and human decisions separately; do not imply measured human review. |
| ManagedFeeds.tsx | Numbered implementation-oriented sections include Pinned configuration, Durable processing and Consumer boundary; configuration and delivery review share a long component | Separate source setup from daily delivery decisions. Put current approval/hold and next action first. Preserve full technical detail through labeled disclosure. |
| NativeEvidencePanel.tsx | Native resources, office assertions and interpretation history include raw JSON views; important scope notices already exist | Provide readable assertion/evidence rows before raw payloads. Preserve unresolved relationships and meaningful limitations at the relevant action. |
| workspaceNavigation.ts | Existing URL state and action guards protect context across navigation | Reuse these mechanisms; preserve selected source/version/case and prevent late responses from redirecting a different workspace. |

These observations identify requirements, not measured user confusion or screenshot-based accessibility results.

## Proposed information architecture

| Area | Main question | S1 experience |
|---|---|---|
| Sources and imports | What arrived and which known meaning applies? | Delivery list, source scope, prior approved version, file/worksheet inspection and explicit unknown-profile state |
| Mapping and quality | How will this file become usable data? | Original/cleaned preview, selected profile/recipe, findings, manual mapping, optional proposal and separate approvals |
| Providers and relationships | Which clinician and office do these records describe? | Existing reviewed links, multiple offices and unresolved associations; richer licensing/network views later |
| Discrepancies | What changed and what should be done? | Filterable table, stable selected-case panel, compared values/dates, reasons and proposed actions |
| Export review | What will a colleague receive? | Approved snapshot, selected scope, unresolved issues, evidence references and inspected workbook/download |

These are task destinations, not a requirement for five top-level pages. P0 chooses navigation around the populated journey; mapping can be a step within an import and export a contextual destination. Preserve existing deep links and approved-version access. Advanced source configuration stays secondary within the source task, while imports and mapping remain first-class work.

Exchanges, network analysis and case research enter navigation only when implemented in their scheduled milestones. Research stays attached to a selected question/case. Keep compatibility/history access without two competing primary workflows.

## Workbench migration priority

The prior release delivered incremental CSS/component improvements; shadcn/Tailwind adoption remains unimplemented. The [UI migration plan](UI_WORKBENCH_MIGRATION.md) now owns UI-W0–W5, the official sidebar-block proposal, table/inspector layout, dependency/CSS strategy and WM acceptance. Prototype a populated workbench before installing production dependencies. This explicitly supersedes the earlier decision to defer component-system migration indefinitely.

## P0 visual design packet

Retain React/TypeScript/Vite and existing TanStack Query/Table. shadcn/ui is the recommended component-system candidate, not an installed or approved migration. Verify compatibility, dependency impact and component ownership; record the decision. Use one coherent system for controls and tokens; retire conflicting CSS as touched screens migrate instead of indefinitely stacking overrides. Keep domain behavior independent of library choice.

Prepare populated desktop and narrow-width proposals for: import inspection; mapping/cleaning preview with an ambiguous field; two-office discrepancy comparison; and export review with unresolved work. Include loading, no results, failed/partial source, schema drift, stale decision and unavailable-assistance states. Use concrete synthetic content and one clear next action. A prepared example must be discoverable and labeled.

The proposed style is a restrained professional operations application: compact navigation, readable data tables, consistent spacing/type scale, limited semantic colors, a stable evidence panel and direct actions. Avoid giant filter forms dominating results, long instructional cards, decorative dashboards and raw JSON as the primary explanation. Owner review evaluates the populated task, not only an attractive empty shell.

P1 implements the reviewed proposal over existing services. P2–P4 extend that same design as their capabilities land. UX1–5 and AI-09 require running screenshots, keyboard/focus and responsive evidence; owner visual acceptance and uncoached usability observations are separate gates.

## Screen and interaction requirements

- Use a persistent context header with clinician, office, source, relevant version and concise state. Display a useful next action or a precise blocker. Source setup must not dominate routine review.
- Use a readable data table and a stable evidence/detail panel. Show changed values side by side with source/date and uncertainty; provide direct original-row/resource access. Keep identifiers copyable but subordinate to human-readable labels.
- Use a consistent type scale, spacing, surface hierarchy, table density, buttons, filters and status treatment across all workspaces. Avoid decorative hero sections, unsupported KPI cards, excessive pill badges and repeated slogans. Color supports labeled meaning, not decoration alone.
- Put routine decisions in a clear action area. Explain what a decision changes and what it does not establish. Reviewer attribution remains a local assertion unless authentication is separately implemented. Retain required reasons without repeatedly requesting irrelevant configuration.
- Distinguish loading, empty, no matching results, partial data, failed acquisition, held delivery, stale evidence and unavailable assistance. A failed fetch is not an empty directory. Historical stale results stay inspectable.
- Preserve keyboard navigation, visible focus, semantic table headers and labels. Screen-reader announcements must not reread an entire evidence panel on every edit. Verify contrast and focus behavior in the running UI; screenshots alone are insufficient.
- Validate at desktop and narrow widths using synthetic owned storage. Detail panels must stack or use an explicit selection view at narrow widths; actions cannot be clipped or hidden behind horizontal page overflow. Target at least 44 CSS px for primary touch interactions without inflating every desktop table row.
- Never remove an approval/version/evidence boundary to make the interface shorter. Move diagnostic JSON, hashes, parser versions and internal IDs behind descriptive controls while retaining easy access for investigation.

## Language and capability integrity

Use labels tied to exact behavior: map columns, review identity link, hold delivery, approve dataset, prepare correction, record supplied response. Distinguish file received, row accepted and directory observed. Avoid unqualified "verified provider", "source of truth", "production-grade", "AI-powered" or "compliant" labels unless a precisely scoped claim is supported and necessary.

Keep source reason codes and interpreted labels separate. Preserve unknown/null/absent semantics; a prettier display must not turn unknown into no. Mark synthetic examples once in persistent context and repeat only when an action could otherwise be mistaken for real outreach or submission. Empty states should explain the next useful action, not sell the product.

## Code and documentation cleanup

Extract shared status presentation, source/version context, async states, evidence display and action patterns when the affected journeys require them. Keep data rules in shared services. Refactor large components along task boundaries while preserving query guards, draft state and tests. Avoid a simultaneous service rewrite or a generic UI abstraction framework.

Remove stale capability statements from current docs. Keep historical receipts dated. API reference and data dictionary describe implemented contracts; proposed contracts stay labeled here. Preserve reproducible exports rather than hand-curated demo-only values.

## Gates and delivery

| ID | Acceptance |
|---|---|
| UX1 | Initial task, current scope, blocker and next action are clear on each touched screen; legacy routes/data remain accessible. |
| UX2 | A complete two-office journey retains selected context and unsaved inputs; stale actions fail without partial changes or confusing success. |
| UX3 | Copy/status labels map to explicit source and decision states; no unsupported compliance, accuracy, participation or savings claims. |
| UX4 | Captured running screens, keyboard/focus checks and desktop/narrow-width evidence support the chosen design; record unresolved limits. |
| UX5 | An analyst can reach the original evidence and export selected work; visible summaries agree with actual serialized outputs. |

Use P0 to specify the populated ingestion-to-export journey and P1 to implement its approved first slice. Apply its components and interaction rules to provider records, investigation, exchanges and sources as those slices are touched. Build operations reporting from its [separate measure contract](OPERATIONAL_MEASURES.md). Human observation remains distinct from automated browser checks.

## Qualified review and export flow

The [100/1,000-record qualification](UI_QUALIFICATION.md) records the current populated review/handoff journey and its measured bounds. Source and delivery context stay visible; complete population counts precede samples. The workbook preview displays at most five rows per section and explicitly states that the download includes the complete selected approved population. Its token comes from the full consistent snapshot; stale work requires refreshing the preview. Candidate state and dataset approval remain separate.

On narrow screens the operator returns to the delivery list, activates a version with Enter and receives inspector focus. Wide preview tables have an explicit sideways-scroll hint, and their focusable frames support Arrow Right. Returning to the list preserves any focus move the operator already made. Coarse-pointer controls have a 44 px minimum; the primary export action has checked normal/hover contrast. Inspect actual [narrow export](evidence/canonical/ui-qualification-2026-11-21/export-1000-narrow.png) and [desktop delivery](evidence/canonical/ui-qualification-2026-11-21/delivery-1000-desktop.png) captures. Owner feedback and uncoached observation remain separate from these automated checks.

## Reviewed correction to handoff

In Reconciliation, establish the clinician and office links, inspect the exact source phone assertion, and explicitly select it with a reason. In the current approved delivery, open **Inspect reviewed phone decisions**, choose the office and compare current/reviewed numbers and extensions, source and review reason. Enter decision attribution and choose **Create roster candidate**. The previous approved directory remains consumable. The new detail is labeled as a derived candidate; inherited quality findings are labeled and source reprocessing is unavailable.

Review the candidate, then choose **Approve dataset version** separately. A stale source/link/field/base requires inspection and a new candidate. An uncertain create result offers an exact retry rather than a fresh request. Open the approved workbook preview; complete counts precede independent samples, with correction and source references visible. Download complete JSON or XLSX using that preview's token. The correction ledger shows old/new numbers and extensions and local decision attribution. A prior approved export remains available. On narrow screens retain the existing list/detail Back control and keyboard scrolling of wide evidence tables. Automated browser rehearsal is not a substitute for an uncoached user trial.

## Subsequent source delivery

A later file keeps its source-to-source comparison against retained observations. Separately, `report.effective_corrections` compares incoming phone/extension assertions to previously corrected rows in the pinned approved version using exact native record/office keys. Changed, missing, invalid or ambiguous incoming assertions raise the `effective_correction_drift` soft hold. An operator must acknowledge the risk before approving the new source version; a source repeating the old phone cannot silently appear safe merely because its source comparison is unchanged. Missing still does not mean termination. No old observation or local decision is rewritten, and approval of a later source does not claim a payer update. Bounded UI samples keep full totals; the complete approved-dataset JSON retains the whole report.

During selected-version loading, show progress without an editable attribution placeholder. Reviewer/reason controls become available with the actual selected evidence, preventing input into a form that will be replaced by the arriving version.
