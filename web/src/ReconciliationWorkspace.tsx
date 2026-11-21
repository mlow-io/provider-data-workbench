import { navigateWorkspace, useWorkspaceQuery, workspaceHref, useWorkspaceActionGuard, updateWorkspaceQuery } from "./workspaceNavigation";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FieldReconciliation } from "./FieldReconciliation";
import { IdentityReview } from "./IdentityReview";
import "./intake.css";
import "./reconciliation.css";

type EntityKind = "unknown" | "clinician" | "organization";
type Json = Record<string, unknown>;
type Receipt = {
  id: string;
  label?: string;
  source: string;
  profile: string;
  received_at?: string;
  attempt_id?: string;
  state?: string;
  designation?: string;
};
type Input = {
  receipt_id: string;
  attempt_id: string;
  entity_kind: EntityKind;
};
type Evidence = {
  original_fields: Json;
  source?: string;
  comparison: Json;
  comparison_provenance?: Json;
  field_findings: Record<string, string[]>;
  locator?: unknown;
  address_path?: string;
  source_problems?: unknown;
  ref?: string;
};
type Profile = {
  rule_version: string;
  total: number;
  quality_counts: Record<string, Record<string, number> | number>;
  items: Evidence[];
  next_offset: number | null;
  sample_truncated?: boolean;
};
type Metrics = {
  input_records: number;
  address_references: number;
  candidate_count: number;
  elapsed_seconds: number;
  counts: { clinician: number; location: number };
};
type Run = {
  id: string;
  rule_version: string;
  metrics: Metrics;
  actor: string;
  reason: string;
  created_at: string;
  inputs_fresh?: boolean;
  inputs?: Input[];
};
type Candidate = {
  id: string;
  kind: "clinician" | "location";
  left: string;
  right: string;
  agreements: string[];
  contradictions: string[];
  missing: string[];
  rank: number;
  eligible: boolean;
  rule_version: string;
  left_record: Evidence;
  right_record: Evidence;
  sample_truncated?: boolean;
};
type Page<T> = {
  items: T[];
  total: number;
  next_offset: number | null;
  inputs_fresh?: boolean;
  reason_counts?: Record<string, number>;
  unfiltered_total?: number;
};

async function request<T>(path: string, payload?: unknown): Promise<T> {
  const response = await fetch(
    path,
    payload === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : JSON.stringify(detail ?? `Request failed (${response.status})`),
    );
  }
  return response.json() as Promise<T>;
}
const show = (value: unknown) =>
  value === undefined ? "[absent]" : JSON.stringify(value);
