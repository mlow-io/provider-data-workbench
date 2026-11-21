import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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
  const [selectedIndex, setSelectedIndex] = useState(0);
  const entries = comparison?.entries ?? [];
  const selected = entries[selectedIndex] ?? entries[0];
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
        <div className="mf-evidence-table"><Table aria-label="Delivery comparison entries">
          <TableHeader><TableRow><TableHead>Source key</TableHead><TableHead>Comparison</TableHead><TableHead>Fields</TableHead></TableRow></TableHeader>
          <TableBody>{entries.slice(0, 20).map((entry, index) => <TableRow key={index} data-state={entry === selected ? "selected" : undefined}>
            <TableCell><Button variant="ghost" aria-pressed={entry === selected} onClick={() => setSelectedIndex(index)}>{entry.key ?? "Unresolved key"}</Button></TableCell>
            <TableCell><Badge variant="secondary">{entry.status.replaceAll("_", " ")}</Badge></TableCell>
            <TableCell>{entry.fields.length}</TableCell>
          </TableRow>)}</TableBody>
        </Table></div>
        {selected && <section className="mf-selected-evidence" aria-label="Selected source key evidence"><h4>Source key · {selected.key ?? "Unresolved key"}</h4><p>These values belong to the selected source key. An identity or office match is a separate review.</p><ComparisonEvidence entry={selected} /></section>}

      </> : <p>No row-level comparison entries were supplied in this report.</p>}
    </>}
  </section>;
}
