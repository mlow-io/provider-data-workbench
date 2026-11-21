# Workbench UI migration plan

Proposed design contract, 2026-11-21. The prior adaptive release improved the existing React/CSS screens; it did not install a component library or complete the workbench redesign. This plan makes that migration a distinct deliverable. [STATUS](../STATUS.md) owns implementation evidence; [NEXT](../NEXT.md) selects the next task. This revision changes planning only.

## Outcome and proposed stack

A provider-data operator works in one application shell: navigation, contextual toolbar, compact source/record list, selected-record inspector and explicit action area. Import inspection, mapping/quality, discrepancy review and export share the same interaction model. Source/version/office context remains visible while original evidence and configuration are progressively disclosed.

Recommended implementation: existing React/TypeScript/Vite; **shadcn/ui + Tailwind CSS**; existing TanStack Query and Table. Start from an **official @shadcn sidebar block**, with sidebar-07 as the candidate, and compose the domain-specific workbench body. Record the selected block, primitive base, icon library and exact package versions at UI-W0. Template example accounts, teams, sample projects and placeholder cards must be removed or replaced by functioning product controls. No new authentication or backend framework is implied.

A component library supplies reusable behavior and visual primitives. An application-shell block supplies navigation/layout structure. The workbench's table/inspector/decision flow still needs product design. Do not claim migration complete by adding a sidebar around legacy long-form screens.

