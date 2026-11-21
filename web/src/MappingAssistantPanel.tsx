import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";
import { NativeSelect, NativeSelectOption } from "./components/ui/native-select";
import { useRef, useState } from "react";
import { useWorkspaceActionGuard } from "./workspaceNavigation";

type Summary = { id: string; state: string; revision: number; attempt_id: string; proposal_id: string | null; created_at: string };
type Run = Summary & { request_sha: string; response_sha: string | null; busy?: boolean;
  result: { error?: string; explanation?: string; response_truncated?: boolean; unresolved?: { field: string; reason: string }[]; conservative_estimated_usd?: number; usage?: unknown } };
type Registry = { configuration: { available: boolean; experimental: boolean; reason: string | null; model: string; limits: { rows: number; columns: number; cell_bytes: number; reserve_usd: number; lifetime_usd: number } }; source_processing_allowed: boolean; reserved_usd: number; items: Summary[] };
async function request<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, body === undefined ? undefined : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string" ? error.detail : `Request failed (${response.status})`);
  }
  return response.json();
}

export function MappingAssistantPanel({ receiptId, attemptId, onProposalReady }: {
  receiptId: string; attemptId: string; onProposalReady: () => Promise<void>;
}) {
  const base = `/api/intakes/${encodeURIComponent(receiptId)}/assistant-runs`;
  const guard = useWorkspaceActionGuard();
  const [open, setOpen] = useState(false);
  const [registry, setRegistry] = useState<Registry>();
  const [run, setRun] = useState<Run>();
  const [actor, setActor] = useState("");
  const [reason, setReason] = useState("");
  const [permission, setPermission] = useState(false);
  const [includeApprovedExamples, setIncludeApprovedExamples] = useState(false);
  const [busy, setBusy] = useState(false);
  const [invoking, setInvoking] = useState(false);
  const [error, setError] = useState("");
  const intent = useRef<{ key: string; id: string } | null>(null);
  function retain(result: Run) {
    setRun(current => current?.id === result.id && current.revision > result.revision ? current : result);
    setRegistry(current => current ? { ...current, items: [result, ...current.items.filter(item => item.id !== result.id)] } : current);
  }
  async function refresh() {
    const origin = guard.capture();
    setError(""); setBusy(true);
    try {
      const data = await request<Registry>(base);
      if (!data.configuration || !Array.isArray(data.items)) throw new Error("Mapping assistance configuration is unavailable");
      if (!guard.isCurrent(origin)) return;
      setRegistry(data);
      if (run) {
        const result = await request<Run>(`${base}/${encodeURIComponent(run.id)}`);
        if (guard.isCurrent(origin)) retain(result);
      }
    } catch (failure) { if (guard.isCurrent(origin)) setError((failure as Error).message); }
    finally { if (guard.isCurrent(origin)) setBusy(false); }
  }
  async function select(id: string) {
    if (!id) { setRun(undefined); return; }
    const origin = guard.capture(); setBusy(true); setError("");
    try {
      const result = await request<Run>(`${base}/${encodeURIComponent(id)}`);
      if (guard.isCurrent(origin)) retain(result);
    } catch (failure) { if (guard.isCurrent(origin)) setError((failure as Error).message); }
    finally { if (guard.isCurrent(origin)) setBusy(false); }
  }
  async function act(action: "create" | "run-once" | "cancel") {
    const origin = guard.capture(); setError("");
    if (action === "run-once") setInvoking(true); else setBusy(true);
    const body = { expected_attempt: attemptId, actor, reason, external_processing: permission, ...(includeApprovedExamples ? { include_approved_examples: true } : {}) };
    const key = JSON.stringify(body);
    if (action === "create" && intent.current?.key !== key) intent.current = { key, id: crypto.randomUUID() };
    try {
      const result = await request<Run>(action === "create" ? base : `${base}/${encodeURIComponent(run!.id)}/${action}`,
        action === "create" ? { ...body, request_id: intent.current!.id } : action === "cancel" ? { expected_revision: run!.revision, actor, reason } : {});
      if (!guard.isCurrent(origin)) return;
      retain(result);
      if (result.busy) setError("Another local worker is active. Refresh to inspect this run before continuing.");
      if (result.state === "succeeded") await onProposalReady();
      if (action === "run-once") {
        const latest = await request<Registry>(base);
        if (guard.isCurrent(origin)) setRegistry(latest);
      }
    } catch (failure) {
      if (guard.isCurrent(origin)) setError(`${(failure as Error).message}. Your operator, reason and permission are preserved. Refresh retained history before retrying an uncertain request; unchanged creation reuses its request ID.`);
    } finally {
      if (guard.isCurrent(origin)) { if (action === "run-once") setInvoking(false); else setBusy(false); }
    }
  }
  const terminal = run && ["succeeded", "failed", "cancelled", "unavailable"].includes(run.state);
  return <section className="np-assistant iw-native" aria-label="Optional mapping assistance">
    <Button variant="outline" type="button" aria-expanded={open} onClick={() => { setOpen(!open); if (!open && !registry) void refresh(); }}>Optional mapping assistance</Button>
    {open && <>
      <p>Experimental: queue a bounded sample, inspect its request, then explicitly run the model. A result can only save a proposed recipe. Manual rules below remain available.</p>
      <Button variant="outline" type="button" disabled={busy} onClick={() => void refresh()}>Refresh assistance</Button>
      {busy && <p role="status">Reading or saving local assistance history…</p>}
      {invoking && <p role="status">Model request in progress. Refresh to inspect retained state; no automatic retry will follow a failed or uncertain call.</p>}
      {error && <p className="iw-error" role="alert">{error}</p>}
      {registry && <>
        <p>Model: <strong>{registry.configuration.model}</strong>. Local reserved allowance: ${registry.reserved_usd.toFixed(2)} / ${registry.configuration.limits.lifetime_usd.toFixed(2)}.</p>
        {!registry.configuration.available && <p className="iw-notice">Mapping assistance unavailable: {registry.configuration.reason}. Continue with deterministic suggestions or manual mapping.</p>}
        {!registry.source_processing_allowed && <p className="iw-notice">This source has no external-processing permission in server configuration.</p>}
        <p>The sample includes at most {registry.configuration.limits.columns} columns and {registry.configuration.limits.rows} rows; cells clip at {registry.configuration.limits.cell_bytes} bytes with a visible flag. Each call reserves ${registry.configuration.limits.reserve_usd.toFixed(2)}, including uncertain outcomes. This is a conservative local allowance, not invoice-exact billing.</p>
        <div className="np-review">
          <label>Assistance operator<Input value={actor} maxLength={2000} disabled={busy} onChange={event => setActor(event.target.value)} /></label>
          <label>Assistance reason<Input value={reason} maxLength={2000} disabled={busy} onChange={event => setReason(event.target.value)} /></label>
        </div>
        <label className="np-check"><input type="checkbox" checked={permission} disabled={busy} onChange={event => setPermission(event.target.checked)} />Allow this source sample to be sent to OpenAI for this run</label>
        <label className="np-check"><input type="checkbox" checked={includeApprovedExamples} disabled={busy || invoking} onChange={event => setIncludeApprovedExamples(event.target.checked)} />Include reviewed mapping definitions from this source and scope as model examples</label>
        <p className="iw-muted">Optional: send up to three approved definitions (4,000 bytes total). Previous source cells and reviewer names/reasons are excluded. Inspect the exact request before running; model output still requires ordinary recipe review.</p>
        <Button variant="outline" type="button" disabled={busy || invoking || !registry.configuration.available || !registry.source_processing_allowed || !permission || !actor.trim() || !reason.trim()} onClick={() => void act("create")}>Queue model mapping</Button>
        <label className="iw-capture-picker">Retained assistance run<NativeSelect value={run?.id ?? ""} disabled={busy || invoking} onChange={event => void select(event.target.value)}>
          <NativeSelectOption value="">Choose a retained run</NativeSelectOption>
          {registry.items.map(item => <NativeSelectOption key={item.id} value={item.id}>{item.state.replaceAll("_", " ")} · {item.created_at} · {item.id}</NativeSelectOption>)}
        </NativeSelect></label>
        {registry.items.length === 0 && <p>No assistance runs recorded.</p>}
      </>}
      {run && <article aria-label="Selected mapping assistance run">
        <h4>Run <code>{run.id}</code></h4><p>State: <strong>{run.state.replaceAll("_", " ")}</strong> · Revision {run.revision}</p>
        {run.attempt_id !== attemptId && <p className="iw-notice">This run belongs to an older interpretation. Its proposal remains inspectable; create a new run for current data.</p>}
        <div className="np-actions">
          <a download="mapping-run.json" href={`${base}/${encodeURIComponent(run.id)}`}>Run evidence JSON</a>
          <a href={`${base}/${encodeURIComponent(run.id)}/artifacts/request`}>Inspect exact model request</a>
          {run.response_sha && <a href={`${base}/${encodeURIComponent(run.id)}/artifacts/response`}>{run.result.response_truncated ? "Retained response prefix" : "Original model response"}</a>}
        </div>
        {run.result.error && <p className="iw-notice">Run result: {run.result.error}</p>}
        {run.result.explanation && <p>{run.result.explanation}</p>}
        {!!run.result.unresolved?.length && <ul>{run.result.unresolved.map(item => <li key={item.field}>{item.field}: {item.reason}</li>)}</ul>}
        {run.proposal_id && <p>Proposed recipe <code>{run.proposal_id}</code> is available in <strong>Retained recipe proposal</strong> below. Load it, preview its rules and enter a separate approval reviewer and reason.</p>}
        {!terminal && <div className="np-actions">
          <Button variant="outline" type="button" disabled={busy || invoking || run.attempt_id !== attemptId} onClick={() => void act("run-once")}>{run.state === "response_ready" ? "Finish retained model response" : run.state === "running" ? "Recover interrupted run" : "Run queued model mapping"}</Button>
          <Button variant="outline" type="button" disabled={busy || !actor.trim() || !reason.trim()} onClick={() => void act("cancel")}>Cancel mapping run</Button>
        </div>}
      </article>}
    </>}
  </section>;
}
