import { useEffect, useRef, useState } from "react";
import { workspaceHref } from "./workspaceNavigation";

export type SupportingReference = { attempt_id: string; locator: string; path: string; field: string };
export type NativePreview = {
  format_version: number;
  parser_version: string;
  validation: { structural: string; profile: string; terminology: string };
  coverage: { entry_count: number; supported_count: number; eligible_count: number; unsupported_count: number; invalid_count: number; unresolved_count: number; assertion_count: number; completeness: string };
  resources: { locator: string; resource_type: string | null; id: unknown; original: unknown; eligible?: boolean; problems: unknown[] }[];
  references: { path: string; raw_target: unknown; state: string; target: string | null }[];
  assertions: { locator: string; clinician_locator: string; location_locator: string; phone: unknown; address: unknown; source_network_reference: unknown; supporting_refs: Omit<SupportingReference, "attempt_id">[] }[];
  findings: { code: string; locator: string; message: string; severity: string }[];
  sample_truncated?: boolean;
};
type NativeReceipt = {
  id: string; label?: string; source?: string; designation?: string; state?: string;
  attempt_id?: string; artifact_sha?: string; is_current_attempt?: boolean; duplicate_of?: string;
  preview?: { native?: NativePreview; error?: string; valid_count?: number };
  attempts?: unknown[]; metadata?: Record<string, unknown>;
};
const show = (value: unknown) => typeof value === "string" ? value : value == null ? "Unavailable in sample" : JSON.stringify(value);
const json = (value: unknown) => JSON.stringify(value ?? null, null, 2);
const object = (value: unknown): Record<string, unknown> | undefined =>
  value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : undefined;

