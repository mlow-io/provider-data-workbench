# Next task: UI-W0 workbench design and migration readiness

Selected 2026-11-21 following the request for an explicit component-library/template migration. Planning and an isolated synthetic spike come first. The earlier reviewed-field candidate task is [retained](docs/archive/next-2026-11-21-field-materialization.md) and scheduled after the first complete UI workbench slice.

## Read and deliver

Read AGENTS, STATUS, SPEC, ROADMAP, [UI migration plan](docs/UI_WORKBENCH_MIGRATION.md) and OPERATOR_EXPERIENCE. Preserve the current qualified application and all user data.

1. Inventory current shell/controls/CSS and map them to proposed shadcn primitives and workbench components. Identify CSS rules that must retire, state/query guards that must remain and package-version risks. Inventory actual list/preview payloads and eager module imports; record any bounded-response prerequisite without changing the API silently.
2. Propose official @shadcn sidebar-07 as the shell starting point; inspect the registry component/block and select one consistent primitive base, icon library and token theme. Verify exact dependency compatibility in an isolated scratch checkout. Keep TanStack Table v8 unless a separate upgrade is justified.
3. Build a populated synthetic design spike: delivery table plus selected office/evidence inspector and export action. Include a held candidate, unresolved discrepancy, loading/failure/stale states and narrow-width detail navigation. Preserve exact original/interpreted-value semantics.
4. Record U1.0 dependency delta, layout/state map, component ownership, CSS coexistence/removal and rollback plan. Apply the migration plan’s typography/color/density brief, record production-build baseline and synthetic performance targets, and capture populated desktop/intermediate/narrow views plus adverse states for visual review. Distinguish mocked rendering evidence from actual service-path measurements.
5. After the chosen direction is reviewed, freeze U1.1 and execute UI-W1/W2 under the existing implementation authorization. Follow the migration plan and AGENTS checks; no backend/schema changes are required by this planning task.

## Planning boundary

This turn selects and documents the migration plan; it does not claim an installed library or redesigned release. UI-W0 can prototype in disposable storage. Defer production dependency changes until the compatibility and visual proposal are concrete. Keep technical docs/commits free of personal preparation and publish only through the clean-history release process.