Official references: [Vite installation](https://ui.shadcn.com/docs/installation/vite), [sidebar blocks](https://ui.shadcn.com/blocks/sidebar), [table composition](https://ui.shadcn.com/docs/components/data-table). These are starting references, not pinned implementation inputs. Inspect current CLI output before generating components and retain generated source for review.

## Current baseline and concrete gaps

- React 19/Vite 6, TanStack Query 5 and Table 8 are installed. No components.json, Tailwind or shadcn dependency/configuration exists.
- WorkbenchShell.tsx, EvidenceComparison.tsx and ApprovedExportReview.tsx contain reusable behavior, but the visual primitives remain custom.
- Ten CSS files independently style shell, intake, normalization, managed feeds, evidence, reconciliation and network screens. Broad shell overrides already caused a primary-button hover contrast defect during the last release.
- Delivery sections still contain substantial explanatory content and configuration/history within the main decision flow. A workbench needs stable selection and a dedicated inspector/action area.
- Preserve workspaceNavigation deep links, query guards, dirty drafts, source/attempt/version pins, explicit approvals, unknown/null/absent semantics and actual download integrity.

## Representative layout and behavior

```text
+------------------+----------------------------------------------------------+
| Product          | Breadcrumb / source / version      Search    Actions     |
|                  +---------------------------+------------------------------+
| Imports          | Compact filters           | Selected item / office       |
| Deliveries       |                           | Status and blocker           |
| Discrepancies    | Record / issue table      |                              |
| Provider records |                           | Evidence | History | Original|
|                  | Sort, filter, select      | Before/after + source dates  |
| Sources          |                           |                              |
| Settings/tools   | Count + pagination        | Reason + explicit decision   |
+------------------+---------------------------+------------------------------+
```

The inspector is a context view, not a second mutable record store. A read-only source inspection does not expose approval actions. Selection keeps the same clinician/office/version while switching evidence tabs. On narrow screens, navigation becomes a sheet and selecting a row opens a focused detail view with a clear return action. Only data tables may horizontally scroll; primary actions and context must remain reachable without page-level overflow.

Import detail uses a short staged flow: inspect file → map/preview → review findings → explicit acceptance. Mapping uses paired source/target columns and a selected-row preview; assistance is contextual and opt-in. Delivery review prioritizes candidate versus approved version, blockers and next action; job history/configuration move into secondary tabs or disclosure. Export review opens a scope/count/issue preview, then downloads the snapshot-bound workbook.

## Visual direction: precise, calm provider operations

Review recommendation, 2026-11-21: retain the proposed stack and staged migration. Strengthen the contract around a recognizable product identity and measured responsiveness. The component system is a starting vocabulary; the distinguishing feature is a well-composed source comparison and decision inspector. The current approved-export capture shows readable evidence but substantial vertical prose and stacked panels. Review this against the proposed populated workbench, not an empty dashboard.

The primary audience spends sustained time comparing office records and source assertions. Use a restrained, contemporary application aesthetic with clear surface separation, compact readable tables and deliberate typography. Technical depth belongs in the inspector; the main workspace answers which dataset is selected, what needs attention and what action is available.

| Element | Proposed U1.0 direction and review rule |
|---|---|
| Identity and surfaces | Light neutral canvas, white data/inspector surfaces, deep ink navigation, one restrained blue/teal action accent. Retain a small product mark; use subtle borders, 6–8 px corner radii and shadow mainly for overlays. Contrast-test actual token combinations. Avoid a stack of equally prominent cards. |
| Typography | Trial one locally served, licensed family such as IBM Plex Sans with a robust fallback; use tabular numerals for counts and monospace only for identifiers/raw evidence. Body/table text starts at 14–16 px; secondary metadata stays readable. Font choice and its transfer cost are part of the spike, not a prerequisite for functionality. |
| Density and hierarchy | Start with 40–44 px table rows, a compact toolbar and a small title hierarchy. Prefer whitespace between task regions over padding around every field. Make the selected record and the next action obvious; avoid all-caps instructions, giant statistics and repetitive explanatory copy. Preserve full values through keyboard-accessible detail/copy controls. |
| State vocabulary | Separate selection/action color from warning/error/success. Pair color with text/icon labels. Pending, proposed, approved and verified stay distinct; a green badge must not imply provider truth. Keep source and observation dates visible where they affect a decision. |
| Interaction and motion | Stable inspector and table geometry; restrained 120–180 ms feedback with reduced-motion support. No entrance choreography, animated counters or a motion dependency for decoration. Loading placeholders reserve space; errors preserve context and provide a specific recovery action. |
| Accessibility | Check text/UI contrast, visible focus, semantic tables and named row-open controls. Aim for 44 px touch actions and at least 24 px desktop targets or the applicable spacing exception. Dense rows must remain operable by keyboard. Sticky regions cannot cover focused controls at 200% zoom. |

At 1440 and 1280 px, review the table beside its inspector with realistic long names, office addresses, missing values and competing evidence. At 1024 px, collapse navigation or switch to a focused detail view when both panes would be cramped. At 390 px and 200% zoom, preserve the complete review/export task with an explicit return to the list. Use content fit, not a device label, to choose the breakpoint. Table overflow stays inside its region; do not hide critical values/actions to make a screenshot fit.

UI-W0 produces one primary direction and, only if needed, a small token/density variant of the same populated screen. Review default, selected, held, empty, loading, failure and stale states. A polished first view must also show where the operator starts; one integrated sample journey should be discoverable without reading project documentation. Dark mode, a command palette, customizable dashboards, bulk approval and a paid grid are deferred until a concrete workflow warrants them.

## Performance contract and evidence

These are proposed engineering targets, not measured results or promises of dataset capacity. UI-W0 records the baseline and freezes the measurement setup before production migration. A miss requires a diagnosis and a scoped remediation or an explicitly reviewed limit; do not silently relax targets after observing a failure.

Current code inspection identified two risks to measure: App.tsx eagerly imports the major workspace modules, and ApprovedExportReview.tsx fetches the full JSON export before displaying a five-row sample. The latter bounds rendered rows but not transfer, JSON parsing or server snapshot work. The existing chunk-size advisory also warrants inspection; suppressing the warning is not a performance improvement.

| Concern | Proposed budget or decision rule |
|---|---|
| Interaction | On the recorded reference desktop, p95 input-to-next-paint at or below 200 ms for row selection, tab opening and filter typing over at least 30 scripted interactions per fixture. Show immediate pending feedback for asynchronous work; separately measure time to useful data. This lab measure is not a field INP claim. |
| Initial task | Production build, cold cache: usable shell and first populated page within 3 seconds on the declared reference setup. Record browser/OS/CPU, viewport, server setup and fixture. Repeat at 4× CPU slowdown and 150 ms added network latency as a separate diagnostic stress case; do not mix its numbers into the reference result. |
| Rendering | Start with 50-row pages and a maximum 100 rendered data rows per table page. Use existing server pagination where available; preserve server-wide sort/filter meaning. Client paging is acceptable only for a measured, explicitly bounded payload. Add virtualization only if the actual task needs continuous scrolling and traces justify it; verify focus and screen-reader behavior. |
| Payload and work | Record actual response bytes, server duration, JSON/React work and longest main-thread tasks. Flag list/preview responses above 1 MiB for investigation. Lazy-load selected evidence/history and heavy workspace modules where measurements justify it; never eagerly fetch every record's full evidence. A paginated DOM alone does not solve a full-data fetch. |
| Request lifecycle | Debounce remote text search initially around 250 ms while reflecting typing immediately. Cancel superseded reads where supported and keep existing version/generation guards. Query keys include all relevant scope/filter/version inputs. Mutations invalidate affected data; caching cannot weaken approval or snapshot checks. |
| Bundle and memory | Record compressed initial JS/CSS and each lazy chunk before/after. Investigate initial transfer growth above 20%; document the cost of new primitives/fonts and remove unused template imports. After 20 list/detail/source switches, inspect retained data, listeners and requests for accumulation beyond the declared query-cache lifetime. No new runtime dependency merely to measure these. |

Use reproducible synthetic populations of 100, 1,000 and 10,000 records with long strings, repeated offices, missing fields and multiple issues. The largest is a stress case, not a claim of current end-to-end support. Keep fixture generation and data loading outside timed UI actions; test the actual HTTP/service path for release evidence. A mocked spike can establish layout and rendering behavior only. Run at least five cold-load trials, report range and median, and retain interaction traces and failures alongside the exact build/fixture. Measure export preparation separately from download transfer; feedback must remain responsive while it runs.

If current endpoints cannot supply bounded list/preview data, UI-W0 records a prerequisite contract revision before UI-W2 qualification. Such a revision must preserve full-export semantics, source/version scope, exact counts and expected-snapshot rejection; a summary response must not masquerade as the complete dataset. This is a bounded service dependency, not permission for a backend rewrite or silent API change. Do not claim scale qualification from a small fixture or a mocked response.

References: [TanStack Table v8 pagination](https://tanstack.com/table/v8/docs/guide/pagination) distinguishes client/server paging; [interaction responsiveness](https://web.dev/articles/inp) distinguishes next-paint feedback from asynchronous completion; [WCAG target-size guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) explains target size and spacing. The project budgets above are local design choices, not thresholds mandated by those sources.

## Component and code ownership

| Layer | Proposed location | Responsibility |
|---|---|---|
| Generated primitives | web/src/components/ui/ | Buttons, fields, selects, tabs, dialog/sheet, sidebar, alerts, skeletons and table primitives from the selected registry/base |
| Product shell | web/src/components/workbench/ | Navigation, context header, split-pane behavior, work table, source badge and inspector frame |
| Existing feature modules | Current intake/feed/reconciliation components, split as touched | Service calls, query/state guards and domain-specific content; move pure presentation into workbench components |
| Theme | One token/theme entrypoint plus small feature-specific layout styles | Typography, semantic color, spacing, density, focus and disabled/hover states |

Do not create an unbounded generic dashboard framework. Extract components when two actual migrated screens share behavior. Domain approval and validation remain in shared backend services. Existing source/API contracts do not change for a visual migration.

## Compatibility and dependency decisions

- The current official data-table guide uses TanStack Table v9; the repository uses v8. Keep v8 for the initial migration and use compatible APIs. Any major-version upgrade is a separate reviewed dependency change with regression evidence.
- Verify React/Vite/TypeScript/Node, Tailwind/plugin, registry primitive-base and overlay compatibility in the isolated spike. Pin exact resolved versions in the lockfile; do not run an uncontrolled dependency-upgrade sweep.
- Follow the existing Vite proxy and Vitest configuration; preserve server settings and test setup when adding Tailwind and import aliases. Alias settings must agree between TypeScript and Vite.
- Tailwind global styles/preflight can change legacy screens. Compare baseline screenshots and explicitly handle coexistence. Scope legacy selectors to legacy containers, remove migrated selectors and test remaining screens; adding the new theme beneath broad old button/headings rules is not acceptable.
- Inspect block/component registry output and license/attribution requirements before adoption. Adapt framework-specific example imports to the existing Vite SPA; do not copy Next.js routing/server-component assumptions.
- Retain current form state unless a concrete migrated interaction needs a form library. Additional router/state/grid libraries require a documented need; existing navigation/Query/Table remain the baseline.

## Ordered migration and specification revisions

| Stage | Contract / work | Completion gate |
|---|---|---|
| **UI-W0 — design and compatibility spike** | U1.0 draft: inventory controls/CSS, select official block/base/theme, validate versions in an isolated scratch checkout, build a populated shell + delivery/inspector proposal | Exact dependency delta, generated-component inventory, screen/state map, visual direction, baseline performance/response inventory, desktop/narrow screenshots and product review; no production dependency changes in this planning stage |
| **UI-W1 — shared foundation** | U1.1 freezes selected shell, tokens, primitives, import paths and coexistence/rollback strategy; add dependencies/configuration and migrate shell | Existing routes and state intact; migrated control states/overlays/focus correct; no regressions on unmigrated screens |
| **UI-W2 — complete delivery workbench** | U1.2 freezes table/inspector/approval/export interactions; migrate one full delivery → evidence → workbook task using existing endpoints | Active task visible without traversing configuration/history; selection, stale-snapshot rejection, actual download and reference-workload performance verified; any required bounded-preview contract resolved |
| **UI-W3 — import and adaptive mapping** | U1.3 freezes file inspection/mapping/quality/reuse/assistance states; migrate the next complete task | Original/normalized values, duplicate-header abstention, manual fallback and opt-in examples remain correct and operable |
| **UI-W4 — discrepancy/provider tools and retirement** | U1.4 covers selected case, identities, field decisions and supporting source screens; migrate remaining primary surfaces | Shared table/inspector/action patterns; remove replaced CSS/components; legacy tools isolated without duplicate main journeys |
| **UI-W5 — release acceptance** | U1.5 records final interaction/visual acceptance and retained limitations | Required frontend/build/browser checks, inspected outputs, keyboard/contrast/responsive checks, consistent screenshots, updated documentation and privacy-reviewed publication |

UI stages reuse the prior UX1–5 and AI-09 acceptance boundaries; stable new IDs below express migration-specific outcomes. Field-candidate materialization remains a separate domain slice after UI-W2 unless a concrete dependency requires rescheduling. Licensing/network and backend roadmap work remain intact.

## Acceptance and review boundaries

| ID | Required result |
|---|---|
| WM-01 | Official component system/config and reviewed shell are used by the migrated task; no placeholder navigation or decorative unimplemented features |
| WM-02 | A populated delivery list and selected inspector show scope/blocker/next action; selection and query/draft context survive navigation and reload |
| WM-03 | Primary controls have consistent normal/hover/focus/disabled/loading/error states; keyboard overlays have focus entry/return and meaningful labels |
| WM-04 | Desktop and narrow-width journeys retain accessible actions, table scrolling and a clear detail return; no page-level clipping |
| WM-05 | Reviewed mapping, source acceptance, dataset approval and observed verification remain distinct; stale requests cannot update another selected record |
| WM-06 | Inspected workbook/JSON content and selected scope match the preview; no regression in original/unknown-value presentation |
| WM-07 | Migrated screens no longer depend on competing legacy control styles; cleanup inventory identifies every remaining legacy surface |
| WM-08 | Owner-reviewed populated captures/prototype establish the chosen direction; automated tests and screenshot existence alone do not imply visual approval or uncoached usability |
| WM-09 | Reference/stress fixture results record response bytes, first useful page, interaction latency, bundle delta and repeated-navigation behavior; misses have explicit dispositions |
| WM-10 | Pagination/filtering and lazy evidence retain complete-scope semantics; preview limits do not silently truncate exported records or weaken snapshot guards |
| WM-11 | Populated states share the selected type/color/density system at desktop, intermediate and narrow widths, with keyboard/contrast/reduced-motion/zoom checks |
| WM-12 | One complete operator task is discoverable from the entry screen; record observed confusion separately from visual approval and automated correctness |

Run AGENTS-required frontend tests, build and full browser gates for completed production slices; inspect real downloads. For UI-W0, run docs checks and the isolated spike's relevant checks, label synthetic outputs and keep user storage untouched. Preserve baseline and failed-run evidence. A rollback restores the previous frontend commit while retaining unchanged API/data storage; do not clear runtime state to recover a UI deployment.

## Current status and next action

Reviewed planning document only. Visual direction and proposed performance gates are now explicit; no benchmark or prototype has been run for this review. shadcn/Tailwind installation, primitive-base selection, isolated prototype, owner visual review and all UI-W implementation gates remain open. NEXT selects UI-W0. The prior CSS release remains the working baseline and its test results are historical receipts, not migration results.