export function NativeEvidencePanel({ receipt, refresh, readOnly = false, loadError = "" }: {
  receipt: NativeReceipt; refresh: () => Promise<void>; readOnly?: boolean; loadError?: string;
}) {
  const native = receipt.preview?.native;
  const assembled = receipt.metadata?.representation === "derived_assembled_searchset";
  const query = object(receipt.metadata?.query);
  const queryValidation = object(receipt.metadata?.query_validation);
  const [actor, setActor] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const intent = useRef<{ key: string; requestId: string } | null>(null);
  const live = useRef(true);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  async function act(action: "reference_resources" | "reject" | "reprocess") {
    setBusy(true); setError("");
    const body = action === "reprocess" ? { expected_attempt: receipt.attempt_id } : {
      expected_attempt: receipt.attempt_id, policy: action, actor, reason,
    };
    const key = JSON.stringify(body);
    if (intent.current?.key !== key) intent.current = { key, requestId: crypto.randomUUID() };
    const requestBody = action === "reprocess" ? body : { ...body, request_id: intent.current.requestId };
    try {
      const response = await fetch(`/api/intakes/${encodeURIComponent(receipt.id)}/${action === "reprocess" ? "mapping" : "commit"}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(requestBody),
      });
      if (!response.ok) {
        const problem = await response.json().catch(() => ({}));
        throw new Error(typeof problem.detail === "string" ? problem.detail : `Request failed (${response.status})`);
      }
      if (live.current) await refresh();
    } catch (failure) {
      if (live.current) setError(`${(failure as Error).message}. Your reviewer and reason are preserved. Refresh to inspect current evidence; retrying unchanged acceptance reuses its request ID.`);
    } finally {
      if (live.current) setBusy(false);
    }
  }
  const terminal = ["committed", "duplicate_delivery", "rejected"].includes(receipt.state ?? "");
  return <section className="iw-native" aria-label="Native FHIR evidence">
    <p className="iw-eyebrow">Saved FHIR directory evidence{readOnly ? " / Read only" : ""}</p>
    <h2>{receipt.label}</h2>
    <p>{receipt.source} · {receipt.designation} · <strong>{receipt.state?.replaceAll("_", " ")}</strong></p>
    <p>Receipt <code>{receipt.id}</code> · Attempt <code>{receipt.attempt_id}</code></p>
    {receipt.duplicate_of && <p>Repeat delivery. The receipt and review decision are retained separately.</p>}
    {readOnly && receipt.is_current_attempt === false && <p role="status">A newer interpretation exists; this evidence stays pinned.</p>}
    <div className="iw-links">
      {receipt.artifact_sha && <a href={`/api/intakes/${encodeURIComponent(receipt.id)}/artifact`}>{assembled ? "Download assembled searchset" : "Download original"}</a>}
      <a href={`/api/intakes/${encodeURIComponent(receipt.id)}/packet`}>Evidence packet JSON</a>
      <a href={workspaceHref("reconciliation")}>Compare retained sources</a>
      {readOnly && <a href={workspaceHref("intake", { receipt: receipt.id })}>Open current receipt workspace</a>}
    </div>
    {assembled && <p className="iw-notice">This searchset was assembled from captured responses. Source-advertised Plan-Net: {show(receipt.metadata?.source_plan_net_version)} · Parser target: {show(receipt.metadata?.parser_target)}. Compatibility is unverified.
      {typeof receipt.metadata?.acquisition_id === "string" && <> <a href={`/api/fhir-acquisitions/${encodeURIComponent(receipt.metadata.acquisition_id)}`}>Acquisition history JSON</a> retains original response-artifact references.</>}
    </p>}
    {assembled && query && <section aria-label="Source query scope">
      <h3>Source query scope</h3>
      <p>Requested {show(query.resource_type)} · Source resource ID <code>{show(query.resource_id)}</code></p>
      {queryValidation?.version === 1 ? <>
        <p>Checked matches: {show(queryValidation.matched_entries)} · Included context: {show(queryValidation.included_entries)} · Source outcomes: {show(queryValidation.outcome_entries)}</p>
        <p>Matching entries without a search mode: {show(queryValidation.implicit_match_entries)}. Counts cover captured search pages; reference acceptance and profile validation remain separate.</p>
      </> : <p className="iw-notice">{queryValidation
        ? "Unsupported search-match report version; inspect the evidence packet."
        : "Match validation was not recorded for this capture; inspect the retained responses."}</p>}
    </section>}
    <p className="iw-notice">Reference evidence requires review. Acceptance does not approve a clinic dataset, link identities, establish local network membership or create correction work.</p>
    {receipt.preview?.error && <p role="alert" className="iw-error">{receipt.preview.error}</p>}
    {native && <>
      <h3>Resource coverage</h3>
      <p>{native.coverage.entry_count} entries · {native.coverage.supported_count} supported · {native.coverage.eligible_count} eligible resources · {native.coverage.invalid_count} invalid resources · {native.coverage.unsupported_count} unsupported · {native.coverage.unresolved_count} unresolved references · {native.coverage.assertion_count} office assertions</p>
      <p>Coverage: {native.coverage.completeness.replaceAll("_", " ")}. Missing from this response does not establish termination.</p>
      <p>Profile validation: <strong>{native.validation.profile.replaceAll("_", " ")}</strong> · Terminology validation: <strong>{native.validation.terminology.replaceAll("_", " ")}</strong>. Structural inspection is separate from standards validation.</p>
      {native.sample_truncated && <p role="status">Bounded sample shown. Download the evidence packet for complete retained values and counts.</p>}
      <h3>Resources</h3>
      {native.resources.map((resource, index) => <details key={index}>
        <summary>{show(resource.resource_type ?? "Malformed entry")} · {String(resource.id ?? "No source ID")} · {resource.eligible ? "Eligible reference resource" : "Retained for inspection"}</summary>
        <p><code>{show(resource.locator)}</code></p>
        <pre className="iw-json">{json(resource.original)}</pre>
        {!!resource.problems?.length && <pre className="iw-json">{json(resource.problems)}</pre>}
      </details>)}
      <h3>Reference resolution</h3>
      {native.references.length === 0 && <p>No source references in this interpretation.</p>}
      {native.references.filter(reference => reference.state !== "resolved").map((reference, index) => <details key={index}>
        <summary>{show(reference.state)} · {String(reference.raw_target ?? "Identifier-only reference")}</summary>
        <p><code>{show(reference.path)}</code> → <code>{show(reference.target ?? "Unresolved target")}</code></p>
      </details>)}
      <details><summary>Resolved references ({native.references.filter(reference => reference.state === "resolved").length} in sample)</summary>
        {native.references.filter(reference => reference.state === "resolved").map((reference, index) => <p key={index}><code>{show(reference.path)}</code> → <code>{show(reference.target)}</code></p>)}
      </details>
      <h3>Derived office evidence</h3>
      {native.assertions.length === 0 && <p>No unambiguous office assertion can be projected. Inspect findings and original resources.</p>}
      {native.assertions.map((assertion, index) => <details key={index}>
        <summary>Office assertion · {show(assertion.location_locator)} · {String(assertion.phone ?? "Unresolved phone")}</summary>
        <pre className="iw-json">{json(assertion)}</pre>
        <p>Source network: {String(assertion.source_network_reference ?? "Unknown")}. Local network binding: unknown until separately reviewed.</p>
      </details>)}
      <h3>Findings</h3>
      {native.findings.length === 0 ? <p>No supported-structure findings. Full profile validation may still be unassessed.</p> : native.findings.map((finding, index) => <p key={index}><strong>{show(finding.code)}</strong> · <code>{show(finding.locator)}</code> · {show(finding.message)}</p>)}
    </>}
    {(error || loadError) && <p className="iw-error" role="alert">{error || loadError}</p>}
    {!readOnly && <>
      <form className="iw-form iw-decision" onSubmit={event => { event.preventDefault(); void act("reference_resources"); }}>
        <label>Reference reviewer<input required value={actor} disabled={busy} onChange={event => setActor(event.target.value)} /></label>
        <label>Reference review reason<input required value={reason} disabled={busy} onChange={event => setReason(event.target.value)} /></label>
        <button className="iw-primary" disabled={busy || terminal || receipt.state !== "preview_ready" || !receipt.preview?.valid_count || !actor.trim() || !reason.trim()}>Accept reference resources</button>
        <button type="button" disabled={busy || terminal || !actor.trim() || !reason.trim()} onClick={() => void act("reject")}>Reject reference intake</button>
      </form>
      <button disabled={busy} onClick={() => void act("reprocess")}>Reprocess saved FHIR evidence</button>
    </>}
    <button disabled={busy} onClick={() => void refresh().catch(failure => setError((failure as Error).message))}>Refresh native evidence</button>
    <details><summary>Native interpretation history</summary><pre className="iw-json">{json(receipt.attempts)}</pre></details>
  </section>;
}
