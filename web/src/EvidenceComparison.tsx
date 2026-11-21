import "./evidence-comparison.css";

type RecordValue = Record<string, unknown>;
function record(value: unknown): RecordValue {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as RecordValue : {};
}
function display(value: unknown, present: boolean): string {
  if (!present) return "Absent";
  if (value === null) return "Null";
  if (value === "") return "Blank";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
const title = (field: string) => field.replaceAll("_", " ");

/** Compare declared mappings only; similar column names never imply a mapping. */
export function EvidenceComparison({ original, interpreted, mapping = {}, caption = "Original evidence and normalized interpretation" }: {
  original: unknown;
  interpreted: unknown;
  mapping?: Record<string, string>;
  caption?: string;
}) {
  const source = record(original), result = record(interpreted);
  const usedColumns = new Set(Object.keys(result).map(field => mapping[field] ?? field));
  const rows = [
    ...Object.keys(result).map(field => ({ field, column: mapping[field] ?? field, target: true })),
    ...Object.keys(source).filter(column => !usedColumns.has(column)).map(column => ({ field: column, column, target: false })),
  ];
  if (!rows.length) return <p className="iw-muted">No comparable fields supplied. Inspect the retained payload below.</p>;
  return <>
    <div className="ec-scroll" role="region" aria-label={caption} tabIndex={0}>
      <table className="ec-table">
        <caption>{caption}</caption>
        <thead><tr><th scope="col">Field / source column</th><th scope="col">Original evidence</th><th scope="col">Normalized interpretation</th><th scope="col">Comparison</th></tr></thead>
        <tbody>{rows.map(({ field, column, target }) => {
          const supplied = Object.hasOwn(source, column);
          const before = display(source[column], supplied);
          const after = display(result[field], target);
          const comparison = !target ? "Source only" : !supplied ? "No same-column comparison" : before === after ? "Unchanged" : "Changed";
          return <tr key={`${target}:${field}`} data-changed={comparison === "Changed" || undefined}>
            <th scope="row">{title(field)}{column !== field && <small>{column}</small>}</th>
            <td><span className={!supplied || source[column] === null || source[column] === "" ? "ec-missing" : undefined}>{before}</span></td>
            <td><span className={!target || result[field] === null || result[field] === "" ? "ec-missing" : undefined}>{after}</span></td>
            <td className="ec-state">{comparison}</td>
          </tr>;
        })}</tbody>
      </table>
    </div>
    <details className="ec-payload"><summary>Original and interpreted payloads</summary><div className="iw-two"><section><h4>Original evidence</h4><pre className="iw-json">{JSON.stringify(original ?? {}, null, 2)}</pre></section><section><h4>Normalized interpretation</h4><pre className="iw-json">{JSON.stringify(interpreted ?? {}, null, 2)}</pre></section></div></details>
  </>;
}
