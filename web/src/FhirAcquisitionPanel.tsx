import { useEffect, useRef, useState } from "react";
import { navigateWorkspace, useWorkspaceActionGuard, useWorkspaceQuery, workspaceHref } from "./workspaceNavigation";

type Source = { key: string; base: string; plan_net_version: string; parser_target: string; limits: Record<string, number>; interval_seconds: number; next_request_at?: string | null };
type Summary = { id: string; state: string; revision: number; next_retry: string | null; receipt_id: string | null; created_at: string };
type Capture = Summary & {
  partial: boolean; busy?: boolean; config: { resource_type: string; resource_id?: string; count: number; source_base: string };
  checkpoint: { pages: number; references: number; requests: number; bytes: number; error: string | null; pending: unknown[] };
  events: { seq: number; kind: string; artifact_sha: string | null; created_at: string; payload: Record<string, unknown> }[];
};
async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/fhir-acquisitions${path}`, body === undefined ? undefined : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => ({}));
    throw new Error(typeof problem.detail === "string" ? problem.detail : `Request failed (${response.status})`);
  }
  return response.json();
}

export function FhirAcquisitionPanel() {
  const selected = useWorkspaceQuery().get("acquisition") ?? "";
  const guard = useWorkspaceActionGuard();
  const [registry, setRegistry] = useState<{ source: Source; items: Summary[] }>();
  const [capture, setCapture] = useState<Capture>();
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [actor, setActor] = useState("");
  const [reason, setReason] = useState("");
  const [resourceType, setResourceType] = useState("Location");
  const [resourceId, setResourceId] = useState("");
  const [count, setCount] = useState(1);
  const [observedNow, setObservedNow] = useState(Date.now());
  const intent = useRef<{ key: string; id: string } | null>(null);
  const generation = useRef(0);
  useEffect(() => {
    let live = true;
    request<{ source: Source; items: Summary[] }>("").then(data => { if (live) setRegistry(data); })
      .catch(failure => { if (live) setError((failure as Error).message); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);
  useEffect(() => {
    const token = ++generation.current;
    setCapture(undefined); setError("");
    setDetailLoading(Boolean(selected));
    if (selected) request<Capture>(`/${encodeURIComponent(selected)}`)
      .then(data => { if (token === generation.current) setCapture(data); })
      .catch(failure => { if (token === generation.current) setError((failure as Error).message); })
      .finally(() => { if (token === generation.current) setDetailLoading(false); });
    return () => { generation.current += 1; };
  }, [selected]);

  async function refresh() {
    const origin = guard.capture();
    setBusy(true); setError("");
    try {
      const data = await request<{ source: Source; items: Summary[] }>("");
      if (!guard.isCurrent(origin)) return;
      setRegistry(data); setLoading(false);
      if (selected) {
        const detail = await request<Capture>(`/${encodeURIComponent(selected)}`);
        if (guard.isCurrent(origin)) setCapture(detail);
      }
      setObservedNow(Date.now());
    } catch (failure) {
      if (guard.isCurrent(origin)) setError((failure as Error).message);
    } finally { setBusy(false); }
  }
  async function act(action: "create" | "run-once" | "cancel") {
    const origin = guard.capture();
    setBusy(true); setError("");
    const body = { source: registry?.source.key, actor, reason, resource_type: resourceType, count,
      ...(resourceId.trim() ? { resource_id: resourceId.trim() } : {}) };
    const key = JSON.stringify(body);
    if (action === "create" && intent.current?.key !== key) intent.current = { key, id: crypto.randomUUID() };
    try {
      const result = await request<Capture>(action === "create" ? "" : `/${encodeURIComponent(selected)}/${action}`,
        action === "create" ? { ...body, request_id: intent.current!.id } :
          action === "cancel" ? { expected_revision: capture?.revision, actor, reason } : {});
      if (!guard.isCurrent(origin)) return;
      setCapture(result); setObservedNow(Date.now());
      setRegistry(prior => prior ? { ...prior, items: [result, ...prior.items.filter(item => item.id !== result.id)] } : prior);
      if (action === "create") navigateWorkspace("sources", { acquisition: result.id });
      if (result.busy) setError("Another local worker is active. Refresh this capture before continuing.");
    } catch (failure) {
      if (guard.isCurrent(origin)) setError(`${(failure as Error).message}. Operator and reason are preserved. Refresh to inspect retained progress; retrying unchanged creation reuses its request ID.`);
    } finally { setBusy(false); }
  }
  const terminal = capture && ["complete", "cancelled", "failed"].includes(capture.state);
  const validResourceId = !resourceId.trim() || /^[A-Za-z0-9.\-]{1,64}$/.test(resourceId.trim());
  const dueLater = Boolean(capture?.checkpoint.pending.length &&
    ((capture.next_retry && Date.parse(capture.next_retry) > observedNow) || (registry?.source.next_request_at && Date.parse(registry.source.next_request_at)>observedNow)));
  return <section className="iw-card iw-native" aria-label="Bounded FHIR captures">
    <div className="iw-title"><h2>Bounded FHIR captures</h2><button disabled={busy} onClick={() => void refresh()}>Refresh captures</button></div>
    <p>Queue a small directory query, run explicit capture steps, then review its intake separately. Loading this page never fetches from the payer.</p>
    {loading && <p role="status">Loading capture configuration…</p>}
    {registry?.source && <>
      <p>Configured source: <strong>{registry.source.key}</strong> · <code>{registry.source.base}</code></p>
      <p>Source-advertised Plan-Net: {registry.source.plan_net_version} · Parser target: {registry.source.parser_target}. Live compatibility remains unverified.</p>
      {registry.source.next_request_at && <p className="iw-notice">Recorded source cooldown until {registry.source.next_request_at}. It applies across captures, including cancelled ones. Refresh when due.</p>}
      <details><summary>Capture limits and source scope</summary>
        <p>At most {registry.source.limits.pages} pages, {registry.source.limits.references} direct references and {registry.source.limits.requests} requests. Minimum source spacing: {registry.source.interval_seconds} seconds. Completion covers this bounded query only.</p>
        <pre className="iw-json">{JSON.stringify(registry.source.limits, null, 2)}</pre>
      </details>
    </>}
    <form className="iw-form" onSubmit={event => { event.preventDefault(); void act("create"); }}>
      <label>Capture operator<input required maxLength={2000} value={actor} disabled={busy} onChange={event => setActor(event.target.value)} /></label>
      <label>Capture reason<input required maxLength={2000} value={reason} disabled={busy} onChange={event => setReason(event.target.value)} /></label>
      <label>Capture resource<select value={resourceType} disabled={busy} onChange={event => setResourceType(event.target.value)}>
        <option value="Location">Location</option><option value="PractitionerRole">PractitionerRole with supported references</option>
      </select></label>
      <label>Source-native resource ID (optional)<input maxLength={64} value={resourceId} disabled={busy} onChange={event => setResourceId(event.target.value)} /></label>
      <label>Requested page size<input type="number" min={1} max={20} required value={count} disabled={busy} onChange={event => setCount(Number(event.target.value))} /></label>
      <button className="iw-primary" disabled={busy || !registry?.source || !actor.trim() || !reason.trim() || !validResourceId || !Number.isInteger(count) || count < 1 || count > 20}>Queue bounded capture</button>
    </form>
    <p>Use a source-native Location or PractitionerRole ID to request one specific resource; it is not an NPI. Page size does not limit total results. An unfiltered query may reach the page budget and remain incomplete.</p>
    {!validResourceId && <p className="iw-notice">Resource IDs use 1–64 letters, digits, hyphens or periods.</p>}
    {error && <p className="iw-error" role="alert">{error}</p>}
    <label className="iw-capture-picker">Retained capture<select value={selected} disabled={busy} onChange={event => navigateWorkspace("sources", { acquisition: event.target.value })}>
      <option value="">Select a retained capture</option>
      {selected && !registry?.items.some(item => item.id === selected) && <option value={selected}>{selected}</option>}
      {registry?.items.map(item => <option key={item.id} value={item.id}>{item.state.replaceAll("_", " ")} · {item.created_at} · {item.id}</option>)}
    </select></label>
    {registry?.items.length === 0 && <p>No captures recorded. Queuing does not start a network request.</p>}
    {detailLoading && <p role="status">Loading retained capture…</p>}
    {capture?.id === selected && <article aria-label="Selected FHIR capture">
      <h3>Capture <code>{capture.id}</code></h3>
      <p>State: <strong>{capture.state.replaceAll("_", " ")}</strong> · Revision {capture.revision}{capture.partial ? " · Partial capture retained" : ""}</p>
      <p>{capture.config.resource_type} · Requested page size {capture.config.count} · <code>{capture.config.source_base}</code></p>
      {capture.config.resource_id && <p>Source resource ID: <code>{capture.config.resource_id}</code></p>}
      <p>{capture.checkpoint.pages} pages · {capture.checkpoint.references} references · {capture.checkpoint.requests} requests · {capture.checkpoint.bytes} retained bytes</p>
      {capture.checkpoint.error && <p className="iw-notice">Source result: {capture.checkpoint.error}</p>}
      {capture.next_retry && !terminal && <p>Next permitted request: <time>{capture.next_retry}</time>. Refresh when due. No retry runs in the background.</p>}
      {!terminal && <div className="iw-links">
        <button disabled={busy || dueLater} onClick={() => void act("run-once")}>Run one capture step</button>
        <button disabled={busy || !actor.trim() || !reason.trim()} onClick={() => void act("cancel")}>Cancel capture</button>
      </div>}
      {capture.receipt_id && <p><a href={workspaceHref("intake", { receipt: capture.receipt_id })}>Review captured reference evidence</a>. Completion does not accept evidence or approve a clinic dataset.</p>}
      <details><summary>Capture history and original responses</summary>
        {capture.events.map(event => <details key={event.seq}>
          <summary>{event.kind} · {event.created_at} · Event {event.seq}</summary>
          {event.artifact_sha && <p><a href={`/api/fhir-acquisitions/${encodeURIComponent(capture.id)}/events/${event.seq}/artifact`}>Download original response {event.seq}</a> · SHA-256 <code>{event.artifact_sha}</code></p>}
          <pre className="iw-json">{JSON.stringify(event.payload, null, 2)}</pre>
        </details>)}
      </details>
    </article>}
  </section>;
}
