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
| **UI-W0 — design and compatibility spike** | U1.0 draft: inventory controls/CSS, select official block/base/theme, validate versions in an isolated scratch checkout, build a populated shell + delivery/inspector proposal | Exact dependency delta, generated-component inventory, screen/state map, baseline comparisons, desktop/narrow screenshots and product review; no production dependency changes in this planning stage |
| **UI-W1 — shared foundation** | U1.1 freezes selected shell, tokens, primitives, import paths and coexistence/rollback strategy; add dependencies/configuration and migrate shell | Existing routes and state intact; migrated control states/overlays/focus correct; no regressions on unmigrated screens |
| **UI-W2 — complete delivery workbench** | U1.2 freezes table/inspector/approval/export interactions; migrate one full delivery → evidence → workbook task using existing endpoints | Active task visible without traversing configuration/history; selection, stale-snapshot rejection and actual download verified |
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

Run AGENTS-required frontend tests, build and full browser gates for completed production slices; inspect real downloads. For UI-W0, run docs checks and the isolated spike's relevant checks, label synthetic outputs and keep user storage untouched. Preserve baseline and failed-run evidence. A rollback restores the previous frontend commit while retaining unchanged API/data storage; do not clear runtime state to recover a UI deployment.

## Current status and next action

Planning document only. shadcn/Tailwind installation, primitive-base selection, isolated prototype, owner visual review and all UI-W implementation gates remain open. NEXT selects UI-W0. The prior CSS release remains the working baseline and its test results are historical receipts, not migration results.
