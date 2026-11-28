# Workbench interface specification

## Purpose and scope
Support an analyst moving from a source discrepancy to an evidenced decision and follow-up. Provider Bench retains its existing provider workflows. The separate payment workbench uses the same visual vocabulary with its own calculations and storage. This specification describes the local review implementation; it does not imply production hosting or authenticated client isolation.

## Visual system
- IBM Plex Sans: body 14px/1.5; page heading 24px/1.25 at weight 600; section heading 16px/1.4 at 600; supporting text 12px/1.5. IBM Plex Mono for record identifiers only. Amounts use tabular numerals.
- Canvas #f4f7f7, white cards, ink #172d32, muted text #52676d, border #dbe4e5. Primary teal #0f766e with white text. Status green/amber/red remain distinct and always have text labels.
- Spacing scale 4, 8, 12, 16, 20, 24, 32px. Desktop page padding 24px; mobile 16px. Card padding 20px. Related panels gap 16px; major sections gap 24px.
- Cards use 8px corners, a subtle 1px border and little or no shadow. Avoid nested cards for every datum.
- Controls remain keyboard accessible with visible focus. Body text stays readable; tables may scroll horizontally within their container.

## Navigation and queue
Stable sidebar, workspace context, and one page heading. Distinguish synthetic demo from API-backed local workspace accurately. Summary values must explain their scope; absence of open issues does not establish verified accuracy. Queue rows include issue, evidence difference, status and next action. Ownership/follow-up belong next to the case. Keep existing filters and exports.

## Case workspace
Offer quick inspection and a wider focused workspace for sustained work. Reuse the same case content and action logic, not a second implementation of state transitions.
1. Case heading, office/provider identity, readable status and follow-up context.
2. Evidence area: current value, proposed/observed value, source identity and date when available. Unknown values remain explicitly unknown.
3. Action area: applicable next action, required reviewer inputs, clear saved/error feedback.
4. Activity area: ordered persisted decisions and follow-up observations.
Desktop uses roughly 2:1 evidence/actions columns; narrow screens stack. Evidence and actions must both remain accessible without horizontal page overflow. Technical version counters are secondary; stale data produces an actionable refresh message.

## Payments
Independent local app. Reuse normalized CSV imports and reconciliation SQL; monetary amounts remain integer cents. Match uses payer + payee + trace with ambiguity surfaced. $160 expected/$160 deposited is a match; $160/$150 is an unexplained $10 payment discrepancy, not proof of claim underpayment. Missing/duplicate evidence stays unknown/ambiguous.
Case notes, owner, follow-up and review decisions persist in SQLite. Calculation status and review status are separate. Source refresh invalidates stale decisions. Exports carry raw evidence and case activity. First setup settings are saved and affect actual case defaults. All demos are synthetic. AI is optional and may draft explanations later; it cannot alter calculations or resolve a case.

## Acceptance
- Existing provider action tests and build pass; phone correction progression still works.
- Desktop and mobile queues and case view remain usable; keyboard controls and labels retained.
- Payment import, $160 match/$10 discrepancy, note, owner, follow-up and export work end to end and survive server restart.
- Import failures are atomic; repeated identical inputs do not duplicate records; stale revisions are rejected; missing evidence cannot become zero or a verified resolution.
- Keep all changes local for review. No deploy or push as part of this implementation.
