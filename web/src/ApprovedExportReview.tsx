import { useEffect, useRef, useState } from "react";

type ExportPreview = {
  version_id: string;
  snapshot_id: string;
  snapshot_at: string;
  counts: { directory: number; unresolved_issues: number; sources: number; quarantined_rows: number; excluded_cross_scope_cases?: number };
  scope_notice?: string;
  directory: Record<string, unknown>[];
  unresolved_issues?: Record<string, unknown>[];
};
async function check(response: Response) {
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === "string" ? data.detail : `Export request failed (${response.status}). Refresh the preview and try again.`);
  }
  return response;
}
export function ApprovedExportReview({ versionId }: { versionId: string }) {
  const [preview, setPreview] = useState<ExportPreview | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const generation = useRef(0);
  useEffect(() => {
    generation.current += 1;
    setPreview(null); setError(""); setBusy(false);
    return () => { generation.current += 1; };
  }, [versionId]);
  const base = `/api/feed-versions/${encodeURIComponent(versionId)}/review-export`;
  async function load() {
    const requestGeneration = ++generation.current;
    setBusy(true); setError(""); setPreview(null);
    try {
      const data = await (await check(await fetch(base))).json() as ExportPreview;
      if (generation.current === requestGeneration) {
        if (data.version_id !== versionId) throw new Error("Export preview does not match the selected dataset version.");
        setPreview(data);
      }
    } catch (value) { if (generation.current === requestGeneration) setError(value instanceof Error ? value.message : String(value)); }
    finally { if (generation.current === requestGeneration) setBusy(false); }
  }
  async function download() {
    if (!preview || preview.version_id !== versionId) return;
    const requestGeneration = ++generation.current;
    setBusy(true); setError("");
    try {
      const response = await check(await fetch(`${base}?${new URLSearchParams({ format: "xlsx", expected_snapshot: preview.snapshot_id })}`));
      const blob = await response.blob();
      if (generation.current !== requestGeneration) return;
      const url = URL.createObjectURL(blob), anchor = document.createElement("a");
      anchor.href = url; anchor.download = "approved-directory-review.xlsx"; anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (value) { if (generation.current === requestGeneration) { setPreview(null); setError(value instanceof Error ? value.message : String(value)); } }
    finally { if (generation.current === requestGeneration) setBusy(false); }
  }
  const sampleFields = ["provider_name", "npi", "location_id", "address", "city", "state", "zip", "phone"].filter(field => preview?.directory.some(row => Object.hasOwn(row, field)));
  return <section className="mf-export-review" aria-label="Approved export review">
    <h3>Review the handoff</h3>
    <p>Prepare the approved directory with separate unresolved issues and source evidence. Later unapproved deliveries do not replace this directory.</p>
    <button disabled={busy} onClick={() => void load()}>{busy ? "Preparing export…" : "Preview approved workbook"}</button>
    {error && <p className="iw-error" role="alert">{error} Refresh the preview before downloading.</p>}
    {preview?.version_id === versionId && <>
      <dl className="mf-summary-counts">
        <div><dt>Directory rows</dt><dd>{preview.counts.directory}</dd></div>
        <div><dt>Unresolved issues</dt><dd>{preview.counts.unresolved_issues}</dd></div>
        <div><dt>Source records</dt><dd>{preview.counts.sources}</dd></div>
        <div><dt>Quarantined rows</dt><dd>{preview.counts.quarantined_rows}</dd></div>
      </dl>
      {!!preview.counts.excluded_cross_scope_cases && <p className="iw-notice" role="status">{preview.counts.excluded_cross_scope_cases} cross-scope {preview.counts.excluded_cross_scope_cases === 1 ? "case" : "cases"} excluded. {preview.scope_notice || "This issue list is limited to the selected dataset scope."}</p>}
      <p className="iw-muted">Open issues as of {preview.snapshot_at}. Directory, unresolved issues and sources remain separate workbook sheets.</p>
      {preview.directory.length > 0 && <details><summary>Inspect directory sample ({Math.min(preview.directory.length, 5)} rows)</summary>
        <div className="mf-evidence-table" role="region" aria-label="Approved directory export sample" tabIndex={0}><table><thead><tr>{sampleFields.map(field => <th key={field} scope="col">{field.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{preview.directory.slice(0, 5).map((row, index) => <tr key={index}>{sampleFields.map(field => <td key={field}>{row[field] === null ? "Null" : typeof row[field] === "object" ? JSON.stringify(row[field]) : String(row[field] ?? "Absent")}</td>)}</tr>)}</tbody></table></div>
      </details>}
      {(preview.unresolved_issues?.length ?? 0) > 0 && <div className="mf-evidence-table" role="region" aria-label="Unresolved export issues" tabIndex={0}>
        <table><caption>Unresolved issues · first {Math.min(preview.unresolved_issues!.length, 5)} of {preview.counts.unresolved_issues}</caption><thead><tr><th scope="col">Kind / status</th><th scope="col">Issue</th><th scope="col">Listed / proposed value</th></tr></thead><tbody>{preview.unresolved_issues!.slice(0, 5).map((issue, index) => <tr key={index}><td>{String(issue.kind ?? "Unknown")}<br />{String(issue.status ?? "Unknown")}</td><td>{String(issue.issue ?? "Not supplied")}</td><td>{String(issue.listed_value ?? "Not supplied")}<br />{String(issue.proposed_value ?? "Not supplied")}</td></tr>)}</tbody></table>
      </div>}
      <button className="mf-primary" disabled={busy} onClick={() => void download()}>Download reviewed workbook XLSX</button>
    </>}
  </section>;
}
