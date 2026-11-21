import { lazy, Suspense, useEffect, useRef, useState } from "react";
import "./intake.css";
import { EvidenceComparison } from "./EvidenceComparison";
import { navigateWorkspace, useWorkspaceQuery, workspaceHref, useWorkspaceActionGuard } from "./workspaceNavigation";
import type { NativePreview } from "./NativeEvidencePanel";
const NativeEvidencePanel = lazy(() => import("./NativeEvidencePanel").then(module => ({ default: module.NativeEvidencePanel })));
const FhirAcquisitionPanel = lazy(() => import("./FhirAcquisitionPanel").then(module => ({ default: module.FhirAcquisitionPanel })));
import { NormalizationPanel } from "./NormalizationPanel";
import { RecurringImport, type DeliveryComparison } from "./RecurringImport";
import { NetworkSetup, RosterConfiguration, emptyRosterBindings, type RosterBindings } from "./NetworkSetup";
import { NetworkWorkFilters, NetworkCaseScope, FollowUpCaseScopes, matchesWorkScope, type FollowUpScope, type CaseScope, type ReviewEntry } from "./NetworkWork";
import { isOverdueFollowUp } from "./workDates";

type JsonObject = Record<string, unknown>;
type PreviewRow = {
  locator?: string | JsonObject;
  original?: JsonObject;
  normalized?: JsonObject;
  problems?: string[];
};
type Preview = {
  native?: NativePreview;
  recipe_revision_id?: string | null;
  comparison?: DeliveryComparison;
  headers?: string[];
  sheets?: string[];
  sheet?: string;
  mapping?: Record<string, string>;
  rows?: PreviewRow[];
  state?: string;
  error?: string;
  valid_count?: number;
  quarantined_count?: number;
  total?: number;
};
type Attempt = {
  id?: string;
  mapping_revision_id?: string | null;
  spec?: {
    header_row?: number;
    sheet?: string;
    encoding?: string;
    delimiter?: string;
    mapping_revision_id?: string | null;
    roster_kind?: "clinic" | "network";
    bindings?: RosterBindings;
    fixed_network_binding_id?: string | null;
  };
  [key: string]: unknown;
};
type ObservationRecord = {
  id: string;
  provider_id?: string;
  location_id?: string;
  relationship_status?: string;
  identity_status?: string;
  [key: string]: unknown;
};
type Receipt = {
  id: string;
  label?: string;
  source?: string;
  profile?: string;
  designation?: string;
  state?: string;
  received_at?: string;
  duplicate_of?: string;
  artifact_sha?: string;
  metadata?: JsonObject;
  attempt_id?: string;
  preview?: Preview;
  attempts?: Attempt[];
  observations?: ObservationRecord[];
  linked_cases?: JsonObject[];
  source_detail?: unknown;
  is_current_attempt?: boolean;
  latest_attempt_id?: string;
};
type WorkAction =
  | "outreach"
  | "assign"
  | "needs_information"
  | "triage"
  | "approve"
  | "submit"
  | "verify"
  | "defer"
  | "resolve";
type WorkEvent = {
  id?: string | number;
  action?: string;
  event_type?: string;
  reason?: string;
  actor?: string;
  created_at?: string;
  occurred_at?: string;
  [key: string]: unknown;
};
type WorkCase = {
  id: string;
  kind: "qa" | "correction";
  provider_name?: string;
  location_id?: string;
  network_id?: string | null;
  network_label?: string | null;
  organization_id?: string | null;
  organization_label?: string | null;
  practice_location_id?: string | null;
  location_label?: string | null;
  scope?: CaseScope|null;
  follow_up_scopes?: FollowUpScope[];
  participation_review?: ReviewEntry[];
  status: string;
  issue?: string;
  risk_level?: string;
  risk_reason?: string;
  owner?: string;
  follow_up?: string;
  version: number;
  proposal?: string;
  observed?: string;
  evidence?: {
    original?: JsonObject;
    normalized?: JsonObject;
    locator?: unknown;
    listing_value?: unknown;
    reference_value?: unknown;
    receipt_id?: string;
  };
  later_evidence?: unknown[];
  history?: WorkEvent[];
};
type Source = {
  source: string;
  adapter_version?: string;
  scope?: unknown;
  last_success?: string;
  last_failure?: unknown;
};
type Items<T> = { items: T[] };
type DemoSample = { id: string; label: string; description: string };
function allowedActions(item: WorkCase): WorkAction[] {
  const actions: WorkAction[] = ["assign", "needs_information", "outreach"];
  if (
    ["new", "reopened", "deferred", "needs_information"].includes(item.status)
  )
    actions.push("triage");
  if (["new", "triaged", "reopened"].includes(item.status))
    actions.push("defer");
  if (
    item.kind === "qa" &&
    ["new", "triaged", "needs_information"].includes(item.status)
  )
    actions.push("resolve");
  if (item.kind === "correction") {
    if (item.status === "triaged") actions.push("approve");
    if (item.status === "approved") actions.push("submit");
    if (item.status === "pending_verification") actions.push("verify");
  }
  return actions;
}
export type IntakePage = "intake" | "work" | "sources";
async function request<T = Receipt>(
  path: string,
  body?: unknown,
  file?: File,
): Promise<T> {
  const response = await fetch(
    `/api${path}`,
    file
      ? {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          body: file,
        }
      : body === undefined
        ? undefined
        : {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
  );
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const error = await response.json();
      message =
        typeof error.detail === "string"
          ? error.detail
          : JSON.stringify(error.detail);
    } catch {
      /* preserve HTTP status */
    }
    throw new Error(message);
  }
  return response.json();
}
const pretty = (value: unknown) => String(value ?? "—").replaceAll("_", " ");
function Json({ value }: { value: unknown }) {
  return <pre className="iw-json">{JSON.stringify(value ?? {}, null, 2)}</pre>;
}
function ErrorMessage({ error, retry }: { error: string; retry?: () => void }) {
  return error ? (
    <div className="iw-error" role="alert">
      <p>{error}</p>
      {retry && <button onClick={retry}>Retry / refresh</button>}
    </div>
  ) : null;
}
function useResource<T>(path: string) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const currentPath = useRef(path);
  const sequence = useRef(0);
  if (currentPath.current !== path) {
    currentPath.current = path;
    sequence.current += 1;
  }
  const refresh = async () => {
    const requestId = ++sequence.current;
    setLoading(true);
    setError("");
    try {
      const value = await request<T>(path);
      if (requestId === sequence.current) setData(value);
    } catch (e) {
      if (requestId === sequence.current) setError((e as Error).message);
    } finally {
      if (requestId === sequence.current) setLoading(false);
    }
  };
  useEffect(() => {
    setData(null);
    void refresh();
    return () => { sequence.current += 1; };
  }, [path]);
  return { data, error, loading, refresh };
}

