import { useWorkspaceQuery, updateWorkspaceQuery, useWorkspaceActionGuard } from "./workspaceNavigation";
import { FollowUpPlan } from "./FollowUpPlan";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type FieldName = "phone" | "address" | "provider_name" | "npi";
type FieldState = {
  field: FieldName;
  decision: {
    id: string;
    decision: "select" | "conflict";
    value?: unknown;
    stale?: boolean;
  } | null;
};
type Input = {
  receipt_id: string;
  attempt_id: string;
  entity_kind: "unknown" | "clinician" | "organization";
};
type Receipt = {
  id: string;
  attempt_id?: string;
  label?: string;
  source: string;
  profile?: string;
  state?: string;
  designation?: string;
};
type Page<T> = { items: T[]; total: number; next_offset: number | null };
type Proposal = {
  id: string;
  clinician_id?: string;
  location_id?: string | null;
  field: FieldName;
  proposed_value: unknown;
  proposed_original?: unknown;
  prior_evidence: unknown;
  inputs: Input[];
  actor: string;
  reason: string;
  created_at: string;
};
type ProposalRequest = {
  clinician_id: string;
  location_id: string | null;
  field: FieldName;
  proposed_value: unknown;
  inputs: Input[];
  expected_snapshot: string;
  request_id: string;
  actor: string;
  reason: string;
};
type Counts = {
  affected: number;
  unaffected_within_assessed_scope: number;
  not_assessed: number;
};
type Impact = {
  proposal_id: string;
  snapshot: string;
  inputs_fresh: boolean;
  stale_reasons: string[];
  counts: Counts;
  work_counts: Counts;
  targets: {
    ref: string;
    source: string;
    network_id?: string | null;
    network_label?: string | null;
    classification: string;
    reason: string;
    value: unknown;
    comparison_value: unknown;
    clinician_link?: unknown;
    location_link?: unknown;
    receipt_id: string;
    attempt_id: string;
    locator: unknown;
    address_path: string;
  }[];
  total: number;
  next_offset: number | null;
  existing_work: {
    id: string;
    status: string;
    owner?: string | null;
    version: number;
    field_name: string;
    classification: string;
    reason: string;
    refs: string[];
  }[];
  work_total: number;
  work_next_offset: number | null;
  scope_notice: string;
};
class ImpactError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}
async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    path,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ImpactError(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail ?? `Request failed (${response.status})`),
      response.status,
    );
  }
  return response.json() as Promise<T>;
}
const human = (text: string) => text.replaceAll("_", " ");
const show = (value: unknown) =>
  value === undefined ? "[absent]" : JSON.stringify(value, null, 2);
