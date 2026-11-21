import type { DeliveryComparison } from "./RecurringImport";

const counts = [
  ["new", "New keys"], ["changed", "Changed keys"], ["unchanged", "Unchanged keys"],
  ["missing_from_this_delivery", "Missing from delivery"], ["unresolved", "Unresolved rows"], ["blocked_invalid", "Invalid rows"],
] as const;
function value(input: unknown, present?: boolean) {
  if (present === false) return "Not supplied";
  if (input === null) return "Null";
  if (input === undefined) return "Not supplied";
  if (input === "") return "Empty text";
  return typeof input === "object" ? JSON.stringify(input) : String(input);
}

type Entry = NonNullable<DeliveryComparison["entries"]>[number];
function FieldEvidence({ fields }: { fields: Entry["fields"] }) {
  return <>{fields.map((field, index) => <div className="mf-change" key={index}>
    <strong>{field.field.replaceAll("_", " ")}</strong>
    <span className="mf-change-before">Before: {value(field.old, field.old_present)}</span>
    <span className="mf-change-after">After: {value(field.new, field.new_present)}</span>
  </div>)}</>;
}
function ComparisonEvidence({ entry }: { entry: Entry }) {
  if (!entry.fields.length) return <>No field differences supplied; inspect original evidence for this entry.</>;
  if (entry.status === "missing" || entry.status === "new") return <>
    <p>{entry.status === "missing" ? "This key is absent from the delivery; termination has not been established." : "This key has no matching key in the pinned baseline."}</p>
    <details><summary>{entry.fields.length} retained field comparisons</summary><FieldEvidence fields={entry.fields} /></details>
  </>;
  return <><FieldEvidence fields={entry.fields.slice(0, 3)} />{entry.fields.length > 3 && <details><summary>{entry.fields.length - 3} more field comparisons</summary><FieldEvidence fields={entry.fields.slice(3)} /></details>}</>;
}

export function DeliveryReviewSummary({ comparison, baselineVersion }: { comparison: DeliveryComparison | null; baselineVersion?: string | null }) {
  const entries = comparison?.entries ?? [];
  const total = typeof comparison?.entry_count === "number" ? comparison.entry_count : entries.length;
  return <section aria-label="Delivery comparison">
    <h3>What changed in this delivery</h3>
    <p>{baselineVersion ? <>Compared with pinned dataset <code>{baselineVersion}</code>.</> : "No approved baseline is recorded for this report. Baseline-dependent checks are not assessed."} Missing keys do not establish termination.</p>
    {!comparison ? <p>Comparison is unavailable. Inspect the quality findings and retained evidence.</p> : <>
      {entries.some(entry => entry.interpretation_changed) && <p className="iw-notice">Interpretation rules changed between deliveries. Differences may reflect mapping changes; compare the retained originals before attributing a change to the source.</p>}
      <dl className="mf-summary-counts">{counts.map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{typeof comparison[key] === "number" ? comparison[key] : "Not assessed"}</dd></div>)}</dl>
      <p className="iw-muted">Keys belong to the source delivery; they are not counts of reviewed clinicians or offices.</p>
      {entries.length > 0 ? <>
        <p>Showing {Math.min(entries.length, 20)} of {total} comparison entries. This is a bounded evidence preview.</p>
        <div className="mf-evidence-table"><table>
          <thead><tr><th scope="col">Source key</th><th scope="col">Comparison</th><th scope="col">Field evidence</th></tr></thead>
          <tbody>{entries.slice(0, 20).map((entry, index) => <tr key={index}>
            <td><code>{entry.key ?? "Unresolved key"}</code></td>
            <td>{entry.status.replaceAll("_", " ")}</td>
            <td><ComparisonEvidence entry={entry} /></td>
          </tr>)}</tbody>
        </table></div>
      </> : <p>No row-level comparison entries were supplied in this report.</p>}
    </>}
  </section>;
}