export function IntakeWorkbench({ page }: { page: IntakePage }) {
  return (
    <main className="iw-shell">
      <header className="iw-heading">
        <p className="iw-eyebrow">Provider data operations</p>
        <h1>
          {page === "intake"
            ? "Receive provider data"
            : page === "work"
              ? "Provider work queue"
              : "Sources and capture history"}
        </h1>
        <p>
          {page === "intake"
            ? "Receive a file, select its supported profile, then review mappings and quality findings before accepting rows."
            : page === "work"
              ? "Choose a clinician and office, inspect the discrepancy, and record the next decision or follow-up."
              : "Inspect reference-source captures, retained responses and their declared coverage."}
        </p>
      </header>
      {page === "intake" ? (
        <IntakeInbox />
      ) : page === "work" ? (
        <WorkQueue />
      ) : (
        <Sources />
      )}
    </main>
  );
}
function IntakeInbox() {
  const actionGuard = useWorkspaceActionGuard();
  const receipts = useResource<Items<Receipt>>("/intakes");
  const samples = useResource<Items<DemoSample>>("/demo/samples");
  const [sampleId, setSampleId] = useState("clinic-workbook");
  const query = useWorkspaceQuery();
  const selected = query.get("receipt") ?? "";
  const pinnedAttempt = query.get("attempt") ?? "";
  const setSelected = (id: string) => navigateWorkspace("intake", { receipt: id });
  const [source, setSource] = useState("clinic"),
    [designation, setDesignation] = useState("synthetic"),
    [profile, setProfile] = useState("flat"),
    [datasetScope, setDatasetScope] = useState(""),
    [completeness, setCompleteness] = useState("unknown"),
    [asOf, setAsOf] = useState("");
  const [error, setError] = useState(""),
    [networkSetupNotice, setNetworkSetupNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [file, setFile] = useState<File | null>(null);
  const [lookup, setLookup] = useState({
    source: "nppes",
    number: "",
    city: "",
    state: "",
    limit: "10",
  });
  const [link, setLink] = useState({
    url: "",
    title: "",
    source: "clinic",
    observed_at: "",
  });
  const run = async (fn: () => Promise<Receipt>) => {
    const origin = actionGuard.capture();
    setBusy(true);
    setError("");
    try {
      const result = await fn();
      if (!actionGuard.isCurrent(origin)) return;
      setSelected(String(result.id));
      await receipts.refresh();
    } catch (e) {
      if (actionGuard.isCurrent(origin)) setError((e as Error).message);
    } finally {
      if (actionGuard.isCurrent(origin)) setBusy(false);
    }
  };
  useEffect(() => {
    setBusy(false);
    if (selected)
      document.getElementById("intake-receipt-detail")?.scrollIntoView?.({ block: "start" });
  }, [selected]);
  const selectedSample = samples.data?.items?.find((sample) => sample.id === sampleId);
  const prepareNetwork = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await request<{notice:string}>("/demo/network-setup", {});
      setNetworkSetupNotice(result.notice);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      {(samples.data?.items?.length ?? 0) > 0 && (
        <section className="iw-card iw-demo" aria-labelledby="synthetic-demo-title">
          <div className="iw-title">
            <div>
              <p className="iw-eyebrow">Synthetic demonstration · Offline</p>
              <h2 id="synthetic-demo-title">Start with a clinic roster</h2>
              <p>
                One clinician, two practice locations, and different requested phone
                corrections. Review a messy delivery before deciding what to accept.
              </p>
            </div>
          </div>
          <form className="iw-form" onSubmit={(e) => {
            e.preventDefault();
            void run(() => request(`/demo/samples/${encodeURIComponent(sampleId)}`, {}));
          }}>
            <label>
              Synthetic sample
              <select value={sampleId} onChange={(e) => setSampleId(e.target.value)}>
                {samples.data?.items.map((sample) => (
                  <option key={sample.id} value={sample.id}>{sample.label}</option>
                ))}
              </select>
            </label>
            <button className="iw-primary" disabled={busy || !selectedSample}>
              {busy ? "Receiving…" : "Load synthetic sample"}
            </button>
          </form>
          <p className="iw-muted">{selectedSample?.description}</p>
          <div className="iw-suggestion">
            <button type="button" disabled={busy} onClick={() => void prepareNetwork()}>
              Prepare synthetic network catalog
            </button>
            <p className="iw-muted">For the network samples, prepare CEDAR/PINE and NORTH/SOUTH source-code bindings first. This only creates reviewed synthetic catalog records. Loading and accepting deliveries remain separate steps.</p>
            {networkSetupNotice && <p className="iw-notice" role="status">{networkSetupNotice}</p>}
          </div>
          <p className="iw-muted">
            Next: review the columns, inspect quarantine, then explicitly accept valid
            rows. Clinic samples share <strong>synthetic-demo</strong>; reference and network samples have separate synthetic source namespaces. To try reconciliation, load the clinic workbook and the synthetic NPPES response, then choose both sources in Reconcile. Loading a sample never accepts or verifies it.
          </p>
        </section>
      )}
      <NetworkSetup source={source} />
      <ErrorMessage error={error} />
      <section className="iw-card">
        <div className="iw-title">
          <div>
            <h2>Receive source evidence</h2>
            <p>
              A delivery keeps its original bytes, source label, and
              interpretation history.
            </p>
          </div>
          <span className="iw-badge">CSV · XLSX · JSON</span>
        </div>
        <form
          className="iw-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (file)
              void run(() =>
                request(
                  `/intakes/files?${new URLSearchParams({
                    filename: file.name, source, designation, profile,
                    ...(datasetScope.trim() ? {dataset_scope:datasetScope.trim()} : {}),
                    completeness,
                    ...(asOf ? {as_of:asOf} : {}),
                  })}`,
                  undefined,
                  file,
                ),
              );
          }}
        >
          <label>
            Source namespace
            <input
              required
              value={source}
              onChange={(e) => setSource(e.target.value)}
            />
          </label>
          <label>
            Evidence designation
            <select
              value={designation}
              onChange={(e) => setDesignation(e.target.value)}
            >
              <option value="synthetic">Synthetic demonstration</option>
              <option value="public">Public source</option>
              <option value="local">Local supplied evidence</option>
            </select>
          </label>
          <label>
            Response profile
            <select
              value={profile}
              onChange={(e) => { setProfile(e.target.value); if (e.target.value === "fhir-plannet-r4") setCompleteness("unknown"); }}
            >
              <option value="flat">Flat CSV / workbook / JSON</option>
              <option value="nppes">NPPES API response</option>
              <option value="cms">CMS clinician response</option>
              <option value="fhir-plannet-r4">Saved FHIR / Plan-Net searchset</option>
            </select>
          </label>
          <details className="iw-file">
            <summary>Delivery scope and source date (optional)</summary>
            <p className="iw-muted">These describe the supplied dataset. A reported date is not a verification date or a provider identity.</p>
            <label>Dataset scope
              <input value={datasetScope} onChange={(e) => setDatasetScope(e.target.value)} placeholder="Exact source-defined scope" />
            </label>
            <label>Completeness
              <select value={completeness} onChange={(e) => setCompleteness(e.target.value)}>
                <option value="unknown">Unknown</option><option value="bounded">Bounded extract</option><option value="full" disabled={profile === "fhir-plannet-r4"}>Source-declared full scope</option>
              </select>
            </label>
            <label>Source as-of date
              <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
            </label>
          </details>
          <label className="iw-file">
            Source file
            <input
              required
              type="file"
              accept=".csv,.xlsx,.json"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <button className="iw-primary" disabled={busy || !file}>
            {busy ? "Receiving…" : "Upload and preview"}
          </button>
        </form>
        <div className="iw-two">
          <details>
            <summary>Look up a public reference</summary>
            <p>
              Bounded query. Unavailable endpoints are recorded as failed
              attempts. Results require human review.
            </p>
            <form
              className="iw-form"
              onSubmit={(e) => {
                e.preventDefault();
                void run(() =>
                  request("/intakes/lookups", {
                    source: lookup.source,
                    query: Object.fromEntries(
                      Object.entries(
                        lookup.source === "cms"
                          ? {
                              npi: lookup.number,
                              state: lookup.state,
                              limit: Number(lookup.limit),
                            }
                          : {
                              number: lookup.number,
                              city: lookup.city,
                              state: lookup.state,
                              limit: Number(lookup.limit),
                            },
                      ).filter(([, value]) => value !== ""),
                    ),
                  }),
                );
              }}
            >
              <label>
                Reference
                <select
                  value={lookup.source}
                  onChange={(e) =>
                    setLookup({ ...lookup, source: e.target.value })
                  }
                >
                  <option value="nppes">NPPES</option>
                  <option value="cms">CMS Doctors and Clinicians</option>
                </select>
              </label>
              {(["number", "city", "state", "limit"] as const)
                .filter((key) => lookup.source !== "cms" || key !== "city")
                .map((key) => (
                  <label key={key}>
                    {key === "number" ? "NPI (optional)" : pretty(key)}
                    <input
                      value={lookup[key]}
                      onChange={(e) =>
                        setLookup({ ...lookup, [key]: e.target.value })
                      }
                    />
                  </label>
                ))}
              <button disabled={busy}>Fetch reference</button>
            </form>
          </details>
          <details>
            <summary>Retain an asserted source link</summary>
            <p>
              A link is an assertion only. This action does not fetch its
              contents or establish verification.
            </p>
            <form
              className="iw-form"
              onSubmit={(e) => {
                e.preventDefault();
                void run(() => request("/intakes/links", link));
              }}
            >
              {(["url", "title", "source", "observed_at"] as const).map(
                (key) => (
                  <label key={key}>
                    {pretty(key)}
                    <input
                      required={key !== "observed_at"}
                      type={key === "url" ? "url" : "text"}
                      value={link[key]}
                      onChange={(e) =>
                        setLink({ ...link, [key]: e.target.value })
                      }
                      placeholder={
                        key === "observed_at" ? "YYYY-MM-DD (optional)" : ""
                      }
                    />
                  </label>
                ),
              )}
              <button disabled={busy}>Save asserted link</button>
            </form>
          </details>
        </div>
      </section>
      <section className="iw-split">
        <div className="iw-card iw-inbox">
          <div className="iw-title">
            <h2>Intake inbox</h2>
            <button onClick={() => void receipts.refresh()}>Refresh</button>
          </div>
          <ErrorMessage error={receipts.error} retry={receipts.refresh} />
          {receipts.loading && <p role="status">Loading receipts…</p>}
          {receipts.data?.items?.length === 0 && (
            <p className="iw-empty">
              No deliveries yet. Upload a file to begin.
            </p>
          )}
          <ul className="iw-list">
            {receipts.data?.items?.map((item: Receipt) => (
              <li key={item.id}>
                <button
                  aria-pressed={selected === item.id}
                  onClick={() => setSelected(item.id)}
                >
                  <strong>{item.label || item.id}</strong>
                  <span>
                    {item.source} · {pretty(item.state)}
                  </span>
                  <small>
                    {item.received_at} · {item.designation}
                    {item.duplicate_of ? " · Repeat delivery" : ""}
                  </small>
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="iw-card" id="intake-receipt-detail">
          {selected ? (
            <ReceiptDetail
              key={`${selected}:${pinnedAttempt}`}
              id={selected}
              pinnedAttempt={pinnedAttempt}
              changed={receipts.refresh}
            />
          ) : (
            <div className="iw-empty">
              <h2>Select a delivery</h2>
              <p>
                Inspect the original, map fields, and make an explicit
                acceptance decision.
              </p>
            </div>
          )}
        </div>
      </section>
    </>
  );
}
const fields = [
  "npi",
  "provider_name",
  "address",
  "city",
  "state",
  "zip",
  "phone",
  "suite",
  "address_line2",
  "record_id",
  "location_id",
  "listing_id",
  "reference_phone",
  "network_code",
  "organization_code",
  "network_label",
  "organization_label",
  "participation_status",
  "effective_date",
  "end_date",
];
function ReceiptDetail({
  id,
  changed,
  pinnedAttempt = "",
}: {
  id: string;
  pinnedAttempt?: string;
  changed: () => Promise<void>;
}) {
  const resource = useResource<Receipt>(`/intakes/${encodeURIComponent(id)}${pinnedAttempt ? `?${new URLSearchParams({ attempt_id: pinnedAttempt })}` : ""}`);
  const detail = resource.data;
  const [mapping, setMapping] = useState<Record<string, string>>({}),
    [sheet, setSheet] = useState(""),
    [header, setHeader] = useState("1"),
    [encoding, setEncoding] = useState("utf-8-sig"),
    [delimiter, setDelimiter] = useState(",");
  const [rosterKind,setRosterKind] = useState<"clinic"|"network">("clinic"),
    [rosterBindings,setRosterBindings] = useState<RosterBindings>(emptyRosterBindings),
    [fixedNetworkBindingId,setFixedNetworkBindingId] = useState("");
  const [actor, setActor] = useState(""),
    [reason, setReason] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (detail?.preview) {
      setMapping(detail.preview.mapping ?? {});
      const spec = detail.attempts?.at(-1)?.spec;
      setSheet(spec?.sheet ?? detail.preview.sheet ?? "");
      setHeader(String(spec?.header_row ?? 1));
      setEncoding(spec?.encoding ?? "utf-8-sig");
      setDelimiter(spec?.delimiter ?? ",");
      setRosterKind(spec?.roster_kind ?? "clinic");
      setRosterBindings(spec?.bindings ?? emptyRosterBindings());
      setFixedNetworkBindingId(spec?.fixed_network_binding_id ?? "");
    }
  }, [detail]);
  const run = async (path: string, body: unknown) => {
    setBusy(true);
    setError("");
    try {
      const requestBody = path === "mapping" && body && typeof body === "object" && !("mapping_revision_id" in body) && rosterKind === "network"
        ? {...body,roster_kind:"network",bindings:rosterBindings,...(fixedNetworkBindingId ? {fixed_network_binding_id:fixedNetworkBindingId} : {})}
        : body;
      await request(`/intakes/${id}/${path}`, requestBody);
      await resource.refresh();
      await changed();
    } catch (e) {
      const message = (e as Error).message;
      setError(path === "commit" && /baseline|stale/i.test(message)
        ? `${message} Refresh comparison and review the updated changes before accepting. Your reviewer and reason are preserved.`
        : message);
    } finally {
      setBusy(false);
    }
  };
  if (!detail)
    return (
      <>
        <ErrorMessage error={resource.error} retry={resource.refresh} />
        {resource.loading && <p role="status">Loading delivery evidence…</p>}
      </>
    );
  if (detail.profile === "fhir-plannet-r4") return <Suspense fallback={<p role="status">Loading native evidence review…</p>}><NativeEvidencePanel
    key={`${id}:${pinnedAttempt}`} receipt={detail} readOnly={Boolean(pinnedAttempt)} loadError={resource.error}
    refresh={async () => { await resource.refresh(); await changed(); }}
  /></Suspense>;
  if (pinnedAttempt) return <section aria-label="Pinned delivery evidence">
    <p className="iw-eyebrow">Retained interpretation / Read only</p>
    <h2>{detail.label}</h2>
    <p>Receipt <code>{id}</code> · Attempt <code>{detail.attempt_id}</code></p>
    <p>{pretty(detail.state)}. This view keeps the selected interpretation; opening it does not reprocess or accept records.</p>
    {detail.is_current_attempt === false && <p role="status" className="iw-notice">A newer interpretation exists. The selected evidence remains pinned.</p>}
    <div className="iw-links">
      <a href={workspaceHref("intake", { receipt: id })}>Open current receipt workspace</a>
      {detail.artifact_sha && <a href={`/api/intakes/${encodeURIComponent(id)}/artifact`}>Download original artifact</a>}
    </div>
    <details open><summary>Selected interpretation and source rows</summary><pre className="iw-json">{JSON.stringify({ preview: detail.preview, observations: detail.observations }, null, 2)}</pre></details>
    <h3>Linked work</h3>
    {detail.linked_cases?.length ? detail.linked_cases.map(item => <p key={String(item.id)}><a href={workspaceHref("work", { case: String(item.id) })}>Open case {String(item.id)}</a></p>) : <p>No linked work for this interpretation.</p>}
  </section>;
  const preview = detail.preview;
  const acceptsEmptyFullNetwork = detail.state === "preview_ready"
    && detail.attempts?.at(-1)?.spec?.roster_kind === "network"
    && detail.metadata?.completeness === "full"
    && preview?.total === 0
    && Boolean(preview?.comparison?.baseline);
  const suggestedMapping = detail.metadata?.suggested_mapping;
  const hasSuggestedMapping = suggestedMapping !== null && typeof suggestedMapping === "object";
  const suggestedNetworkSettings = detail.metadata?.suggested_network_settings;
  const hasSuggestedNetworkSettings = suggestedNetworkSettings !== null && typeof suggestedNetworkSettings === "object";
  const isNetworkSample = String(detail.metadata?.demo_sample ?? "").startsWith("network-");
  const isReferenceSample = ["nppes", "cms"].includes(String(detail.metadata?.demo_sample));
  return (
    <>
      <p className="iw-eyebrow">Delivery {id}</p>
      <h2>{detail.label}</h2>
      <div className="iw-pills">
        <span>{pretty(detail.state)}</span>
        <span>{detail.source}</span>
        <span>{detail.designation}</span>
      </div>
      <section className="iw-import-context" aria-label="Import review progress">
        <ol className="iw-stages">
          <li>1. Evidence received</li>
          <li aria-current={detail.state === "needs_mapping" ? "step" : undefined}>2. Map and inspect</li>
          <li aria-current={detail.state === "preview_ready" ? "step" : undefined}>3. Review acceptance</li>
          <li aria-current={["committed", "duplicate_delivery"].includes(detail.state ?? "") ? "step" : undefined}>4. Accepted evidence</li>
        </ol>
        {preview && <dl className="iw-quality-counts">
          <div><dt>Source rows</dt><dd>{preview.total ?? "Unknown"}</dd></div>
          <div><dt>Valid rows</dt><dd>{preview.valid_count ?? "Unknown"}</dd></div>
          <div><dt>Quarantined</dt><dd>{preview.quarantined_count ?? "Unknown"}</dd></div>
        </dl>}
        <p>{detail.state === "needs_mapping"
          ? "Next: review column mapping and parsing, then reprocess this retained file."
          : detail.state === "preview_ready"
            ? "Next: inspect original and interpreted values, resolve mapping concerns, then explicitly accept valid rows or reject this intake."
            : ["committed", "duplicate_delivery"].includes(detail.state ?? "")
              ? "Next: inspect source observations and linked work. Intake acceptance does not approve a dataset or verify a listing."
              : "Review the delivery state and retained evidence below before making a decision."}</p>
        {detail.attempt_id && <details><summary>Current interpretation identity</summary><code>{detail.attempt_id}</code></details>}
      </section>
      {Boolean(detail.metadata?.demo_sample) && (
        <aside className="iw-notice" aria-label="Synthetic sample next step">
          <strong>Synthetic example — no real clinicians or payer updates.</strong>
          <p>
            {isNetworkSample
              ? ["committed", "duplicate_delivery"].includes(detail.state ?? "")
                ? "Next: inspect the source-listed network scope and comparison QA work. Filter by network and location, assign follow-up and download scoped evidence. Later rows never verify human work or terminate participation."
                : String(detail.metadata?.demo_notice ?? (hasSuggestedNetworkSettings
                  ? "Review the suggested network bindings, save mapping and reprocess, then save a named mapping revision before explicit acceptance."
                  : "Prepare the synthetic network catalog above, then load this sample again to review its source bindings. No catalog is created by loading a file."))
              : ["committed", "duplicate_delivery"].includes(detail.state ?? "")
              ? isReferenceSample
                ? "Next: inspect the native source observations below. A provider identity does not select a practice location; any location relationship needs an explicit evidence-supported choice. This saved-response fixture is synthetic, not a live public lookup or human verification."
                : "Next: open a linked case below. Compare NORTH and SOUTH, assign an owner, and record triage, approval, simulated submission and an observed result. Download the case XLSX to hand off the evidence and decisions."
              : detail.state === "rejected"
                ? "This delivery was rejected. Its original and decision remain inspectable. Save a new mapping attempt to reprocess it before making another acceptance decision."
              : detail.state === "needs_mapping"
                ? "Next: use the suggested columns, review each editable mapping, then save mapping and reprocess. Header row 2 skips the workbook title. Check the malformed row before accepting anything."
                : "Next: compare original and normalized evidence, inspect any quarantined rows, and enter a reviewer and reason to accept valid rows. Later evidence and repeat deliveries never verify cases automatically."}
          </p>
        </aside>
      )}
      {detail.duplicate_of && (
        <p className="iw-notice">
          Repeat delivery of {detail.duplicate_of}. A receipt remains visible
          even when the artifact is reused.
        </p>
      )}
      {detail.artifact_sha && detail.attempt_id && <NormalizationPanel
        receiptId={id} attemptId={detail.attempt_id} currentMapping={detail.preview?.mapping}
        appliedRecipeId={detail.preview?.recipe_revision_id}
        accepted={["committed", "duplicate_delivery"].includes(detail.state ?? "")}
        supported={(detail.profile ?? "flat") === "flat" && detail.attempts?.at(-1)?.spec?.roster_kind !== "network"}
        onChanged={async () => { await resource.refresh(); await changed(); }}
      />}
      <div className="iw-links">
        {detail.artifact_sha && (
          <>
            <a href={`/api/intakes/${id}/artifact`}>Download original</a>
            <a href={`/api/intakes/${id}/quarantine`}>Quarantined rows CSV</a>
          </>
        )}
        <a href={`/api/intakes/${id}/packet`}>Evidence packet JSON</a>
      </div>
      {detail.state === "reference_only" && (
        <p className="iw-notice">
          Asserted link only: contents were not fetched and no original artifact
          was retained. <span>{String(detail.metadata?.url ?? "")}</span>
        </p>
      )}
      <ErrorMessage error={error || resource.error} retry={resource.refresh} />
      {preview && (
        <>
          <h3>Interpretation preview</h3>
          <RecurringImport
            receiptId={id}
            state={detail.state ?? ""}
            attemptId={detail.attempt_id ?? ""}
            appliedRevisionId={detail.attempts?.at(-1)?.spec?.mapping_revision_id ?? detail.attempts?.at(-1)?.mapping_revision_id ?? null}
            comparison={preview.comparison}
            effectiveMapping={preview.mapping ?? {}}
            parsing={{
              sheet: detail.attempts?.at(-1)?.spec?.sheet ?? preview.sheet ?? "",
              header_row: detail.attempts?.at(-1)?.spec?.header_row ?? 1,
              encoding: detail.attempts?.at(-1)?.spec?.encoding ?? "utf-8-sig",
              delimiter: detail.attempts?.at(-1)?.spec?.delimiter ?? ",",
            }}
            busy={busy}
            onRun={run}
            onChanged={async () => { await resource.refresh(); await changed(); }}
          />
          {preview.error && (
            <p className="iw-error" role="alert">
              {preview.error}
            </p>
          )}
          <p>
            {preview.valid_count ?? 0} valid · {preview.quarantined_count ?? 0}{" "}
            quarantined · {preview.total ?? 0} total
          </p>
          {hasSuggestedNetworkSettings && <div className="iw-suggestion">
            <button type="button" disabled={busy} onClick={() => {
              const settings = suggestedNetworkSettings as {bindings?:RosterBindings;fixed_network_binding_id?:string|null};
              setRosterKind("network");
              setRosterBindings(settings.bindings ?? emptyRosterBindings());
              setFixedNetworkBindingId(settings.fixed_network_binding_id ?? "");
            }}>Use suggested network scope</button>
            <p className="iw-muted">Fills this form only. Open Column mapping and parsing to review exact bindings, then save mapping and reprocess. Saving a named revision and accepting valid rows are separate decisions.</p>
          </div>}
          <details
            open={["needs_mapping", "failed", "interrupted"].includes(
              preview.state ?? "",
            )}
          >
            <summary>Column mapping and parsing</summary>
            <RosterConfiguration
              source={detail.source ?? ""}
              kind={rosterKind}
              bindings={rosterBindings}
              fixedNetworkBindingId={fixedNetworkBindingId}
              busy={busy}
              onKind={setRosterKind}
              onBindings={setRosterBindings}
              onFixedNetworkBindingId={setFixedNetworkBindingId}
            />
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void run("mapping", {
                  mapping: Object.fromEntries(
                    Object.entries(mapping).filter(([, column]) => column),
                  ),
                  sheet,
                  header_row: Number(header),
                  encoding,
                  delimiter,
                });
              }}
            >
              <div className="iw-form">
                <label>
                  Sheet name (blank uses first)
                  <input
                    list="intake-sheets"
                    value={sheet}
                    onChange={(e) => {
                      setSheet(e.target.value);
                      setMapping({});
                    }}
                    placeholder="First worksheet"
                  />
                  <datalist id="intake-sheets">
                    {preview.sheets?.map((s) => (
                      <option key={s} value={s} />
                    ))}
                  </datalist>
                </label>
                <label>
                  Header row
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={header}
                    onChange={(e) => {
                      setHeader(e.target.value);
                      setMapping({});
                    }}
                  />
                </label>
                <label>
                  Encoding
                  <input
                    value={encoding}
                    onChange={(e) => setEncoding(e.target.value)}
                  />
                </label>
                <label>
                  Delimiter
                  <input
                    value={delimiter}
                    onChange={(e) => setDelimiter(e.target.value)}
                  />
                </label>
              </div>
              <p className="iw-muted">
                For a title row or failed workbook header, choose the correct
                header row and save to detect columns again. Then map the newly
                detected headers.
              </p>
              {hasSuggestedMapping && (
                <div className="iw-suggestion">
                  <button type="button" disabled={busy} onClick={() => {
                    setMapping(Object.fromEntries(
                      Object.entries(suggestedMapping).filter((entry): entry is [string, string] => typeof entry[1] === "string"),
                    ));
                  }}>Use suggested columns</button>
                  <p className="iw-muted">
                    Fills this form only. Review the columns and save mapping to
                    validate; acceptance remains a separate decision.
                  </p>
                </div>
              )}
              <div className="iw-mapping">
                {fields.map((field) => (
                  <label key={field}>
                    {pretty(field)}
                    {fields.indexOf(field) < 7 ? " *" : " (optional)"}
                    <select
                      value={mapping[field] ?? ""}
                      onChange={(e) =>
                        setMapping({ ...mapping, [field]: e.target.value })
                      }
                    >
                      <option value="">Unmapped</option>
                      {preview.headers?.map((h: string) => (
                        <option key={h}>{h}</option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              <button disabled={busy}>Save mapping and reprocess</button>
            </form>
          </details>
          <div className="iw-preview">
            {preview.rows?.slice(0, 8).map((row: PreviewRow, i: number) => (
              <details key={i}>
                <summary>
                  {typeof row.locator === "object"
                    ? JSON.stringify(row.locator)
                    : row.locator || `Row ${i + 1}`}{" "}
                  · {row.problems?.length ? "Quarantined" : "Valid"}
                </summary>
                {(row.problems?.length ?? 0) > 0 && (
                  <Json value={row.problems} />
                )}
                <EvidenceComparison original={row.original} interpreted={row.normalized} mapping={preview.mapping} />
              </details>
            ))}
          </div>
          <form
            className="iw-form iw-decision"
            onSubmit={(e) => {
              e.preventDefault();
              void run("commit", {
                policy: "valid_rows",
                actor,
                reason,
                expected_attempt: detail.attempt_id,
              });
            }}
          >
            <label>
              Reviewer
              <input
                required
                value={actor}
                onChange={(e) => setActor(e.target.value)}
              />
            </label>
            <label>
              Acceptance / rejection reason
              <input
                required
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            <button
              className="iw-primary"
              disabled={
                busy ||
                !actor ||
                !reason ||
                detail.state !== "preview_ready" ||
                (!preview.valid_count && !acceptsEmptyFullNetwork)
              }
            >
              {acceptsEmptyFullNetwork ? "Accept empty snapshot as absence evidence" : "Accept valid rows"}
            </button>
            <button
              type="button"
              disabled={busy || !actor || !reason}
              onClick={() =>
                void run("commit", {
                  policy: "reject",
                  actor,
                  reason,
                  expected_attempt: detail.attempt_id,
                })
              }
            >
              Reject intake
            </button>
          </form>
          <p className="iw-muted">
            Interactive evidence samples show up to 50 observations; the packet
            contains the full history. Acceptance is explicit. Quarantined rows
            remain evidence and do not silently enter the directory.
          </p>
        </>
      )}
      {(detail.observations?.length ?? 0) > 0 && (
        <section>
          <h3>Source observations and relationships</h3>
          {detail.observations?.map((observation: ObservationRecord) => (
            <Observation
              key={observation.id}
              observation={observation}
              refresh={resource.refresh}
            />
          ))}
        </section>
      )}
      {(detail.linked_cases?.length ?? 0) > 0 && (
        <section>
          <h3>Linked cases</h3>
          <ul className="iw-list">
            {detail.linked_cases?.map((item) => (
              <li key={String(item.id)}>
                <a href={`?view=work&case=${item.id}`}>
                  {String(item.issue)} · {String(item.status)} ·{" "}
                  {String(item.location_id ?? "Unresolved location")}
                </a>
              </li>
            ))}
          </ul>
          <a href="?view=work">Open durable work queue →</a>
        </section>
      )}
      <details>
        <summary>Attempt history and source detail</summary>
        <Json value={detail.attempts} />
        <Json
          value={
            detail.source_detail ?? {
              source: detail.source,
              received_at: detail.received_at,
              artifact_sha: detail.artifact_sha,
              metadata: detail.metadata,
              duplicate_of: detail.duplicate_of,
            }
          }
        />
      </details>
    </>
  );
}
function Observation({
  observation,
  refresh,
}: {
  observation: ObservationRecord;
  refresh: () => Promise<void>;
}) {
  const [nativeIndex, setNativeIndex] = useState("");
  const nativeLocations =
    (observation.normalized as { locations?: JsonObject[] })?.locations ?? [];
  const [provider, setProvider] = useState(""),
    [location, setLocation] = useState(""),
    [actor, setActor] = useState(""),
    [reason, setReason] = useState(""),
    [error, setError] = useState("");
  return (
    <details>
      <summary>
        {observation.id} ·{" "}
        {observation.relationship_status ??
          observation.identity_status ??
          (observation.provider_id && observation.location_id
            ? "Provider and location linked"
            : "Unresolved relationship")}
      </summary>
      <Json value={observation} />
      <form
        className="iw-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setError("");
          try {
            await request("/relationships", {
              observation_id: observation.id,
              provider_id: provider,
              location_id: location,
              actor,
              reason,
              ...(nativeIndex !== ""
                ? { location_index: Number(nativeIndex) }
                : {}),
            });
            await refresh();
          } catch (failure) {
            setError((failure as Error).message);
          }
        }}
      >
        <p>
          Choose an evidence-supported provider and a separate local location. A
          row number is not an identity.
        </p>
        {nativeLocations.length > 0 && (
          <label>
            Native source location
            <select
              value={nativeIndex}
              required={nativeLocations.length > 1}
              onChange={(e) => setNativeIndex(e.target.value)}
            >
              <option value="">Choose source location</option>
              {nativeLocations.map((loc, index) => (
                <option key={index} value={index}>
                  {index}: {String(loc.address)} ·{" "}
                  {String(loc.purpose ?? "practice")}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Provider identity
          <input
            required
            placeholder="NPI:1234567890 (exact NPI only)"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
          />
        </label>
        <label>
          Local location identity
          <input
            required
            value={location}
            onChange={(e) => setLocation(e.target.value)}
          />
        </label>
        <label>
          Reviewer
          <input
            required
            value={actor}
            onChange={(e) => setActor(e.target.value)}
          />
        </label>
        <label>
          Relationship evidence / reason
          <input
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </label>
        <button>Link observation explicitly</button>
      </form>
      <ErrorMessage error={error} />
    </details>
  );
}
function WorkQueue() {
  const resource = useResource<Items<WorkCase>>("/work");
  const params = useWorkspaceQuery();
  const selected = params.get("case") ?? "";
  const setSelected = (id: string) => navigateWorkspace("work", { ...Object.fromEntries(params), case: id });
  const filters = {
    search: params.get("search") ?? "",
    owner: params.get("owner") ?? "",
    status: params.get("status") ?? "",
    overdue: params.get("overdue") === "1",
    awaiting: params.get("awaiting") === "1",
    unassigned: params.get("unassigned") === "1",
    needs_information: params.get("needs_information") === "1",
    network_id: params.get("network_id") ?? "",
    organization_id: params.get("organization_id") ?? "",
    location_id: params.get("location_id") ?? "",
  };
  const update = (next: typeof filters) => {
    const query = new URLSearchParams(location.search);
    for (const [key, value] of Object.entries(next)) {
      if (value) query.set(key, typeof value === "boolean" ? "1" : value);
      else query.delete(key);
    }
    query.delete("view");
    navigateWorkspace("work", Object.fromEntries(query), true);
  };
  const items = (resource.data?.items ?? []).filter(
    (item: WorkCase) =>
      (!filters.search ||
        JSON.stringify(item)
          .toLowerCase()
          .includes(filters.search.toLowerCase())) &&
      (!filters.owner ||
        String(item.owner ?? "")
          .toLowerCase()
          .includes(filters.owner.toLowerCase())) &&
      (!filters.status || item.status === filters.status) &&
      matchesWorkScope(item,{networkId:filters.network_id,organizationId:filters.organization_id,locationId:filters.location_id}) &&
      (!filters.overdue || isOverdueFollowUp(item.follow_up, item.status)) &&
      (!filters.awaiting ||
        ["submitted", "awaiting_verification", "pending_verification"].includes(
          item.status,
        )) &&
      (!filters.unassigned || !item.owner?.trim()) &&
      (!filters.needs_information || item.status === "needs_information"),
  );
  useEffect(() => {
    if (resource.data && selected && (filters.network_id || filters.organization_id || filters.location_id)
      && !items.some((item) => item.id === selected)) setSelected("");
  }, [resource.data, filters, selected]);
  return (
    <>
      {params.get("proposal") && <aside className="iw-card" aria-label="Follow-up context"><p>This case is part of the selected change follow-up.</p><a href={workspaceHref("reconciliation", Object.fromEntries([...params].filter(([key]) => ["feed", "version", "receipt", "attempt", "run", "clinician", "location", "proposal", "followup", "candidate_kind", "eligibility", "evidence_reason", "candidate_search"].includes(key))))}>Return to change assessment and follow-up receipt</a></aside>}
      <section className="iw-card">
        <div className="iw-title">
          <div>
            <h2>Find work to review</h2>
            <p>
              Showing up to 200 matching items; search to narrow large
              queues.{" "}
            </p>
            <p>
              QA disposition and correction verification are separate decisions.
            </p>
            <div className="iw-links">
              <a href="/api/work-export.xlsx" download>Download all work XLSX</a>
            </div>
            <p>Includes every durable case, evidence row and decision; ignores the filters below.</p>
          </div>
          <button onClick={() => void resource.refresh()}>Refresh</button>
        </div>
        <div className="iw-form">
          <label>
            Search work
            <input
              value={filters.search}
              onChange={(e) => update({ ...filters, search: e.target.value })}
            />
          </label>
          <label>
            Owner filter
            <input
              value={filters.owner}
              onChange={(e) => update({ ...filters, owner: e.target.value })}
            />
          </label>
          <label>
            Status filter
            <select
              value={filters.status}
              onChange={(e) => update({ ...filters, status: e.target.value })}
            >
              <option value="">All statuses</option>
              {Array.from(
                new Set(
                  (resource.data?.items ?? []).map((i: WorkCase) =>
                    String(i.status),
                  ),
                ),
              ).map((status) => (
                <option key={String(status)}>{String(status)}</option>
              ))}
            </select>
          </label>
          <label className="iw-check">
            <input
              type="checkbox"
              checked={filters.overdue}
              onChange={(e) =>
                update({ ...filters, overdue: e.target.checked })
              }
            />
            Overdue follow-up
          </label>
          <label className="iw-check">
            <input
              type="checkbox"
              checked={filters.awaiting}
              onChange={(e) =>
                update({ ...filters, awaiting: e.target.checked })
              }
            />
            Awaiting verification
          </label>
          <label className="iw-check">
            <input
              type="checkbox"
              checked={filters.unassigned}
              onChange={(e) =>
                update({ ...filters, unassigned: e.target.checked })
              }
            />
            Unassigned
          </label>
          <label className="iw-check">
            <input
              type="checkbox"
              checked={filters.needs_information}
              onChange={(e) =>
                update({ ...filters, needs_information: e.target.checked })
              }
            />
            Needs information
          </label>
        </div>
        <NetworkWorkFilters
          items={resource.data?.items ?? []}
          networkId={filters.network_id}
          organizationId={filters.organization_id}
          locationId={filters.location_id}
          onNetwork={(network_id) => update({...filters,network_id})}
          onOrganization={(organization_id) => update({...filters,organization_id})}
          onLocation={(location_id) => update({...filters,location_id})}
        />
        <ErrorMessage error={resource.error} retry={resource.refresh} />
      </section>
      <section className="iw-split">
        <div className="iw-card">
          {resource.loading && <p role="status">{resource.data ? "Refreshing work; showing previously loaded results…" : "Loading work…"}</p>}
          {resource.error && resource.data && <p>Showing previously loaded work; the latest refresh failed and these results may be out of date.</p>}
          {!resource.loading && !resource.error && resource.data && items.length === 0 && (
            <div className="iw-empty"><p>No work matches these filters.</p><p>Receive a provider file to create reviewable evidence, or broaden the filters above.</p><a className="wb-empty-action" href="?view=intake">Receive a provider file</a></div>
          )}
          <ul className="iw-list">
            {items.slice(0, 200).map((item: WorkCase) => (
              <li key={item.id}>
                <button
                  aria-pressed={selected === item.id}
                  onClick={() => setSelected(item.id)}
                >
                  <strong>{item.provider_name || item.id}</strong>
                  <span>
                    {pretty(item.issue)} · {pretty(item.status)}
                  </span>
                  <small>
                    {item.kind} · {item.location_id || "Unresolved location"} ·{" "}
                    {item.owner?.trim() || "Unassigned"}
                  </small>
                  {item.network_id && <small>
                    Network {item.network_label || item.network_id} · {item.location_label || item.practice_location_id || "Unresolved practice location"}
                    {item.organization_id ? ` · ${item.organization_label || item.organization_id}` : " · organization unknown"}
                  </small>}
                  <small>
                    {pretty(item.risk_level)} priority: {item.risk_reason}
                  </small>
                  {item.follow_up && <small>Follow up {item.follow_up}</small>}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="iw-card">
          {selected ? (
            <WorkDetail
              key={selected}
              id={selected}
              changed={resource.refresh}
            />
          ) : (
            <div className="iw-empty">
              <h2>Select a work item</h2>
              <p>
                Compare evidence, record a reason, and preserve the decision
                history.
              </p>
            </div>
          )}
        </div>
      </section>
    </>
  );
}
function WorkDetail({
  id,
  changed,
}: {
  id: string;
  changed: () => Promise<void>;
}) {
  const resource = useResource<WorkCase>(`/work/${encodeURIComponent(id)}`),
    detail = resource.data;
  const [action, setAction] = useState<WorkAction>("assign"),
    [draft, setDraft] = useState({
      contact_at: "", method: "phone", outcome: "no_answer", contact_target: "", respondent_role: "", response_summary: "", reported_phone: "",
      actor: "",
      reason: "",
      owner: "",
      follow_up: "",
      proposal: "",
      submission_reference: "",
      observed: "",
      verification_note: "",
    }),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const actions = detail ? allowedActions(detail) : [];
  const selectedAction = actions.includes(action) ? action : actions[0];
  const actionFields = [
    "actor", "reason",
    ...(selectedAction === "outreach" ? ["contact_at", "method", "outcome", "contact_target", "respondent_role", "response_summary", ...(draft.outcome === "response_received" ? ["reported_phone"] : [])] : []),
    ...(["assign", "needs_information"].includes(selectedAction) ? ["owner", "follow_up"] : []),
    ...(selectedAction === "approve" ? ["proposal"] : []),
    ...(selectedAction === "submit" ? ["submission_reference"] : []),
    ...(selectedAction === "verify" ? ["observed", "verification_note"] : []),
  ] as (keyof typeof draft)[];
  if (!detail)
    return (
      <>
        <ErrorMessage error={resource.error} retry={resource.refresh} />
        {resource.loading && <p role="status">Loading work evidence…</p>}
      </>
    );
  return (
    <>
      <p className="iw-eyebrow">
        {detail.kind} · version {detail.version}
      </p>
      <h2>{detail.provider_name}</h2>
      <p>
        {detail.location_id || "Unresolved location"} · {pretty(detail.status)}
      </p>
      <div className="iw-links">
        <a href={`/api/work-export.xlsx?${new URLSearchParams({ case_id: id })}`} download>
          Download case XLSX
        </a>
        <a href={`/api/work-export.json?${new URLSearchParams({ case_id: id })}`} download>
          Download case JSON
        </a>
      </div>
      <NetworkCaseScope scope={detail.scope} review={detail.participation_review} evidence={detail.evidence} />
      <FollowUpCaseScopes scopes={detail.follow_up_scopes} />
      {detail.scope && <p className="iw-muted">This case export includes only its operational scope. Shared receipt and attempt payloads may contain other source rows and are labeled context.</p>}
      <p className="iw-notice">
        <strong>{pretty(detail.issue)}</strong>
        <br />
        {detail.risk_reason}
      </p>
      <h3>Evidence comparison</h3>
      <EvidenceComparison original={detail.evidence?.original} interpreted={detail.evidence?.normalized} />
      <dl className="iw-facts">
        <dt>Source locator</dt>
        <dd>{JSON.stringify(detail.evidence?.locator)}</dd>
        <dt>Listing value</dt>
        <dd>{String(detail.evidence?.listing_value ?? "—")}</dd>
        <dt>Reference value</dt>
        <dd>{String(detail.evidence?.reference_value ?? "—")}</dd>
        <dt>Current proposal</dt>
        <dd>{String(detail.proposal ?? "—")}</dd>
        <dt>Observed result</dt>
        <dd>{String(detail.observed ?? "—")}</dd>
      </dl>
      {detail.evidence?.receipt_id && (
        <a href={`/api/intakes/${detail.evidence.receipt_id}/packet`}>
          Download source evidence packet
        </a>
      )}
      <details>
        <summary>
          Later source evidence ({detail.later_evidence?.length ?? 0})
        </summary>
        <Json value={detail.later_evidence} />
      </details>
      <section className="iw-decision">
        <h3>Record accountable action</h3>
        <form
          className="iw-form"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await request(`/work/${id}/events`, {
                ...Object.fromEntries(actionFields.filter((key) => draft[key].trim() !== "").map((key) => [key, draft[key]])),
                action: selectedAction,
                expected_version: detail.version,
              });
              await resource.refresh();
              await changed();
              setDraft({ ...draft, reason: "" });
            } catch (failure) {
              setError((failure as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Action
            <select
              value={selectedAction}
              onChange={(e) => setAction(e.target.value as WorkAction)}
            >
              {actions.map((a) => (
                <option key={a} value={a}>
                  {pretty(a)}
                </option>
              ))}
            </select>
          </label>
          {selectedAction === "outreach" && <p>Record a contact attempt or response. This does not send a message, approve a phone number, or verify a directory update. Use a contact timestamp including timezone, for example 2026-11-03T09:30:00-05:00.</p>}
          {actionFields.map((key) => (
            <label key={key}>
              {pretty(key)}
              {["actor", "reason"].includes(key) ||
              (selectedAction === "outreach" && (key === "contact_at" || (key === "response_summary" && draft.outcome === "response_received"))) ||
              (selectedAction === "assign" && key === "owner") ||
              (selectedAction === "approve" && key === "proposal") ||
              (selectedAction === "submit" && key === "submission_reference") ||
              (selectedAction === "verify" &&
                ["observed", "verification_note"].includes(key))
                ? " *"
                : ""}
              {key === "method" || key === "outcome" ? <select value={draft[key]} onChange={(e) => setDraft({...draft, [key]: e.target.value})}>
                {(key === "method" ? ["phone", "email", "portal", "other"] : ["no_answer", "message_left", "response_received", "unable_to_contact"]).map(value => <option key={value} value={value}>{pretty(value)}</option>)}
              </select> : <input
                required={
                  ["actor", "reason"].includes(key) ||
              (selectedAction === "outreach" && (key === "contact_at" || (key === "response_summary" && draft.outcome === "response_received"))) ||
                  (selectedAction === "assign" && key === "owner") ||
                  (selectedAction === "approve" && key === "proposal") ||
                  (selectedAction === "submit" &&
                    key === "submission_reference") ||
                  (selectedAction === "verify" &&
                    ["observed", "verification_note"].includes(key))
                }
                placeholder={
                  key === "owner"
                    ? `Current: ${detail.owner || "Unassigned"}`
                    : key === "follow_up"
                      ? detail.follow_up || ""
                      : ""
                }
                value={draft[key]}
                type={key === "follow_up" ? "date" : "text"}
                onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
              />}
            </label>
          ))}
          <button className="iw-primary" disabled={busy}>
            {busy ? "Saving…" : "Save review event"}
          </button>
        </form>
        <ErrorMessage
          error={error}
          retry={async () => {
            await resource.refresh();
            setError("");
          }}
        />
        <p className="iw-muted">
          Current owner: {detail.owner || "Unassigned"}. Follow-up:{" "}
          {detail.follow_up || "Not scheduled"}. Blank optional fields preserve
          existing values.
        </p>
        <p className="iw-muted">
          If another reviewer changed this case, refresh its version and retry.
          Your unsaved draft stays here. A submitted correction still needs
          observed verification; contradictory evidence can reopen work.
        </p>
      </section>
      <details open>
        <summary>Append-only review history</summary>
        {detail.history?.length ? (
          <ol className="iw-history">
            {detail.history.map((event: WorkEvent, index: number) => (
              <li key={event.id ?? index}>
                <strong>{pretty(event.action ?? event.event_type)}</strong>
                <span>{event.reason}</span>
                {event.action === "outreach" && (() => { const contact = event.payload as Record<string, string> | undefined; return <p>Contact: {contact?.contact_at} · {pretty(contact?.method)} · {pretty(contact?.outcome)}{contact?.contact_target ? ` · ${contact.contact_target}` : ""}{contact?.respondent_role ? ` · ${contact.respondent_role}` : ""}{contact?.response_summary ? ` · ${contact.response_summary}` : ""}{contact?.reported_phone ? ` · Reported phone: ${contact.reported_phone}` : ""}</p>; })()}
                <small>
                  {event.actor} · {event.created_at ?? event.occurred_at}
                </small>
                <details>
                  <summary>Event detail</summary>
                  <Json value={event} />
                </details>
              </li>
            ))}
          </ol>
        ) : (
          <p>No events yet.</p>
        )}
      </details>
    </>
  );
}
function Sources() {
  const resource = useResource<Items<Source>>("/sources");
  return (
    <>
    <Suspense fallback={<p role="status">Loading FHIR capture controls…</p>}><FhirAcquisitionPanel /></Suspense>
    <section className="iw-card">
      <div className="iw-title">
        <h2>Source registry</h2>
        <button onClick={() => void resource.refresh()}>Refresh</button>
      </div>
      <p className="iw-notice">
        NPPES and CMS provide public reference evidence with different coverage
        and date semantics. Missing from a bounded response does not establish
        termination. Asserted links are retained without fetching their
        contents.
      </p>
      <ErrorMessage error={resource.error} retry={resource.refresh} />
      {resource.loading && <p role="status">Loading source health…</p>}
      {resource.data?.items?.length === 0 && (
        <p className="iw-empty">No sources received yet.</p>
      )}
      <div className="iw-source-grid">
        {resource.data?.items?.map((item: Source, index: number) => (
          <article className="iw-source" key={`${item.source}-${index}`}>
            <p className="iw-eyebrow">
              {item.adapter_version || "Supplied evidence"}
            </p>
            <h3>{item.source}</h3>
            <dl className="iw-facts">
              <dt>Bounded scope</dt>
              <dd>
                {typeof item.scope === "object"
                  ? JSON.stringify(item.scope)
                  : String(item.scope || "Supplied artifact")}
              </dd>
              <dt>Last successful intake</dt>
              <dd>{item.last_success || "No successful intake"}</dd>
              <dt>Last failed attempt</dt>
              <dd>
                {typeof item.last_failure === "object"
                  ? JSON.stringify(item.last_failure)
                  : String(item.last_failure || "None recorded")}
              </dd>
            </dl>
            <details>
              <summary>Source detail and limitations</summary>
              <Json value={item} />
            </details>
          </article>
        ))}
      </div>
    </section>
    </>
  );
}