function Pages({
  label,
  offset,
  next,
  locked,
  onChange,
}: {
  label: string;
  offset: number;
  next: number | null;
  locked: boolean;
  onChange: (offset: number) => void;
}) {
  return (
    <div className="rc-pager" role="group" aria-label={label}>
      <button
        disabled={locked || offset === 0}
        onClick={() => onChange(Math.max(0, offset - 20))}
      >
        Previous
      </button>
      <span>From {offset + 1}</span>
      <button
        disabled={locked || next === null}
        onClick={() => next !== null && onChange(next)}
      >
        Next
      </button>
    </div>
  );
}
function Coverage({ title, counts }: { title: string; counts: Counts }) {
  return (
    <section aria-label={title}>
      <h4>{title}</h4>
      <div className="rc-run-summary">
        <span>
          <b>{counts.affected}</b> affected
        </span>
        <span>
          <b>{counts.unaffected_within_assessed_scope}</b> unaffected within
          assessed scope
        </span>
        <span>
          <b>{counts.not_assessed}</b> not assessed
        </span>
      </div>
    </section>
  );
}
export function ChangeImpact({
  clinicianId,
  locationId,
  snapshot,
  inputsFresh,
  fields,
  otherBusy,
  onPendingChange,
  onRefresh,
}: {
  clinicianId: string;
  locationId: string | null;
  snapshot: string;
  inputsFresh: boolean;
  fields: FieldState[];
  otherBusy: boolean;
  onPendingChange: (pending: boolean) => void;
  onRefresh: () => Promise<void>;
}) {
  const client = useQueryClient();
  const route = useWorkspaceQuery();
  const actionGuard = useWorkspaceActionGuard();
  const routeProposal = route.get("proposal") ?? "";
  const [opened, setOpened] = useState(Boolean(routeProposal));
  const [followUpPending, setFollowUpPending] = useState(false);
  const [field, setField] = useState<FieldName | "">("");
  const [text, setText] = useState("");
  const [extension, setExtension] = useState("");
  const [address, setAddress] = useState({
    line1: "",
    line2: "",
    suite: "",
    city: "",
    state: "",
    zip: "",
  });
  const [selected, setSelected] = useState<Record<string, Input>>({});
  const [sourceOffset, setSourceOffset] = useState(0);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [actor, setActor] = useState("");
  const [reason, setReason] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [requiresRefresh, setRequiresRefresh] = useState(false);
  const [pending, setPending] = useState<ProposalRequest | null>(null);
  const selectedId = routeProposal;
  const setSelectedId = (value: string) => {
    updateWorkspaceQuery({ proposal: value, followup: null });
  };
  useEffect(() => { if (routeProposal) setOpened(true); }, [routeProposal]);
  const [previewFor, setPreviewFor] = useState("");
  const previewRequested = Boolean(selectedId) && previewFor === selectedId;
  const [previewOffset, setPreviewOffset] = useState(0);
  const [workOffset, setWorkOffset] = useState(0);
  const [saved, setSaved] = useState(false);
  const [refreshError, setRefreshError] = useState("");
  useEffect(() => {
    setReviewed(false);
  }, [snapshot]);
  const receipts = useQuery({
    queryKey: ["impact-inputs", sourceOffset],
    enabled: opened,
    queryFn: () =>
      request<Page<Receipt>>(`/api/intakes?offset=${sourceOffset}&limit=20`),
  });
  const history = useQuery({
    queryKey: ["change-proposals", clinicianId, locationId, historyOffset],
    enabled: opened,
    queryFn: () =>
      request<Page<Proposal>>(
        `/api/reconciliation/change-proposals?${new URLSearchParams({ clinician_id: clinicianId, ...(locationId ? { location_id: locationId } : {}), offset: String(historyOffset), limit: "20" })}`,
      ),
  });
  const detail = useQuery({
    queryKey: ["change-proposal", selectedId, clinicianId, locationId],
    enabled: opened && Boolean(selectedId),
    queryFn: async () => {
      const value = await request<Proposal>(`/api/reconciliation/change-proposals/${encodeURIComponent(selectedId)}`);
      if ((value.clinician_id !== undefined && value.clinician_id !== clinicianId) || (value.location_id !== undefined && value.location_id !== locationId)) throw new Error("The selected proposal belongs to a different clinician or practice location. Choose a proposal for this scope.");
      return value;
    },
  });
  const preview = useQuery({
    queryKey: ["impact-preview", selectedId, previewOffset, workOffset],
    enabled: opened && Boolean(selectedId) && detail.isSuccess && previewRequested,
    refetchOnWindowFocus: false,
    queryFn: () =>
      request<Impact>("/api/reconciliation/impact-preview", {
        proposal_id: selectedId,
        offset: previewOffset,
        work_offset: workOffset,
        limit: 20,
      }),
  });
  const mutation = useMutation({
    mutationFn: (body: ProposalRequest) =>
      request<Proposal>("/api/reconciliation/change-proposals", body),
    onMutate: () => actionGuard.capture(),
    onSuccess: async (proposal, _body, origin) => {
      client.setQueryData(["change-proposal", proposal.id, clinicianId, locationId], proposal);
      const invalidation = client.invalidateQueries({ queryKey: ["change-proposals", clinicianId, locationId] });
      if (!actionGuard.isCurrent(origin)) { await invalidation; return; }
      setPending(null);
      onPendingChange(false);
      setSaved(true);
      setSelectedId(proposal.id);
      setPreviewFor("");
      setPreviewOffset(0);
      setWorkOffset(0);
      setReason("");
      setReviewed(false);
      setRequiresRefresh(false);
      await invalidation;
    },
    onError: (error, _body, origin) => {
      if (!actionGuard.isCurrent(origin)) return;
      if (error instanceof ImpactError && error.status < 500) {
        setPending(null);
        onPendingChange(false);
        if (error.status === 409) {
          setRequiresRefresh(true);
          setReviewed(false);
        }
      }
    },
  });
  const locked =
    otherBusy || mutation.isPending || pending !== null || followUpPending;
  const selectedCount = Object.keys(selected).length;
  const staleSelection = receipts.data?.items.some(
    (receipt) =>
      selected[receipt.id] &&
      receipt.attempt_id !== selected[receipt.id].attempt_id,
  );
  const currentField = fields.find((item) => item.field === field);
  const currentDecision =
    currentField?.decision && !currentField.decision.stale;
  const valueReady =
    field === "phone"
      ? Boolean(text.trim())
      : field === "address"
        ? Boolean(
            address.line1.trim() &&
              address.city.trim() &&
              address.state.trim() &&
              address.zip.trim(),
          )
        : Boolean(field && text.trim());
  const canCreate =
    inputsFresh &&
    currentDecision &&
    !requiresRefresh &&
    !staleSelection &&
    !locked &&
    valueReady &&
    selectedCount >= 1 &&
    selectedCount <= 6 &&
    actor.trim() &&
    reason.trim() &&
    reviewed;
  const create = () => {
    if (pending) {
      mutation.mutate(pending);
      return;
    }
    if (!canCreate || !field) return;
    const value =
      field === "phone"
        ? { number: text, extension: extension === "" ? null : extension }
        : field === "address"
          ? {
              ...address,
              line2: address.line2 === "" ? null : address.line2,
              suite: address.suite === "" ? null : address.suite,
            }
          : text;
    const body: ProposalRequest = {
      clinician_id: clinicianId,
      location_id: locationId,
      field,
      proposed_value: value,
      inputs: Object.values(selected),
      expected_snapshot: snapshot,
      request_id: crypto.randomUUID(),
      actor: actor.trim(),
      reason: reason.trim(),
    };
    setSaved(false);
    setPending(body);
    onPendingChange(true);
    mutation.mutate(body);
  };
  const refresh = async () => {
    setReviewed(false);
    setRefreshError("");
    try {
      await onRefresh();
      const result = await receipts.refetch();
      if (result.isError) throw result.error;
      setRequiresRefresh(false);
      mutation.reset();
    } catch (error) {
      setRefreshError(
        error instanceof Error
          ? error.message
          : "Unable to refresh proposal evidence",
      );
    }
  };
  if (!opened)
    return (
      <section
        style={{
          borderTop: "1px solid #d7e3df",
          marginTop: "24px",
          paddingTop: "18px",
        }}
      >
        <h3>Provider-change impact preview</h3>
        <p>
          Propose a reviewed field change and assess explicitly selected
          listings and existing work. Unlinked evidence stays visible as not
          assessed.
        </p>
        <button disabled={otherBusy} onClick={() => setOpened(true)}>
          Open change impact preview
        </button>
      </section>
    );
  return (
    <section
      aria-label="Provider-change impact preview"
      style={{
        borderTop: "1px solid #d7e3df",
        marginTop: "24px",
        paddingTop: "18px",
        minWidth: 0,
      }}
    >
      <h3>Provider-change impact preview</h3>
      <p>
        Preview only: no cases are created, source listings are unchanged, and
        external directories are not contacted.
      </p>
      <fieldset
        disabled={locked}
        style={{ border: "1px solid #d7e3df", padding: "16px", minWidth: 0 }}
      >
        <legend>Propose a scoped field change</legend>
        <label>
          Proposed field
          <select
            aria-label="Proposed field"
            value={field}
            onChange={(event) => {
              setField(event.target.value as FieldName | "");
              setText("");
              setExtension("");
              setAddress({
                line1: "",
                line2: "",
                suite: "",
                city: "",
                state: "",
                zip: "",
              });
              setReviewed(false);
            }}
          >
            <option value="">Choose a reviewed field</option>
            {fields.map((item) => (
              <option key={item.field} value={item.field}>
                {human(item.field)}
              </option>
            ))}
          </select>
        </label>
        {field && !currentDecision && (
          <p className="rc-warning">
            Record a current source selection or retained-conflict decision for
            this field before proposing a change.
          </p>
        )}
        {currentField?.decision && (
          <details>
            <summary>Prior reviewed {human(field)} evidence</summary>
            <p>
              {currentField.decision.decision === "conflict"
                ? "Explicit retained conflict"
                : "Selected source assertion"}{" "}
              · Decision <code>{currentField.decision.id}</code>
            </p>
            <pre>{show(currentField.decision.value)}</pre>
          </details>
        )}
        {field === "phone" ? (
          <div className="rc-create">
            <label>
              Proposed phone number
              <input
                aria-label="Proposed phone number"
                value={text}
                onChange={(event) => setText(event.target.value)}
              />
            </label>
            <label>
              Proposed phone extension
              <input
                aria-label="Proposed phone extension"
                value={extension}
                onChange={(event) => setExtension(event.target.value)}
                placeholder="Optional; blank means null"
              />
            </label>
          </div>
        ) : field === "address" ? (
          <>
            <p>
              Enter one coherent proposed address. Line 2 and suite remain
              explicit.
            </p>
            <div className="rc-create">
              {(
                ["line1", "line2", "suite", "city", "state", "zip"] as const
              ).map((component) => (
                <label key={component}>
                  Proposed address {component}
                  <input
                    aria-label={`Proposed address ${component}`}
                    value={address[component]}
                    onChange={(event) =>
                      setAddress((current) => ({
                        ...current,
                        [component]: event.target.value,
                      }))
                    }
                  />
                </label>
              ))}
            </div>
          </>
        ) : (
          field && (
            <label>
              Proposed {human(field)}
              <input
                aria-label={`Proposed ${human(field)}`}
                value={text}
                onChange={(event) => setText(event.target.value)}
                inputMode={field === "npi" ? "numeric" : undefined}
              />
            </label>
          )
        )}
        <h4>Select retained assessment inputs</h4>
        <p>
          Choose 1–6 parsed deliveries explicitly, including listings that may
          not have reviewed links. {selectedCount} selected.
        </p>
        {receipts.isFetching && (
          <p role="status">Loading retained assessment inputs…</p>
        )}
        {receipts.error && (
          <p className="rc-error" role="alert">
            {receipts.error.message}
          </p>
        )}
        {receipts.data && !receipts.data.items.length && (
          <p>No retained deliveries on this page.</p>
        )}
        {receipts.data?.items.map((receipt) => (
          <div key={receipt.id} className="rc-source">
            <label
              style={{ flexDirection: "row", alignItems: "start", gap: "8px" }}
            >
              <input
                type="checkbox"
                aria-label={`Assess delivery ${receipt.label ?? receipt.id}`}
                checked={Boolean(selected[receipt.id])}
                disabled={
                  !receipt.attempt_id ||
                  ["failed", "processing", "interrupted", "rejected"].includes(
                    receipt.state ?? "",
                  ) ||
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
                  setReviewed(false);
                }}
              />
              <span>
                <strong>{receipt.label ?? receipt.id}</strong>
                <span className="rc-reference" style={{ display: "block" }}>
                  {receipt.source} · {receipt.profile} · {receipt.state} ·{" "}
                  {receipt.designation}
                </span>
              </span>
            </label>
            {selected[receipt.id] && (
              <>
                <label>
                  Assessment entity type for {receipt.label ?? receipt.id}
                  <select
                    aria-label={`Assessment entity type for ${receipt.label ?? receipt.id}`}
                    value={selected[receipt.id].entity_kind}
                    onChange={(event) => {
                      setSelected((current) => ({
                        ...current,
                        [receipt.id]: {
                          ...current[receipt.id],
                          entity_kind: event.target
                            .value as Input["entity_kind"],
                        },
                      }));
                      setReviewed(false);
                    }}
                  >
                    <option value="unknown">
                      Unknown unless supported by source evidence
                    </option>
                    <option value="clinician">Clinician</option>
                    <option value="organization">Organization</option>
                  </select>
                </label>
                {selected[receipt.id].attempt_id !== receipt.attempt_id && (
                  <button
                    onClick={() => {
                      setSelected((current) => ({
                        ...current,
                        [receipt.id]: {
                          ...current[receipt.id],
                          attempt_id: receipt.attempt_id!,
                        },
                      }));
                      setReviewed(false);
                    }}
                  >
                    Use latest assessment interpretation
                  </button>
                )}
              </>
            )}
          </div>
        ))}
        {receipts.data && (
          <Pages
            label="Assessment input pages"
            offset={sourceOffset}
            next={receipts.data.next_offset ?? null}
            locked={locked || receipts.isFetching}
            onChange={setSourceOffset}
          />
        )}
        <details>
          <summary>Selected assessment references · {selectedCount}</summary>
          <pre>{show(Object.values(selected))}</pre>
        </details>
        <div className="rc-create">
          <label>
            Proposal actor
            <input
              aria-label="Proposal actor"
              value={actor}
              onChange={(event) => setActor(event.target.value)}
            />
          </label>
          <label>
            Proposal reason
            <textarea
              aria-label="Proposal reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              rows={3}
            />
          </label>
        </div>
        <label
          style={{
            flexDirection: "row",
            alignItems: "start",
            gap: "8px",
            marginTop: "14px",
          }}
        >
          <input
            type="checkbox"
            aria-label="I reviewed the prior field and assessment inputs"
            checked={reviewed}
            onChange={(event) => setReviewed(event.target.checked)}
          />
          I reviewed the prior field evidence and selected assessment inputs.
        </label>
      </fieldset>
      {!inputsFresh && (
        <p className="rc-warning" role="alert">
          The reconciled source dependencies need renewed review. A new proposal
          requires current field evidence.
        </p>
      )}
      {staleSelection && (
        <p className="rc-warning" role="alert">
          A selected assessment interpretation changed. Inspect and explicitly
          choose its latest interpretation.
        </p>
      )}
      {requiresRefresh && (
        <p className="rc-warning" role="alert">
          The field snapshot or assessment inputs changed. Refresh and review
          the proposal evidence again.
        </p>
      )}
      {mutation.error && (
        <p className="rc-error" role="alert">
          {mutation.error.message}
        </p>
      )}
      {refreshError && (
        <p className="rc-error" role="alert">
          {refreshError}
        </p>
      )}
      {pending && mutation.isError && (
        <p role="status">
          The proposal result is unconfirmed. Retry sends the identical request
          ID and payload.
        </p>
      )}
      {saved && (
        <p role="status">
          Change proposal saved. Run the read-only impact preview separately.
        </p>
      )}
      <div className="rc-filters">
        <button
          disabled={pending ? mutation.isPending || otherBusy : !canCreate}
          onClick={create}
        >
          {mutation.isPending
            ? "Saving change proposal…"
            : pending
              ? "Retry same change proposal"
              : "Save change proposal"}
        </button>
        <button disabled={locked} onClick={() => void refresh()}>
          Refresh proposal evidence
        </button>
      </div>
      <h4>Saved change proposals</h4>
      {history.isFetching && (
        <p role="status">Loading change proposal history…</p>
      )}
      {history.error && (
        <p className="rc-error" role="alert">
          {history.error.message}
        </p>
      )}
      <label>
        Saved change proposal
        <select
          aria-label="Saved change proposal"
          value={selectedId}
          disabled={locked}
          onChange={(event) => {
            setSelectedId(event.target.value);
            setPreviewFor("");
            setPreviewOffset(0);
            setWorkOffset(0);
          }}
        >
          <option value="">Choose a saved proposal</option>
          {detail.data &&
            !history.data?.items.some((item) => item.id === selectedId) && (
              <option value={selectedId}>
                {detail.data.field} · {selectedId}
              </option>
            )}
          {history.data?.items.map((item) => (
            <option key={item.id} value={item.id}>
              {human(item.field)} · {item.actor} · {item.created_at} · {item.id}
            </option>
          ))}
        </select>
      </label>
      {history.data && (
        <>
          <p>{history.data.total} proposals in this identity scope.</p>
          <Pages
            label="Change proposal history pages"
            offset={historyOffset}
            next={history.data.next_offset}
            locked={locked || history.isFetching}
            onChange={setHistoryOffset}
          />
        </>
      )}
      {detail.isFetching && selectedId && (
        <p role="status">Loading pinned change proposal…</p>
      )}
      {detail.error && (
        <p className="rc-error" role="alert">
          {detail.error.message}
        </p>
      )}
      {detail.data && (
        <>
          <h4>Proposed {human(detail.data.field)}</h4>
          <pre>{show(detail.data.proposed_value)}</pre>
          <p>
            {detail.data.actor}: {detail.data.reason} · {detail.data.created_at}
          </p>
          <details>
            <summary>Prior evidence and pinned proposal inputs</summary>
            <pre>
              {show({
                original_proposal: detail.data.proposed_original,
                prior_evidence: detail.data.prior_evidence,
                inputs: detail.data.inputs,
              })}
            </pre>
          </details>
          <button
            disabled={locked || preview.isFetching}
            onClick={() => {
              if (previewRequested) void preview.refetch();
              else setPreviewFor(selectedId);
            }}
          >
            Run read-only impact preview
          </button>
        </>
      )}
      {preview.isFetching && previewRequested && (
        <p role="status">Assessing selected listings and existing work…</p>
      )}
      {preview.error && previewRequested && (
        <p className="rc-error" role="alert">
          {preview.error.message}
        </p>
      )}
      {preview.data && previewRequested && (
        <section aria-label="Impact assessment results">
          <p className="rc-reference">
            Assessment snapshot <code>{preview.data.snapshot}</code>
          </p>
          {!preview.data.inputs_fresh && (
            <div role="alert" className="rc-warning">
              <strong>This proposal preview is stale.</strong>
              <ul>
                {preview.data.stale_reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              <p>
                Review current field and link evidence, then create a renewed
                proposal.
              </p>
            </div>
          )}
          <p>{preview.data.scope_notice}</p>
          <Coverage title="Listing coverage" counts={preview.data.counts} />
          <Coverage
            title="Existing work coverage"
            counts={preview.data.work_counts}
          />
          <h4>{preview.data.total} selected listing references</h4>
          <div
            className="rc-scroll"
            tabIndex={0}
            role="region"
            aria-label="Listing impact evidence"
          >
            <table>
              <thead>
                <tr>
                  <th>Source / network</th>
                  <th>Assessment</th>
                  <th>Source value / comparison</th>
                </tr>
              </thead>
              <tbody>
                {preview.data.targets.map((target) => (
                  <tr key={target.ref}>
                    <th
                      scope="row"
                      style={{
                        textTransform: "none",
                        letterSpacing: "normal",
                        fontWeight: 400,
                      }}
                    >
                      <strong>{target.source}</strong>
                      {(target.network_id || target.network_label) && (
                        <p>
                          Network {target.network_label ?? "Unlabeled"} ·{" "}
                          {target.network_id}
                        </p>
                      )}
                      <details>
                        <summary>Target provenance</summary>
                        <pre>
                          {show({
                            ref: target.ref,
                            receipt_id: target.receipt_id,
                            attempt_id: target.attempt_id,
                            locator: target.locator,
                            address_path: target.address_path,
                            clinician_link: target.clinician_link,
                            location_link: target.location_link,
                          })}
                        </pre>
                      </details>
                    </th>
                    <td>
                      <strong>{human(target.classification)}</strong>
                      <p>{target.reason}</p>
                    </td>
                    <td>
                      <pre>{show(target.value)}</pre>
                      <details>
                        <summary>Comparison value</summary>
                        <pre>{show(target.comparison_value)}</pre>
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!preview.data.targets.length && (
            <p>No listing references on this page.</p>
          )}
          <h4>{preview.data.work_total} existing work records</h4>
          {!preview.data.existing_work.length ? (
            <p>No existing work records on this page. Preview creates none.</p>
          ) : (
            <div
              className="rc-scroll"
              tabIndex={0}
              role="region"
              aria-label="Existing work impact evidence"
            >
              <table>
                <thead>
                  <tr>
                    <th>Existing case</th>
                    <th>Work state</th>
                    <th>Assessment</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.data.existing_work.map((work) => (
                    <tr key={work.id}>
                      <th scope="row">
                        <code>{work.id}</code>
                        <p>{human(work.field_name)}</p>
                      </th>
                      <td>
                        {human(work.status)} · Owner{" "}
                        {work.owner ?? "Unassigned"} · Version {work.version}
                      </td>
                      <td>
                        {human(work.classification)}
                        <p>{work.reason}</p>
                        <details>
                          <summary>Work source references</summary>
                          <pre>{show(work.refs)}</pre>
                        </details>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p>
            Coverage counts describe all selected evidence. Listing and
            existing-work evidence have independent pages; unlinked records stay
            not assessed.
          </p>
          <Pages
            label="Impact listing pages"
            offset={previewOffset}
            next={preview.data.next_offset}
            locked={locked || preview.isFetching}
            onChange={setPreviewOffset}
          />
          <Pages
            label="Impact existing work pages"
            offset={workOffset}
            next={preview.data.work_next_offset}
            locked={locked || preview.isFetching}
            onChange={setWorkOffset}
          />

        </section>
      )}
      {detail.isSuccess && selectedId && ((preview.data && previewRequested) || route.get("followup")) && (
          <FollowUpPlan
            key={selectedId}
            proposalId={selectedId}
            otherBusy={
              otherBusy ||
              mutation.isPending ||
              pending !== null ||
              preview.isFetching
            }
            onPendingChange={(value) => {
              setFollowUpPending(value);
              onPendingChange(value);
            }}
          />
      )}
    </section>
  );
}
