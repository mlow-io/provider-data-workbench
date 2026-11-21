# Next task: workbench performance and supporting-surface qualification

The owner authorized migration implementation on 2026-11-21. The shared shell and primary delivery/import/mapping/reconciliation controls now use the selected component system. Read [STATUS](STATUS.md), [migration contract](docs/UI_WORKBENCH_MIGRATION.md) and [receipt](docs/evidence/canonical/workbench-migration-2026-11-21/README.md). Preserve current runtime storage and completed decisions.

1. Measure the actual HTTP path with reproducible 100/1,000/10,000-record synthetic workloads. Record response bytes, main-thread work, first useful page, repeated-navigation retention and reference/stress conditions. Do not infer scale from build sizes or small fixtures.
2. Freeze a bounded workbook-preview contract if full-export payloads exceed the review budget. Preserve full JSON/XLSX semantics, exact population counts, scope and snapshot rejection; add affected service/UI regression checks before switching the consumer.
3. Inventory remaining native-source/remediation/custom evidence controls and styles; migrate supporting surfaces under the shared system without changing data meaning. Verify narrow tables retain all fields through internal scroll.
4. Record WM acceptance outcomes explicitly. Obtain owner visual feedback on populated captures and retain the independent uncoached-human gate. Actual-model/network/source expansion remains separately scoped.

Use at most two disjoint bounded GPT-6.1 Terra workers, medium by default/high for interaction or integration complexity. The lead owns performance design, interpretation, visual verification and sanitized publication. Continue the retained [field-materialization brief](docs/archive/next-2026-11-21-field-materialization.md) after UI performance/interaction issues affecting the primary task are resolved. This continuation does not authorize silently revising backend semantics or claiming unmeasured performance targets.
