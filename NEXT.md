# Next implementation: explicit reviewed-field candidate materialization

The owner authorized implementation, technical Git commits and privacy-reviewed public results on 2026-11-21. The bounded adaptive ingestion/workbook release is implemented and qualified; see STATUS and the adaptive-release receipt. The long-term roadmap remains active, with no claim that its future rows are already built.

## Immediate contract and implementation work

1. Inspect FieldReconciliation, managed-feed approval and the new workbook. Identify the exact gap between a reviewed contact decision and a new consumer-eligible roster candidate.
2. Freeze a narrow S1.3 contract: selected office/field decisions, pinned base dataset/link/decision versions, explicit candidate creation, retained original and proposed values, completeness, conflicting/stale decisions, repeat/restart and separate dataset approval. No implicit promotion or external verification.
3. Implement one two-office phone-change journey through the existing services and UI. Pending/unresolved values remain excluded; the prior approved dataset remains readable until a separate explicit approval. Avoid a second canonical store or unrestricted grid edits.
4. Independently inspect output workbook/JSON values and lineage before/after approval; qualify no-op/repeat/stale/restart/conflict behavior. Run AGENTS-required affected checks; preserve failures and update STATUS/SPEC/API/data docs with code.
5. Continue P5 source-specific licensing and P6 network milestones through their named spec revisions. Use bounded named source access; absent credentials or source samples remain explicit gates, never synthetic success claims.

## Preserved boundaries

Model-context plumbing is controlled-provider tested; actual-model quality requires configured approved access and separate evaluation. Licensing entries from NPPES are registry assertions, not board verification. A supported FHIR subset is not a conformant server, payer writeback or recipient-template compatibility. Existing original histories and real data remain outside public release inputs.

Use the current local implementation worktree for continuation. The clean-history public candidate is a release surface, not a reason to merge private history. Inspect actual refs/status before publication. Keep commit messages and product documentation technical; ignore private preparation and chat exports.