const human = (value: string) => value.replaceAll("_", " ");
const evidenceLabel = (code: string) => human(code).replace(/\bnpi\b/g, "NPI");
function sourceContext(record: Evidence, kind: string): string {
  const original = record.original_fields;
  const source = record.source || (typeof original.source === "string" ? original.source : "Source unavailable");
  const location = typeof original.source_location_id === "string" && original.source_location_id.trim()
    ? `Source location: ${original.source_location_id}`
    : kind === "location" && typeof at(original, "address.line1") === "string" && String(at(original, "address.line1")).trim()
      ? `Source address: ${String(at(original, "address.line1"))}` : kind === "clinician" ? "No source location label" : "Location unavailable";
  const locator = record.locator == null ? "Row unavailable" : `Row: ${typeof record.locator === "string" ? record.locator : JSON.stringify(record.locator)}`;
  const path = kind === "location" && record.address_path ? `Address path: ${record.address_path}` : "";
  return [source, location, locator, path].filter(Boolean).join(" · ");
}
function at(object: Json, path: string): unknown {
  return path
    .split(".")
    .reduce<unknown>(
      (value, key) =>
        value !== null && typeof value === "object"
          ? (value as Json)[key]
          : undefined,
      object,
    );
}
function ErrorMessage({ error }: { error: Error | null }) {
  return error ? (
    <p className="rc-error" role="alert">
      {error.message}
    </p>
  ) : null;
}
function Pager({
  offset,
  next,
  onChange,
  label,
}: {
  offset: number;
  next: number | null;
  onChange: (offset: number) => void;
  label: string;
}) {
  return (
    <div className="rc-pager" aria-label={label}>
      <button
        disabled={offset === 0}
        onClick={() => onChange(Math.max(0, offset - 20))}
      >
        Previous
      </button>
      <span>From {offset + 1}</span>
      <button
        disabled={next === null}
        onClick={() => next !== null && onChange(next)}
      >
        Next
      </button>
    </div>
  );
}
function EvidencePanel({ record, title }: { record: Evidence; title: string }) {
  const fields = [
    "provider_name",
    "npi",
    "entity_kind",
    "phone",
    "phone_extension",
    ...[
      "line1",
      "line2",
      "suite",
      "city",
      "state",
      "zip",
      "zip_base",
      "kind",
      "path",
      "source_path",
    ].map((field) => `address.${field}`),
  ];
  return (
    <section className="rc-evidence">
      <h4>{title}</h4>
      <p className="rc-reference">
        Locator {show(record.locator)} · Address path{" "}
        {record.address_path ||
          String(at(record.original_fields, "address.path") ?? "[none]")}
      </p>
      <div
        className="rc-scroll"
        tabIndex={0}
        role="region"
        aria-label={`${title} source and comparison values`}
      >
        <table>
          <thead>
            <tr>
              <th>Field</th>
              <th>Source value</th>
              <th>Comparison value</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((field) => (
              <tr key={field}>
                <th scope="row">{field}</th>
                <td>
                  <code>{show(at(record.original_fields, field))}</code>
                </td>
                <td>
                  <code>{show(at(record.comparison, field))}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details>
        <summary>Field findings and transformation provenance</summary>
        <pre>
          {JSON.stringify(
            {
              findings: record.field_findings,
              transformations: record.comparison_provenance ?? {},
              source_problems: record.source_problems ?? [],
            },
            null,
            2,
          )}
        </pre>
      </details>
    </section>
  );
}
function Reasons({
  heading,
  reasons,
  className,
}: {
  heading: string;
  reasons: string[];
  className: string;
}) {
  return (
    <section className={className}>
      <h4>{heading}</h4>
      {reasons.length ? (
        <ul>
          {reasons.map((reason) => (
            <li key={reason}>{human(reason)}</li>
          ))}
        </ul>
      ) : (
        <p>None recorded</p>
      )}
    </section>
  );
}

export function ReconciliationWorkspace() {
  const query = useWorkspaceQuery();
  const actionGuard = useWorkspaceActionGuard();
  const queryString = query.toString();
  const seedVersion = query.get("version") ?? "";
  const seedFeed = query.get("feed") ?? "";
  const seedReceipt = query.get("receipt") ?? "";
  const seedAttempt = query.get("attempt") ?? "";
  const seedRequested = Boolean(seedVersion || seedFeed || seedReceipt || seedAttempt);
  const runId = query.get("run") ?? "";
  const setRunId = (id: string) => navigateWorkspace("reconciliation", { ...Object.fromEntries(query), run: id });
  const seed = useQuery({
    queryKey: ["approved-reconciliation-seed", seedVersion, seedFeed, seedReceipt, seedAttempt],
    enabled: seedRequested,
    retry: false,
    queryFn: async () => {
      if (!seedVersion || !seedFeed || !seedReceipt || !seedAttempt) throw new Error("The approved-version link is incomplete. Return to Managed feeds and choose a version.");
      const version = await request<{ id: string; feed_id: string; state: string; manifest: { receipt_id: string; attempt_id: string } }>(`/api/feed-versions/${encodeURIComponent(seedVersion)}`);
      if (version.feed_id !== seedFeed || version.state !== "approved" || version.manifest.receipt_id !== seedReceipt || version.manifest.attempt_id !== seedAttempt) throw new Error("The link does not identify an approved version and its exact source interpretation. Return to Managed feeds.");
      await request(`/api/intakes/${encodeURIComponent(seedReceipt)}?${new URLSearchParams({ attempt_id: seedAttempt })}`);
      return { receipt_id: seedReceipt, attempt_id: seedAttempt, entity_kind: "unknown" as const };
    },
  });
  const client = useQueryClient();
  const [selected, setSelected] = useState<Record<string, Input>>({});
  const [inspectId, setInspectId] = useState("");
  const [profileOffset, setProfileOffset] = useState(0);
  const [actor, setActor] = useState("");
  const [reason, setReason] = useState("");
  const [historyOffset, setHistoryOffset] = useState(0);
  const kind = query.get("candidate_kind") ?? "clinician";
  const eligibility = query.get("eligibility") ?? "";
  const evidenceReason = query.get("evidence_reason") ?? "";
  const search = query.get("candidate_search") ?? "";
  const setKind = (value: string) => updateWorkspaceQuery({ candidate_kind: value, evidence_reason: null });
  const setEligibility = (value: string) => updateWorkspaceQuery({ eligibility: value, evidence_reason: null });
  const [candidateOffset, setCandidateOffset] = useState(0);
  const [searchDraft, setSearchDraft] = useState(search);
  const receipts = useQuery({
    queryKey: ["reconciliation-receipts"],
    queryFn: () => request<{ items: Receipt[] }>("/api/intakes"),
    // Intake uses a separate resource, so its new deliveries do not invalidate
    // this cache. Always refresh when returning to the comparison workspace.
    staleTime: 0,
    refetchOnMount: "always",
  });
  const history = useQuery({
    queryKey: ["reconciliation-history", historyOffset],
    queryFn: () =>
      request<Page<Run>>(
        `/api/reconciliation/runs?offset=${historyOffset}&limit=20`,
      ),
  });
  useEffect(() => {
    if (!runId && !seedRequested && history.data?.items[0]) setRunId(history.data.items[0].id);
  }, [runId, history.data]);
  useEffect(() => { setSelected({}); setInspectId(""); }, [seedVersion, seedFeed, seedReceipt, seedAttempt]);
  useEffect(() => {
    if (seed.data && !runId) {
      setSelected({ [seed.data.receipt_id]: seed.data });
      setInspectId(seed.data.receipt_id);
    }
  }, [seed.data, seedVersion, runId]);
  useEffect(() => { setCandidateOffset(0); }, [queryString]);
  useEffect(() => { setSearchDraft(search); }, [search]);
  const seedPrepared = !seedRequested || (seed.isSuccess && selected[seedReceipt]?.attempt_id === seedAttempt);
  const inspected = selected[inspectId];
  const profile = useQuery({
    queryKey: ["comparison-profile", inspected, profileOffset],
    enabled: Boolean(inspected),
    queryFn: () =>
      request<Profile>(
        `/api/intakes/${encodeURIComponent(inspected.receipt_id)}/comparison-profile?${new URLSearchParams({ expected_attempt: inspected.attempt_id, entity_kind: inspected.entity_kind, offset: String(profileOffset), limit: "20" })}`,
      ),
  });
  const run = useQuery({
    queryKey: ["reconciliation-run", runId, seedVersion, seedReceipt, seedAttempt],
    enabled: Boolean(runId) && (!seedRequested || seed.isSuccess),
    queryFn: async () => {
      const value = await request<Run>(`/api/reconciliation/runs/${encodeURIComponent(runId)}`);
      if (seedRequested && !value.inputs?.some(input => input.receipt_id === seedReceipt && input.attempt_id === seedAttempt)) throw new Error("The saved run is incompatible with this approved delivery interpretation. Return to its dataset version or choose a different run.");
      return value;
    },
  });
  const candidates = useQuery({
    queryKey: [
      "reconciliation-candidates",
      runId,
      kind,
      eligibility, evidenceReason, search,
      candidateOffset, seedVersion, seedReceipt, seedAttempt,
    ],
    enabled: Boolean(runId) && run.isSuccess,
    queryFn: () =>
      request<Page<Candidate>>(
        `/api/reconciliation/runs/${encodeURIComponent(runId)}/candidates?${new URLSearchParams({ kind, ...(eligibility ? { eligible: eligibility } : {}), ...(evidenceReason ? { reason: evidenceReason } : {}), ...(search ? { search } : {}), offset: String(candidateOffset), limit: "20" })}`,
      ),
  });
  const create = useMutation({
    mutationFn: () => {
      if (!seedPrepared) throw new Error("Review the approved source link before creating a run.");
      return request<Run>("/api/reconciliation/runs", {
        inputs: Object.values(selected),
        actor: actor.trim(),
        reason: reason.trim(),
      });
    },
    onMutate: () => actionGuard.capture(),
    onSuccess: async (value, _body, origin) => {
      const invalidation = client.invalidateQueries({ queryKey: ["reconciliation-history"] });
      if (!actionGuard.isCurrent(origin)) { await invalidation; return; }
      setRunId(value.id);
      setCandidateOffset(0);
      setHistoryOffset(0);
      client.setQueryData(["reconciliation-run", value.id, seedVersion, seedReceipt, seedAttempt], value);
      await invalidation;
    },
  });
  const sources =
    receipts.data?.items.filter(
      (receipt) =>
        receipt.attempt_id &&
        !["processing", "failed", "interrupted", "rejected"].includes(
          receipt.state ?? "",
        ),
    ) ?? [];
  const staleSelection = sources.some(
    (receipt) =>
      selected[receipt.id] &&
      selected[receipt.id].attempt_id !== receipt.attempt_id,
  );
  const staleRun =
    run.data?.inputs_fresh === false || candidates.data?.inputs_fresh === false;
  const selectedCount = Object.keys(selected).length;
  const namespaceCount = new Set(
    sources
      .filter((source) => selected[source.id])
      .map((source) => source.source),
  ).size;
  const chooseRun = (id: string) => {
    setRunId(id);
    setCandidateOffset(0);
  };
  const exportParams = new URLSearchParams({ kind, ...(eligibility ? { eligible: eligibility } : {}),
    ...(evidenceReason ? { reason: evidenceReason } : {}), ...(search ? { search } : {}) });
  const refresh = async () => {
    await Promise.all([
      receipts.refetch(),
      history.refetch(),
      ...(runId ? [run.refetch(), candidates.refetch()] : []),
    ]);
  };
  return (
    <main className="iw-shell rc-shell">
      <header className="iw-heading">
        <p className="iw-eyebrow">Retained evidence / Reconciliation</p>
        <h1>Provider records and reconciliation</h1>
        <p>
          Inspect comparison rules, then propose clinician and practice-location
          candidates separately. A candidate creates no identity or link. Rule
          ranking is not a probability.
        </p>
        <button
          onClick={() => void refresh()}
          disabled={receipts.isFetching || run.isFetching}
        >
          Refresh sources and run status
        </button>
      </header>
      {seedRequested && <aside className="iw-card" aria-label="Approved delivery context">
        <h2>Continue from the approved delivery</h2>
        <p>Dataset version <code>{seedVersion}</code> · receipt <code>{seedReceipt}</code> · interpretation <code>{seedAttempt}</code></p>
        {seed.isPending && <p role="status">Checking approved source evidence…</p>}
        <ErrorMessage error={seed.error} />
        {seed.isSuccess && <p>The approved clinic interpretation stays pinned; its entity type still needs source review. Choose at least one other source and review the inputs before explicitly creating a run.</p>}
        <a href={workspaceHref("feeds", { feed: seedFeed, version: seedVersion })}>Return to this dataset version</a>
      </aside>}
      <section className="iw-card" aria-label="Reconciliation next steps">
        <strong>Select sources → Review identity links → Review fields → Assess change → Confirm follow-up</strong>
        <p>Each saved decision retains its evidence. Opening a step creates no records or approvals.</p>
        <a href="#reconciled-fields">Continue to reviewed field evidence</a>
      </section>
      <section className="iw-card" aria-labelledby="rc-sources">
        <div className="iw-title">
          <div>
            <h2 id="rc-sources">1. Select source deliveries</h2>
            <p>
              Choose 2–6 retained interpretations. Unknown entity type stays
              unknown; declare a type only when the source supports it.
            </p>
          </div>
          <span className="iw-badge">{selectedCount} selected</span>
        </div>
        <ErrorMessage error={receipts.error} />
        {receipts.isFetching && !receipts.isPending && <p role="status">Refreshing source deliveries…</p>}
        {!receipts.isFetching && !receipts.error && new Set(sources.map(source => source.source)).size < 2 && <p>Comparison needs at least two retained interpretations from different sources. <a href="?view=intake">Open Intake</a> to add another. In sample mode, the synthetic clinic workbook and synthetic NPPES response are separate sources; inspect each before creating a run.</p>}
        {receipts.isPending ? (
          <p role="status">Loading retained sources…</p>
        ) : !sources.length && (receipts.isFetching || receipts.error) ? null : !sources.length ? (
          <p>
            No parsed deliveries yet. Add source files in Intake, then return
            here.
          </p>
        ) : (
          <div className="rc-source-list">
            {sources.map((receipt) => (
              <div className="rc-source" key={receipt.id} data-receipt-id={receipt.id}>
                <label className="rc-check">
                  <input
                    type="checkbox"
                    checked={Boolean(selected[receipt.id])}
                    disabled={
                      create.isPending ||
                      receipts.isFetching || receipts.isError ||
                      !seedPrepared ||
                      (seedRequested && receipt.id === seedReceipt) ||
                      (!selected[receipt.id] && selectedCount >= 6)
                    }
                    onChange={(event) => {
                      const checked = event.target.checked;
                      setSelected((current) => {
                        const next = { ...current };
                        if (checked)
                          next[receipt.id] = {
                            receipt_id: receipt.id,
                            attempt_id: receipt.attempt_id!,
                            entity_kind: "unknown",
                          };
                        else delete next[receipt.id];
                        return next;
                      });
                      if (checked && !inspectId) {
                        setInspectId(receipt.id);
                        setProfileOffset(0);
                      }
                      if (!checked && inspectId === receipt.id)
                        setInspectId("");
                    }}
                  />
                  <span>
                    <strong>{receipt.label || receipt.id}</strong>
                    <small>
                      {receipt.source} · {receipt.profile} · {receipt.state} ·{" "}
                      {receipt.designation}
                    </small>
                    <small>Received {receipt.received_at || "time unavailable"} · Receipt <code>{receipt.id}</code></small>
                  </span>
                </label>
                {selected[receipt.id] && (
                  <div className="rc-source-actions">
                    <label>
                      Entity type for {receipt.label || receipt.id}
                      <select
                        aria-label={`Entity type for ${receipt.label || receipt.id}`}
                        value={selected[receipt.id].entity_kind}
                        disabled={create.isPending}
                        onChange={(event) => {
                          setSelected((current) => ({
                            ...current,
                            [receipt.id]: {
                              ...current[receipt.id],
                              entity_kind: event.target.value as EntityKind,
                            },
                          }));
                          setProfileOffset(0);
                        }}
                      >
                        <option value="unknown">Unknown</option>
                        <option value="clinician">Clinician</option>
                        <option value="organization">Organization</option>
                      </select>
                    </label>
                    <button
                      onClick={() => {
                        setInspectId(receipt.id);
                        setProfileOffset(0);
                      }}
                    >
                      Inspect quality: {receipt.label || receipt.id}
                    </button>
                    {selected[receipt.id].attempt_id !== receipt.attempt_id && !(seedRequested && receipt.id === seedReceipt) && (
                      <button
                        onClick={() =>
                          setSelected((current) => ({
                            ...current,
                            [receipt.id]: {
                              ...current[receipt.id],
                              attempt_id: receipt.attempt_id!,
                            },
                          }))
                        }
                      >
                        Use latest interpretation
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        {staleSelection && (
          <p role="alert" className="rc-warning">
            A selected source has a newer interpretation. Review the changed evidence before creating a run.
            {seedRequested ? <a href={workspaceHref("reconciliation")}>Start a comparison without the approved-version context</a> : " Inspect and select its latest interpretation."}
          </p>
        )}
        {selectedCount >= 2 && namespaceCount < 2 && (
          <p>
            Choose deliveries from at least two different source namespaces.
          </p>
        )}
        <div className="rc-create">
          <label>
            Run reviewer
            <input
              value={actor}
              onChange={(event) => setActor(event.target.value)}
              disabled={create.isPending}
            />
          </label>
          <label>
            Run reason
            <input
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              disabled={create.isPending}
            />
          </label>
          <button
            className="button button-primary"
            disabled={
              selectedCount < 2 ||
              selectedCount > 6 ||
              namespaceCount < 2 ||
              !actor.trim() ||
              !reason.trim() ||
              staleSelection ||
              create.isPending ||
              receipts.isFetching || receipts.isError ||
              !seedPrepared
            }
            onClick={() => create.mutate()}
          >
            {create.isPending
              ? "Creating candidate run…"
              : "Create candidate run"}
          </button>
        </div>
        <ErrorMessage error={create.error} />
      </section>
      <section className="iw-card" aria-labelledby="rc-quality">
        <h2 id="rc-quality">2. Inspect comparison quality</h2>
        {!inspected ? (
          <p>
            Select a delivery and choose Inspect quality to see retained source
            values beside comparison values.
          </p>
        ) : (
          <>
            <p>
              Source:{" "}
              <strong>
                {sources.find((source) => source.id === inspectId)?.label ||
                  inspectId}
              </strong>{" "}
              · Pinned attempt <code>{inspected.attempt_id}</code>
            </p>
            <ErrorMessage error={profile.error} />
            {profile.isFetching && (
              <p role="status">Loading comparison evidence…</p>
            )}
            {profile.data && (
              <>
                <p>
                  {profile.data.total} address references · Rule{" "}
                  <code>{profile.data.rule_version}</code>. Quality counts cover
                  all references; rows below are paginated.
                </p>
                <div className="rc-quality-counts">
                  {Object.entries(profile.data.quality_counts).flatMap(
                    ([key, counts]) => {
                      const separator = key.lastIndexOf(":");
                      const field =
                        typeof counts === "number" && separator >= 0
                          ? key.slice(0, separator)
                          : key;
                      const entries =
                        typeof counts === "number"
                          ? [
                              [
                                separator >= 0
                                  ? key.slice(separator + 1)
                                  : "finding",
                                counts,
                              ] as const,
                            ]
                          : Object.entries(counts);
                      return entries.map(([code, count]) => (
                        <span key={`${field}:${code}`}>
                          <b>{count}</b> {field}: {human(code)}
                        </span>
                      ));
                    },
                  )}
                </div>
                {profile.data.items.map((item, index) => (
                  <details key={item.ref ?? index}>
                    <summary>
                      Inspect source record {profileOffset + index + 1} ·{" "}
                      {String(item.original_fields.provider_name ?? "Unnamed")}{" "}
                      · {item.address_path || "No address path"}
                    </summary>
                    <EvidencePanel record={item} title="Source record" />
                  </details>
                ))}
                {profile.data.sample_truncated && (
                  <p>
                    Some evidence text is bounded for display; retained source
                    evidence remains separate.
                  </p>
                )}
                <Pager
                  offset={profileOffset}
                  next={profile.data.next_offset}
                  onChange={setProfileOffset}
                  label="Comparison profile pages"
                />
              </>
            )}
          </>
        )}
      </section>
      <FieldReconciliation />
      <section className="iw-card" aria-labelledby="rc-candidates">
        <div className="iw-title">
          <div>
            <h2 id="rc-candidates">3. Inspect candidate runs</h2>
            <p>
              Persisted runs retain selected inputs and explanations. Open a
              candidate to review clinician or location links explicitly.
            </p>
          </div>
        </div>
        <ErrorMessage error={history.error} />
        {history.isPending && <p role="status">Loading run history…</p>}
        <label>
          Saved candidate run
          <select
            aria-label="Saved candidate run"
            value={runId}
            onChange={(event) => chooseRun(event.target.value)}
          >
            <option value="">Select a run</option>
            {run.data &&
              !history.data?.items.some((item) => item.id === runId) && (
                <option value={runId}>{runId}</option>
              )}
            {history.data?.items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.created_at} · {item.actor} · {item.id}
              </option>
            ))}
          </select>
        </label>
        {history.data && (
          <>
            <p>{history.data.total} saved runs</p>
            <Pager
              offset={historyOffset}
              next={history.data.next_offset}
              onChange={setHistoryOffset}
              label="Run history pages"
            />
          </>
        )}
        <ErrorMessage error={run.error} />
        {run.isFetching && runId && <p role="status">Checking run snapshot…</p>}
        {staleRun && (
          <p role="alert" className="rc-warning">
            This run is stale: a selected source interpretation, accepted
            baseline, or reviewed snapshot has changed. Historical candidates
            remain readable. Create a new run against current inputs.
          </p>
        )}
        {run.data && (
          <>
            <div className="rc-run-summary" aria-label="Run measurements">
              <span>
                <b>{run.data.metrics.input_records}</b> retained records
              </span>
              <span>
                <b>{run.data.metrics.address_references}</b> address references
              </span>
              <span>
                <b>{run.data.metrics.candidate_count}</b> candidates
              </span>
              <span>{run.data.metrics.elapsed_seconds.toFixed(4)} seconds</span>
            </div>
            <p>
              Rule <code>{run.data.rule_version}</code> · {run.data.reason}
            </p>
            <div className="rc-filters">
              <label>
                Candidate type
                <select
                  aria-label="Candidate type"
                  value={kind}
                  onChange={(event) => {
                    setKind(event.target.value as "clinician" | "location");
                    setCandidateOffset(0);
                  }}
                >
                  <option value="clinician">Clinician</option>
                  <option value="location">Practice location</option>
                </select>
              </label>
              <label>
                Review eligibility
                <select
                  aria-label="Review eligibility"
                  value={eligibility}
                  onChange={(event) => {
                    setEligibility(event.target.value);
                    setCandidateOffset(0);
                  }}
                >
                  <option value="">All candidates</option>
                  <option value="true">Eligible for review</option>
                  <option value="false">Unresolved or conflicting</option>
                </select>
              </label>
              <label>
                Evidence reason
                <select aria-label="Evidence reason" value={evidenceReason}
                  disabled={candidates.isFetching}
                  onChange={event => { updateWorkspaceQuery({ evidence_reason: event.target.value }); setCandidateOffset(0); }}>
                  <option value="">All evidence reasons</option>
                  {evidenceReason && !candidates.data?.reason_counts?.[evidenceReason] && <option value={evidenceReason}>{evidenceLabel(evidenceReason)} · 0 pairs</option>}
                  {Object.entries(candidates.data?.reason_counts ?? {}).map(([code, count]) => <option key={code} value={code}>{evidenceLabel(code)} · {count} {count === 1 ? "pair" : "pairs"}</option>)}
                </select>
              </label>
            </div>
            <form className="rc-filters" onSubmit={event => { event.preventDefault(); const value = searchDraft.trim(); setSearchDraft(value); updateWorkspaceQuery({ candidate_search: value }); setCandidateOffset(0); }}>
              <label>Find a provider or identifier
                <input aria-label="Find a provider or identifier" value={searchDraft} maxLength={100}
                  onChange={event => setSearchDraft(event.target.value)} />
              </label>
              <button type="submit">Search candidates</button>
              {search && <button type="button" onClick={() => { setSearchDraft(""); updateWorkspaceQuery({ candidate_search: null }); setCandidateOffset(0); }}>Clear search</button>}
            </form>
            {search && <p role="status">Applied search: {search}</p>}
            <p className="rc-reference">Search checks either side's provider name, NPI or source-native ID across the full run. Applied terms appear in the address and bookmarks, and are sent to the local server and included in filtered exports. Share links only with people allowed to see those terms.</p>
            <p className="rc-reference">Reason counts cover the complete type, eligibility and search selection before the reason filter. A pair may have several reasons; counts are not additive. Filtering does not change eligibility or approve a link.</p>
            <a href={`/api/reconciliation/runs/${encodeURIComponent(runId)}/candidates/export?${exportParams}`}>Download filtered candidate evidence (JSON)</a>
            <p className="rc-reference">The download contains every pair in the applied filters and its retained source evidence, not only this page. Review decisions are separate.</p>
            {evidenceReason && <p role="status" aria-label="Evidence reason summary">Showing {candidates.data?.total ?? "…"} of {candidates.data?.unfiltered_total ?? "…"} pairs for this type, eligibility and search · {evidenceLabel(evidenceReason)}. <button onClick={() => { updateWorkspaceQuery({ evidence_reason: null }); setCandidateOffset(0); }}>Clear evidence reason</button></p>}
            <p>
              {kind === "clinician"
                ? "Clinician candidates compare person identity evidence. Shared phones and offices do not establish clinician identity."
                : "Location candidates compare operating addresses separately from clinician identity. Mailing addresses are excluded; suites remain distinct."}
            </p>
            <ErrorMessage error={candidates.error} />
            {candidates.isFetching && <p role="status">Loading candidates…</p>}
            {candidates.data && (
              <>
                <p>
                  {candidates.data.total} {kind} candidates in this filter ·
                  Ranking expresses rule priority only.
                </p>
                {!candidates.data.items.length && (
                  <p>
                    No candidates in this filter. Missing candidates are not
                    evidence that records are unrelated.
                  </p>
                )}
                <div className="rc-candidates">
                  {candidates.data.items.map((candidate) => (
                    <details className="rc-candidate" key={candidate.id}>
                      <summary>
                        <span>
                          {String(
                            candidate.left_record.original_fields
                              .provider_name ?? candidate.left,
                          )}{" "}
                          ↔{" "}
                          {String(
                            candidate.right_record.original_fields
                              .provider_name ?? candidate.right,
                          )}
                        </span>
                        <small className="rc-candidate-context">Left: {sourceContext(candidate.left_record, candidate.kind)}<br />Right: {sourceContext(candidate.right_record, candidate.kind)}</small>
                        <span className="rc-candidate-meta">
                          Rule rank {candidate.rank} ·{" "}
                          {candidate.eligible
                            ? "Eligible for review"
                            : "Unresolved / conflicting"}
                        </span>
                      </summary>
                      <p className="rc-reference">
                        Candidate <code>{candidate.id}</code> · {candidate.kind}{" "}
                        · {candidate.rule_version}
                      </p>
                      <p className="rc-reference">
                        {candidate.left} ↔ {candidate.right}
                      </p>
                      <div className="rc-reasons">
                        <Reasons
                          heading="Agreements"
                          reasons={candidate.agreements}
                          className="rc-agreements"
                        />
                        <Reasons
                          heading="Contradictions"
                          reasons={candidate.contradictions}
                          className="rc-contradictions"
                        />
                        <Reasons
                          heading="Missing evidence"
                          reasons={candidate.missing}
                          className="rc-missing"
                        />
                      </div>
                      <div className="rc-pair">
                        <EvidencePanel
                          record={candidate.left_record}
                          title="Left source"
                        />
                        <EvidencePanel
                          record={candidate.right_record}
                          title="Right source"
                        />
                      </div>
                      <IdentityReview
                        key={`${runId}:${candidate.id}`}
                        runId={runId}
                        candidateId={candidate.id}
                        kind={candidate.kind}
                      />
                      {candidate.sample_truncated && (
                        <p>
                          Evidence display is bounded. Consult the retained
                          delivery for full source content.
                        </p>
                      )}
                    </details>
                  ))}
                </div>
                <Pager
                  offset={candidateOffset}
                  next={candidates.data.next_offset}
                  onChange={setCandidateOffset}
                  label="Candidate pages"
                />
              </>
            )}
          </>
        )}
        {!runId && !history.isPending && (
          <p>
            Create a candidate run to compare the selected deliveries. Nothing
            is linked automatically.
          </p>
        )}
      </section>
    </main>
  );
}
