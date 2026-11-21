# Workbench UI migration plan

Design contract and historical migration reference, selected 2026-11-21. The shared shell and primary delivery/import/mapping/reconciliation controls are implemented; some supporting surfaces remain legacy. [STATUS](../STATUS.md) and the linked receipts describe verification and open limits; [NEXT](../NEXT.md) states the current task boundary.

## Outcome and proposed stack

A provider-data operator works in one application shell: navigation, contextual toolbar, compact source/record list, selected-record inspector and explicit action area. Import inspection, mapping/quality, discrepancy review and export share the same interaction model. Source/version/office context remains visible while original evidence and configuration are progressively disclosed.

The selected stack retains React/TypeScript/Vite and TanStack Query/Table, with **shadcn/ui + Tailwind CSS**. The shell composes official sidebar primitives after inspecting sidebar-07; see the implementation notes below. Template accounts and placeholder controls do not belong in product navigation. No new authentication or backend framework is implied.

A component library supplies reusable behavior and visual primitives; the table, inspector and decision flow require product-specific design. A sidebar alone does not complete migration of legacy screens.

Official references: [Vite installation](https://ui.shadcn.com/docs/installation/vite), [sidebar blocks](https://ui.shadcn.com/blocks/sidebar), [table composition](https://ui.shadcn.com/docs/components/data-table). These are starting references, not pinned implementation inputs. Inspect current CLI output before generating components and retain generated source for review.

## Pre-migration baseline and concrete gaps

Before migration, custom control styles and stacked delivery sections made the task harder to scan. The [migration receipt](evidence/canonical/workbench-migration-2026-11-21/README.md) records the selected implementation and remaining supporting surfaces. Preserve navigation, query guards, dirty drafts, source/attempt/version pins, approval boundaries, unknown/null/absent semantics and download integrity.

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

The component system is a starting vocabulary; source comparison and the decision inspector must remain understandable in populated states. Assess recognizable product identity and responsiveness alongside actual tasks.

The primary audience spends sustained time comparing office records and source assertions. Use a restrained, contemporary application aesthetic with clear surface separation, compact readable tables and deliberate typography. Technical depth belongs in the inspector; the main workspace answers which dataset is selected, what needs attention and what action is available.

| Element | Proposed U1.0 direction and review rule |
|---|---|
| Identity and surfaces | Light neutral canvas, white data/inspector surfaces, deep ink navigation, one restrained blue/teal action accent. Retain a small product mark; use subtle borders, 6–8 px corner radii and shadow mainly for overlays. Contrast-test actual token combinations. Avoid a stack of equally prominent cards. |
| Typography | Use a locally served, licensed family with a robust fallback; use tabular numerals for counts and monospace only for identifiers/raw evidence. Body/table text starts at 14–16 px; secondary metadata stays readable. Account for font transfer cost. |
| Density and hierarchy | Start with 40–44 px table rows, a compact toolbar and a small title hierarchy. Prefer whitespace between task regions over padding around every field. Make the selected record and the next action obvious; avoid all-caps instructions, giant statistics and repetitive explanatory copy. Preserve full values through keyboard-accessible detail/copy controls. |
| State vocabulary | Separate selection/action color from warning/error/success. Pair color with text/icon labels. Pending, proposed, approved and verified stay distinct; a green badge must not imply provider truth. Keep source and observation dates visible where they affect a decision. |
| Interaction and motion | Stable inspector and table geometry; restrained 120–180 ms feedback with reduced-motion support. No entrance choreography, animated counters or a motion dependency for decoration. Loading placeholders reserve space; errors preserve context and provide a specific recovery action. |
| Accessibility | Check text/UI contrast, visible focus, semantic tables and named row-open controls. Aim for 44 px touch actions and at least 24 px desktop targets or the applicable spacing exception. Dense rows must remain operable by keyboard. Sticky regions cannot cover focused controls at 200% zoom. |

At 1440 and 1280 px, review the table beside its inspector with realistic long names, office addresses, missing values and competing evidence. At 1024 px, collapse navigation or switch to a focused detail view when both panes would be cramped. At 390 px and 200% zoom, preserve the complete review/export task with an explicit return to the list. Use content fit, not a device label, to choose the breakpoint. Table overflow stays inside its region; do not hide critical values/actions to make a screenshot fit.

Review default, selected, held, empty, loading, failure and stale states. A polished first view must also show where the operator starts; one integrated sample journey should be discoverable without reading project documentation. Dark mode, a command palette, customizable dashboards, bulk approval and a paid grid are deferred until a concrete workflow warrants them.

## Performance contract and evidence

These local engineering targets are not promises of dataset capacity. The [qualification protocol](UI_QUALIFICATION.md) and its receipt report measured 100/1,000-record results and limitations. The original eager workspace imports and full-JSON preview transfer have since been addressed; the bounded preview still constructs the complete server snapshot. A miss needs diagnosis and a scoped remediation or reviewed limit.

| Concern | Proposed budget or decision rule |
|---|---|
| Interaction | On the recorded reference desktop, p95 input-to-next-paint at or below 200 ms for row selection, tab opening and filter typing over at least 30 scripted interactions per fixture. Show immediate pending feedback for asynchronous work; separately measure time to useful data. This lab measure is not a field INP claim. |
| Initial task | Production build, cold cache: usable shell and first populated page within 3 seconds on the declared reference setup. Record browser/OS/CPU, viewport, server setup and fixture. Repeat at 4× CPU slowdown and 150 ms added network latency as a separate diagnostic stress case; do not mix its numbers into the reference result. |
| Rendering | Start with 50-row pages and a maximum 100 rendered data rows per table page. Use existing server pagination where available; preserve server-wide sort/filter meaning. Client paging is acceptable only for a measured, explicitly bounded payload. Add virtualization only if the actual task needs continuous scrolling and traces justify it; verify focus and screen-reader behavior. |
| Payload and work | Record actual response bytes, server duration, JSON/React work and longest main-thread tasks. Flag list/preview responses above 1 MiB for investigation. Lazy-load selected evidence/history and heavy workspace modules where measurements justify it; never eagerly fetch every record's full evidence. A paginated DOM alone does not solve a full-data fetch. |
| Request lifecycle | Debounce remote text search initially around 250 ms while reflecting typing immediately. Cancel superseded reads where supported and keep existing version/generation guards. Query keys include all relevant scope/filter/version inputs. Mutations invalidate affected data; caching cannot weaken approval or snapshot checks. |
| Bundle and memory | Record compressed initial JS/CSS and each lazy chunk before/after. Investigate initial transfer growth above 20%; document the cost of new primitives/fonts and remove unused template imports. After 20 list/detail/source switches, inspect retained data, listeners and requests for accumulation beyond the declared query-cache lifetime. No new runtime dependency merely to measure these. |

Use reproducible synthetic populations of 100 and 1,000 records with long strings, repeated offices, missing fields and multiple issues. The 1,000-record workload is the selected upper qualification bound. Do not run a 10,000-record case. Keep fixture generation and data loading outside timed UI actions; test the actual HTTP/service path for release evidence. A mocked spike can establish layout and rendering behavior only. Run at least five cold-load trials, report range and median, and retain interaction traces and failures alongside the exact build/fixture. Measure export preparation separately from download transfer; feedback must remain responsive while it runs.

Bounded previews must preserve full-export semantics, source/version scope, exact counts and expected-snapshot rejection; a sample is not the complete dataset. Do not infer scale qualification from a small fixture or mocked response.

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

- The repository uses TanStack Table v8. A major-version upgrade is a separate dependency change requiring compatibility and regression review.
- Verify React/Vite/TypeScript/Node, Tailwind/plugin, registry primitive-base and overlay compatibility in the isolated spike. Pin exact resolved versions in the lockfile; do not run an uncontrolled dependency-upgrade sweep.
- Follow the existing Vite proxy and Vitest configuration; preserve server settings and test setup when adding Tailwind and import aliases. Alias settings must agree between TypeScript and Vite.
- Tailwind global styles/preflight can change legacy screens. Compare baseline screenshots and explicitly handle coexistence. Scope legacy selectors to legacy containers, remove migrated selectors and test remaining screens; adding the new theme beneath broad old button/headings rules is not acceptable.
- Inspect block/component registry output and license/attribution requirements before adoption. Adapt framework-specific example imports to the existing Vite SPA; do not copy Next.js routing/server-component assumptions.
- Retain current form state unless a concrete migrated interaction needs a form library. Additional router/state/grid libraries require a documented need; existing navigation/Query/Table remain the baseline.

## Ordered migration and specification revisions

The original stage plan is retained below as historical context, not a current task queue. See the implementation notes and receipts for actual scope and open gates.

| Stage | Contract / work | Completion gate |
|---|---|---|
| **UI-W0 — design and compatibility spike** | U1.0 draft: inventory controls/CSS, select official block/base/theme, validate versions in an isolated scratch checkout, build a populated shell + delivery/inspector proposal | Exact dependency delta, generated-component inventory, screen/state map, visual direction, baseline performance/response inventory, desktop/narrow screenshots and product review; no production dependency changes in this planning stage |
| **UI-W1 — shared foundation** | U1.1 freezes selected shell, tokens, primitives, import paths and coexistence/rollback strategy; add dependencies/configuration and migrate shell | Existing routes and state intact; migrated control states/overlays/focus correct; no regressions on unmigrated screens |
| **UI-W2 — complete delivery workbench** | U1.2 freezes table/inspector/approval/export interactions; migrate one full delivery → evidence → workbook task using existing endpoints | Active task visible without traversing configuration/history; selection, stale-snapshot rejection, actual download and reference-workload performance verified; any required bounded-preview contract resolved |
| **UI-W3 — import and adaptive mapping** | U1.3 freezes file inspection/mapping/quality/reuse/assistance states; migrate the next complete task | Original/normalized values, duplicate-header abstention, manual fallback and opt-in examples remain correct and operable |
| **UI-W4 — discrepancy/provider tools and retirement** | U1.4 covers selected case, identities, field decisions and supporting source screens; migrate remaining primary surfaces | Shared table/inspector/action patterns; remove replaced CSS/components; legacy tools isolated without duplicate main journeys |
| **UI-W5 — release acceptance** | U1.5 records final interaction/visual acceptance and retained limitations | Required frontend/build/browser checks, inspected outputs, keyboard/contrast/responsive checks, consistent screenshots, updated documentation and privacy-reviewed publication |

UI stages reuse UX1–5 and AI-09; the stable IDs below express migration-specific outcomes. Field-candidate materialization was implemented separately in [S1.3](FIELD_MATERIALIZATION_SPEC.md).

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

Run AGENTS-required frontend tests, build and full browser gates for completed production slices; inspect real downloads. Preserve baseline and failed-run evidence. Before rollback, check frontend/backend compatibility and preserve data and artifacts; do not clear runtime state to recover a UI deployment.

## Current implementation and remaining gates

The migration installs Tailwind 4 and official shadcn Radix Nova source components, with Lucide icons and locally served IBM Plex Sans. The shell composes the official Sidebar primitives after inspecting sidebar-07; it contains actual product navigation rather than template accounts/projects. React/Vite, Query 5 and Table 8 remain. TypeScript and Vite aliases agree. Generated source is owned in web/src/components/ui; selected registry dependencies are locked in package-lock.json.

Delivery review now uses a compact version table, selected inspector, evidence/original tabs, selected source-key comparison and pinned workbook controls. Narrow detail has explicit return navigation and query-change focus guards. Intake, mapping, normalization and reconciliation use shared controls; native checkbox and specialized selection behavior remain. The legacy QA console uses shared primary controls; supporting custom evidence/layout and remediation/native-source panels remain scoped legacy surfaces. Shell replacement removed old control overrides, and legacy styles are explicitly layered/scoped. This does not mean every historical feature stylesheet has been deleted.

Major workspace modules load on demand. An isolated build of the prior revision produced a 519.08 kB initial JS chunk (145.90 kB gzip); the integrated migration build produced 365.86 kB (118.26 kB gzip), plus route chunks. Initial CSS grows from 10.74 to 16.73 kB gzip, and three local font weights add transfer. These are build measurements, not loading-time or field-performance results. The bounded review-preview endpoint now supplies the small workbook sample, retaining complete counts and the full export token. The [100/1,000-record qualification](UI_QUALIFICATION.md) records actual service/browser measurements and exact limits; server snapshot construction remains proportional to the full data. No beyond-1,000 scale claim is asserted.

See the [migration receipt](evidence/canonical/workbench-migration-2026-11-21/README.md), [UI qualification receipt](evidence/canonical/ui-qualification-2026-11-21/README.md) and [correction receipt](evidence/canonical/correction-export-2026-11-21/README.md) for checks and captures. The selected 100/1,000-record engineering measurements include interaction, one slowed-condition diagnostic and a finite heap observation; they do not establish broader capacity or leak freedom. Owner visual acceptance, uncoached usability, exhaustive accessibility/zoom qualification and retirement of supporting legacy surfaces remain open.
