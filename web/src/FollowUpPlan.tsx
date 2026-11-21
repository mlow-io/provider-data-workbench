import { useWorkspaceQuery, updateWorkspaceQuery, workspaceHref, useWorkspaceActionGuard } from "./workspaceNavigation";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type Page<T> = { items: T[]; total: number; next_offset: number | null };
type Counts = Record<string, number>;
type Case = {
  id: string;
  owner: string | null;
  status: string;
  version: number;
  kind?: string;
  field_name: string;
  proposal?: unknown;
  observed?: unknown;
  eligible_for_reuse?: boolean;
};
type Ack = {
  id: string;
  actor: string;
  reason: string;
  created_at: string;
  case_version: number;
};
type Action = {
  target_key: string;
  refs: string[];
  source: string;
  network_id?: string | null;
  network_label?: string | null;
  field: string;
  action: "create" | "reuse" | "blocked";
  case_id: string | null;
  case_version: number | null;
  available_cases: Case[];
  reason: string;
};
type Preview = {
  proposal_id: string;
  impact_snapshot: string;
  plan_snapshot: string;
  inputs_fresh: boolean;
  stale_reasons: string[];
  counts: Counts;
  actions: Action[];
  total: number;
  next_offset: number | null;
  blocked_count: number;
};
type Summary = {
  id: string;
  proposal_id: string;
  actor: string;
  reason: string;
  created_at: string;
};
type Target = {
  association_id: string;
  target_key: string;
  refs: string[];
  source: string;
  network_id?: string | null;
  network_label?: string | null;
  field: string;
  action: "create" | "reuse";
  case: Case;
  latest_ack: Ack | null;
  ack_count: number;
};
type Receipt = Summary & {
  snapshot: string;
  scope: unknown;
  counts: Counts;
  source_inputs_fresh: boolean;
  source_stale_reasons: string[];
  targets: Target[];
  total: number;
  next_offset: number | null;
};
type ConfirmBody = {
  proposal_id: string;
  expected_snapshot: string;
  expected_plan: string;
  case_choices: Record<string, string>;
  request_id: string;
  actor: string;
  reason: string;
  confirm: true;
};
type AckBody = {
  association_id: string;
  expected_ack_id: string | null;
  expected_case_version: number;
  request_id: string;
  actor: string;
  reason: string;
};
class PlanError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}
async function checked(response: Response) {
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new PlanError(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail ?? `Request failed (${response.status})`),
      response.status,
    );
  }
  return response;
}
async function request<T>(path: string, body?: unknown): Promise<T> {
  return (
    await checked(
      await fetch(
        path,
        body === undefined
          ? undefined
          : {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(body),
            },
      ),
    )
  ).json() as Promise<T>;
}
const human = (text: string) => text.replaceAll("_", " ");
const show = (value: unknown) => JSON.stringify(value, null, 2);
function Pages({
  offset,
  next,
  label,
  disabled,
  onChange,
}: {
  offset: number;
  next: number | null;
  label: string;
  disabled: boolean;
  onChange: (offset: number) => void;
}) {
  return (
    <div className="rc-pager" role="group" aria-label={label}>
      <button
        disabled={disabled || offset === 0}
        onClick={() => onChange(Math.max(0, offset - 20))}
      >
        Previous
      </button>
      <span>From {offset + 1}</span>
      <button
        disabled={disabled || next === null}
        onClick={() => next !== null && onChange(next)}
      >
        Next
      </button>
    </div>
  );
}
function Metrics({ counts }: { counts: Counts }) {
  return (
    <div className="rc-run-summary">
      {Object.entries(counts).map(([name, count]) => (
        <span key={name}>
          <b>{count}</b> {human(name)}
        </span>
      ))}
    </div>
  );
}
function Acknowledgement({
  receiptId,
  target,
  otherBusy,
  onPending,
  onRefresh,
}: {
  receiptId: string;
  target: Target;
  otherBusy: boolean;
  onPending: (id: string | null) => void;
  onRefresh: () => Promise<void>;
}) {
  const client = useQueryClient();
  const [actor, setActor] = useState("");
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState<AckBody | null>(null);
  const [requiresRefresh, setRequiresRefresh] = useState(false);
  const [saved, setSaved] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const [refreshError, setRefreshError] = useState("");
  const history = useQuery({
    queryKey: ["follow-up-acks", receiptId, target.association_id, offset],
    enabled: historyOpen,
    refetchOnWindowFocus: false,
    queryFn: () =>
      request<Page<Ack>>(
        `/api/reconciliation/follow-up/${encodeURIComponent(receiptId)}/acknowledgements?${new URLSearchParams({ association_id: target.association_id, offset: String(offset), limit: "20" })}`,
      ),
  });
  const mutation = useMutation({
    mutationFn: (body: AckBody) =>
      request<Ack>(
        `/api/reconciliation/follow-up/${encodeURIComponent(receiptId)}/acknowledge`,
        body,
      ),
    onSuccess: async () => {
      setPending(null);
      onPending(null);
      setSaved(true);
      setReason("");
      setRequiresRefresh(false);
      await Promise.all([
        client.invalidateQueries({
          queryKey: ["follow-up-receipt", receiptId],
        }),
        client.invalidateQueries({
          queryKey: ["follow-up-acks", receiptId, target.association_id],
        }),
      ]);
    },
    onError: (error) => {
      if (error instanceof PlanError && error.status < 500) {
        setPending(null);
        onPending(null);
        if (error.status === 409) setRequiresRefresh(true);
      }
    },
  });
  const locked = otherBusy || mutation.isPending || pending !== null;
  const submit = () => {
    if (pending) {
      mutation.mutate(pending);
      return;
    }
    if (locked || requiresRefresh || !actor.trim() || !reason.trim()) return;
    const body: AckBody = {
      association_id: target.association_id,
      expected_ack_id: target.latest_ack?.id ?? null,
      expected_case_version: target.case.version,
      request_id: crypto.randomUUID(),
      actor: actor.trim(),
      reason: reason.trim(),
    };
    setSaved(false);
    setPending(body);
    onPending(target.association_id);
    mutation.mutate(body);
  };
  return (
    <section aria-label={`Acknowledgement for ${target.case.id}`}>
      <h4>Acknowledge receipt of this follow-up</h4>
      <p>
        Acknowledgement records receipt only. It does not verify the proposed
        correction, close the case or change its owner/status.
      </p>
      {target.latest_ack ? (
        <p>
          Latest acknowledgement: {target.latest_ack.actor}:{" "}
          {target.latest_ack.reason} · {target.latest_ack.created_at} · At case
          version {target.latest_ack.case_version}
        </p>
      ) : (
        <p>No acknowledgement recorded.</p>
      )}
      <fieldset
        disabled={locked}
        style={{ minWidth: 0, border: "1px solid #d7e3df", padding: "14px" }}
      >
        <legend>Record receipt acknowledgement</legend>
        <div className="rc-create">
          <label>
            Acknowledgement actor
            <input
              aria-label="Acknowledgement actor"
              value={actor}
              onChange={(event) => setActor(event.target.value)}
            />
          </label>
          <label>
            Acknowledgement reason
            <textarea
              aria-label="Acknowledgement reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              rows={2}
            />
          </label>
        </div>
      </fieldset>
      {requiresRefresh && (
        <p className="rc-warning" role="alert">
          Acknowledgement or case state changed. Refresh the saved receipt and
          inspect the current case version before acknowledging.
        </p>
      )}
      {requiresRefresh && (
        <button
          disabled={locked}
          onClick={async () => {
            setRefreshError("");
            try {
              await onRefresh();
              setRequiresRefresh(false);
              mutation.reset();
            } catch (error) {
              setRefreshError(
                error instanceof Error
                  ? error.message
                  : "Unable to refresh acknowledgement context",
              );
            }
          }}
        >
          Refresh acknowledgement context
        </button>
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
          Acknowledgement outcome is unconfirmed. Retry sends the identical
          request ID and payload.
        </p>
      )}
      {saved && (
        <p role="status">
          Receipt acknowledgement saved. Verification and case state were not
          changed.
        </p>
      )}
      <button
        disabled={
          pending
            ? mutation.isPending || otherBusy
            : locked || requiresRefresh || !actor.trim() || !reason.trim()
        }
        onClick={submit}
      >
        {mutation.isPending
          ? "Saving acknowledgement…"
          : pending
            ? "Retry same acknowledgement"
            : "Record acknowledgement"}
      </button>
      <details
        onToggle={(event) => {
          if (event.currentTarget.open) setHistoryOpen(true);
        }}
      >
        <summary>Acknowledgement history · {target.ack_count}</summary>
        {history.isFetching && (
          <p role="status">Loading acknowledgement history…</p>
        )}
        {history.error && (
          <>
            <p className="rc-error" role="alert">
              {history.error.message}
            </p>
            <button disabled={locked} onClick={() => void history.refetch()}>
              Retry acknowledgement history
            </button>
          </>
        )}
        {history.data && (
          <>
            <p>{history.data.total} recorded acknowledgements</p>
            <ol className="history">
              {history.data.items.map((ack) => (
                <li key={ack.id}>
                  <span>
                    {ack.actor}: {ack.reason}
                  </span>
                  <small>At case version {ack.case_version}</small>
                  <time>{ack.created_at}</time>
                </li>
              ))}
            </ol>
            <Pages
              offset={offset}
              next={history.data.next_offset}
              label={`Acknowledgement history for ${target.case.id}`}
              disabled={locked || history.isFetching}
              onChange={setOffset}
            />
          </>
        )}
      </details>
    </section>
  );
}
export function FollowUpPlan({
  proposalId,
  otherBusy,
  onPendingChange,
}: {
  proposalId: string;
  otherBusy: boolean;
  onPendingChange: (pending: boolean) => void;
}) {
  const client = useQueryClient();
  const route = useWorkspaceQuery();
  const actionGuard = useWorkspaceActionGuard();
  const routeReceipt = route.get("followup") ?? "";
  const [opened, setOpened] = useState(Boolean(routeReceipt));
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [previewRequested, setPreviewRequested] = useState(false);
  const [previewOffset, setPreviewOffset] = useState(0);
  const [actor, setActor] = useState("");
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [requiresRefresh, setRequiresRefresh] = useState(false);
  const [pending, setPending] = useState<ConfirmBody | null>(null);
  const [pendingAck, setPendingAck] = useState<string | null>(null);
  const receiptId = routeReceipt;
  const setReceiptId = (value: string) => { updateWorkspaceQuery({ followup: value }); };
  useEffect(() => { if (routeReceipt) setOpened(true); }, [routeReceipt]);
  const [listOffset, setListOffset] = useState(0);
  const [receiptOffset, setReceiptOffset] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const history = useQuery({
    queryKey: ["follow-up-history", proposalId, listOffset],
    enabled: opened,
    refetchOnWindowFocus: false,
    queryFn: () =>
      request<Page<Summary>>(
        `/api/reconciliation/follow-up?${new URLSearchParams({ proposal_id: proposalId, offset: String(listOffset), limit: "20" })}`,
      ),
  });
  const preview = useQuery({
    queryKey: ["follow-up-preview", proposalId, choices, previewOffset],
    enabled:
      opened &&
      history.isSuccess &&
      history.data.total === 0 &&
      previewRequested,
    refetchOnWindowFocus: false,
    queryFn: () =>
      request<Preview>("/api/reconciliation/follow-up-preview", {
        proposal_id: proposalId,
        case_choices: choices,
        offset: previewOffset,
        limit: 20,
      }),
  });
  const receipt = useQuery({
    queryKey: ["follow-up-receipt", receiptId, proposalId, receiptOffset],
    enabled: opened && Boolean(receiptId),
    refetchOnWindowFocus: false,
    queryFn: async () => {
      const value = await request<Receipt>(`/api/reconciliation/follow-up/${encodeURIComponent(receiptId)}?offset=${receiptOffset}&limit=20`);
      if (value.proposal_id !== proposalId) throw new Error("This follow-up receipt belongs to another change proposal. Select a receipt for this proposal.");
      return value;
    },
  });
  useEffect(() => {
    if (!receiptId && !pending && !pendingAck && history.data?.items[0])
      setReceiptId(history.data.items[0].id);
  }, [history.data, receiptId, pending, pendingAck]);
  useEffect(() => {
    setConfirmed(false);
  }, [preview.data?.plan_snapshot]);
  const mutation = useMutation({
    mutationFn: (body: ConfirmBody) =>
      request<Summary>("/api/reconciliation/follow-up", body),
    onMutate: () => actionGuard.capture(),
    onSuccess: async (saved, _body, origin) => {
      const invalidation = Promise.all([
        client.invalidateQueries({ queryKey: ["follow-up-history", proposalId] }),
        client.invalidateQueries({ queryKey: ["impact-preview", proposalId] }),
      ]);
      if (!actionGuard.isCurrent(origin)) { await invalidation; return; }
      setPending(null);
      onPendingChange(false);
      setConfirmed(false);
      setReason("");
      setRequiresRefresh(false);
      setReceiptId(saved.id);
      setReceiptOffset(0);
      setPreviewRequested(false);
      await invalidation;
    },
    onError: (error, _body, origin) => {
      if (!actionGuard.isCurrent(origin)) return;
      if (error instanceof PlanError && error.status < 500) {
        setPending(null);
        onPendingChange(false);
        if (error.status === 409) {
          setRequiresRefresh(true);
          setConfirmed(false);
        }
      }
    },
  });
  const locked =
    otherBusy ||
    mutation.isPending ||
    pending !== null ||
    pendingAck !== null ||
    exporting;
  const canConfirm =
    history.isSuccess &&
    history.data.total === 0 &&
    !receiptId &&
    preview.data?.inputs_fresh &&
    preview.data.blocked_count === 0 &&
    !preview.isFetching &&
    !requiresRefresh &&
    !locked &&
    confirmed &&
    actor.trim() &&
    reason.trim();
  const confirm = () => {
    if (pending) {
      mutation.mutate(pending);
      return;
    }
    if (!canConfirm || !preview.data) return;
    const body: ConfirmBody = {
      proposal_id: proposalId,
      expected_snapshot: preview.data.impact_snapshot,
      expected_plan: preview.data.plan_snapshot,
      case_choices: choices,
      request_id: crypto.randomUUID(),
      actor: actor.trim(),
      reason: reason.trim(),
      confirm: true,
    };
    setPending(body);
    onPendingChange(true);
    mutation.mutate(body);
  };
  const setAckPending = (id: string | null) => {
    setPendingAck(id);
    onPendingChange(id !== null);
  };
  const refreshReceipt = async () => {
    const result = await receipt.refetch();
    if (result.isError) throw result.error;
  };
  const refreshPreview = async () => {
    setConfirmed(false);
    const result = await preview.refetch();
    if (result.isSuccess) {
      setRequiresRefresh(false);
      mutation.reset();
    }
  };
  const download = async (format: "json" | "xlsx") => {
    if (!receipt.data) return;
    setExporting(true);
    setExportError("");
    try {
      const response = await checked(
        await fetch(
          `/api/reconciliation/follow-up/${encodeURIComponent(receiptId)}/export?${new URLSearchParams({ expected_snapshot: receipt.data.snapshot, format })}`,
        ),
      );
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `follow-up-${receiptId}.${format}`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setExportError(
        error instanceof Error
          ? error.message
          : "Unable to export saved follow-up receipt",
      );
    } finally {
      setExporting(false);
    }
  };
  if (!opened)
    return (
      <section
        style={{
          borderTop: "1px solid #d7e3df",
          paddingTop: "18px",
          marginTop: "20px",
        }}
      >
        <h4>Bounded follow-up plan</h4>
        <p>
          Preview exact review-case actions, then confirm explicitly. Existing
          case ownership and status are preserved.
        </p>
        <button disabled={otherBusy} onClick={() => setOpened(true)}>
          Review follow-up plan
        </button>
      </section>
    );
  return (
    <section
      aria-label="Bounded follow-up plan"
      style={{
        borderTop: "1px solid #d7e3df",
        paddingTop: "18px",
        marginTop: "20px",
        minWidth: 0,
      }}
    >
      <h4>Bounded follow-up plan</h4>
      <p>
        New tasks request review. Acknowledgement records receipt and does not
        verify a correction.
      </p>
      {history.isFetching && (
        <p role="status">Checking saved follow-up confirmations…</p>
      )}
      {history.error && (
        <>
          <p className="rc-error" role="alert">
            {history.error.message}
          </p>
          <button disabled={locked} onClick={() => void history.refetch()}>
            Retry saved confirmation lookup
          </button>
        </>
      )}
      {history.data && history.data.total > 0 && (
        <>
          <p>
            A follow-up confirmation already exists for this immutable proposal.
            Inspect its saved receipt; a different plan requires a new proposal
            revision.
          </p>
          <label>
            Saved follow-up confirmation
            <select
              aria-label="Saved follow-up confirmation"
              value={receiptId}
              disabled={locked}
              onChange={(event) => {
                setReceiptId(event.target.value);
                setReceiptOffset(0);
              }}
            >
              <option value="">Choose a saved confirmation</option>
              {history.data.items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.actor} · {item.created_at} · {item.id}
                </option>
              ))}
            </select>
          </label>
          <Pages
            offset={listOffset}
            next={history.data.next_offset}
            label="Saved follow-up confirmation pages"
            disabled={locked || history.isFetching}
            onChange={setListOffset}
          />
        </>
      )}
      {history.isSuccess && history.data.total === 0 && !receiptId && (
        <>
          <button
            disabled={locked || preview.isFetching}
            onClick={() => {
              if (previewRequested) void refreshPreview();
              else setPreviewRequested(true);
            }}
          >
            Preview follow-up actions
          </button>
          {preview.isFetching && (
            <p role="status">Evaluating the complete follow-up action plan…</p>
          )}
          {preview.error && (
            <>
              <p className="rc-error" role="alert">
                {preview.error.message}
              </p>
              <button
                disabled={locked}
                onClick={() => {
                  setConfirmed(false);
                  if (Object.keys(choices).length) setChoices({});
                  else void preview.refetch();
                }}
              >
                Reset case choices and preview
              </button>
            </>
          )}
          {preview.data && (
            <>
              <p>
                {preview.data.total} deduplicated follow-up targets ·{" "}
                {preview.data.blocked_count} blocked
              </p>
              <Metrics counts={preview.data.counts} />
              <p className="rc-reference">
                Impact snapshot <code>{preview.data.impact_snapshot}</code> ·
                Plan snapshot <code>{preview.data.plan_snapshot}</code>
              </p>
              {!preview.data.inputs_fresh && (
                <div className="rc-warning" role="alert">
                  <strong>Follow-up dependencies are stale.</strong>
                  <ul>
                    {preview.data.stale_reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                </div>
              )}
              {preview.data.actions.map((action) => (
                <section
                  key={action.target_key}
                  aria-label={`Follow-up action ${action.target_key}`}
                  style={{
                    borderTop: "1px solid #d7e3df",
                    paddingTop: "14px",
                    marginTop: "16px",
                  }}
                >
                  <h4>
                    {action.source}
                    {(action.network_id || action.network_label) && (
                      <> · {action.network_label ?? action.network_id}</>
                    )}
                  </h4>
                  <p>
                    <strong>{human(action.action)}</strong> ·{" "}
                    {human(action.field)} · {action.reason}
                  </p>
                  {action.case_id && (
                    <p>
                      Existing case <code>{action.case_id}</code> · Version{" "}
                      {action.case_version}
                    </p>
                  )}
                  {action.case_id &&
                    action.available_cases
                      .filter((item) => item.id === action.case_id)
                      .map((item) => (
                        <p key={item.id}>
                          Current owner {item.owner ?? "Unassigned"} · Work
                          state {human(item.status)} · Existing proposal remains
                          unchanged.
                        </p>
                      ))}
                  <label>
                    Case choice for this target
                    <select
                      aria-label={`Case choice for ${action.target_key}`}
                      disabled={locked || preview.isFetching}
                      value={choices[action.target_key] ?? ""}
                      onChange={(event) => {
                        setChoices((current) => {
                          const next = { ...current };
                          if (event.target.value)
                            next[action.target_key] = event.target.value;
                          else delete next[action.target_key];
                          return next;
                        });
                        setConfirmed(false);
                      }}
                    >
                      <option value="">Use the assessed default</option>
                      <option
                        value="new"
                        disabled={action.available_cases.some(
                          (item) => item.eligible_for_reuse !== false,
                        )}
                      >
                        Create a new QA review case
                      </option>
                      {action.available_cases.map((item) => (
                        <option
                          key={item.id}
                          value={item.id}
                          disabled={item.eligible_for_reuse === false}
                        >
                          {item.id} · {item.owner ?? "Unassigned"} ·{" "}
                          {human(item.status)} · v{item.version}
                          {item.eligible_for_reuse === false
                            ? " · unavailable for reuse"
                            : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                  <details>
                    <summary>Target and existing-case provenance</summary>
                    <pre>
                      {show({
                        target_key: action.target_key,
                        refs: action.refs,
                        network_id: action.network_id,
                        available_cases: action.available_cases,
                      })}
                    </pre>
                  </details>
                </section>
              ))}
              <Pages
                offset={previewOffset}
                next={preview.data.next_offset}
                label="Follow-up action pages"
                disabled={locked || preview.isFetching}
                onChange={(offset) => {
                  setPreviewOffset(offset);
                  setConfirmed(false);
                }}
              />
              <fieldset
                disabled={locked || preview.isFetching}
                style={{
                  minWidth: 0,
                  border: "1px solid #d7e3df",
                  padding: "14px",
                }}
              >
                <legend>Confirm the exact bounded plan</legend>
                <div className="rc-create">
                  <label>
                    Follow-up actor
                    <input
                      aria-label="Follow-up actor"
                      value={actor}
                      onChange={(event) => setActor(event.target.value)}
                    />
                  </label>
                  <label>
                    Follow-up reason
                    <textarea
                      aria-label="Follow-up reason"
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
                    aria-label="I confirm this bounded review-case plan"
                    checked={confirmed}
                    onChange={(event) => setConfirmed(event.target.checked)}
                  />
                  I confirm this exact review-case plan and its create/reuse
                  choices.
                </label>
              </fieldset>
              {requiresRefresh && (
                <p className="rc-warning" role="alert">
                  The impact or work-case plan changed. Preview the actions
                  again and inspect the current case versions before confirming.
                </p>
              )}
              {mutation.error && (
                <p className="rc-error" role="alert">
                  {mutation.error.message}
                </p>
              )}
              {pending && mutation.isError && (
                <p role="status">
                  Confirmation outcome is unconfirmed. Retry sends the identical
                  request ID and plan.
                </p>
              )}
              <button
                disabled={
                  pending ? mutation.isPending || otherBusy : !canConfirm
                }
                onClick={confirm}
              >
                {mutation.isPending
                  ? "Confirming follow-up plan…"
                  : pending
                    ? "Retry same follow-up confirmation"
                    : "Confirm follow-up plan"}
              </button>
            </>
          )}
        </>
      )}
      {receipt.isFetching && receiptId && (
        <p role="status">
          Loading the saved follow-up receipt and current case state…
        </p>
      )}
      {receipt.error && (
        <>
          <p className="rc-error" role="alert">
            {receipt.error.message}
          </p>
          <button disabled={locked} onClick={() => void receipt.refetch()}>
            Retry saved follow-up receipt
          </button>
        </>
      )}
      {receipt.isSuccess && receipt.data?.proposal_id === proposalId && (
        <>
          <h4>Saved follow-up receipt</h4>
          <p>
            {receipt.data.actor}: {receipt.data.reason} ·{" "}
            {receipt.data.created_at}
          </p>
          <Metrics counts={receipt.data.counts} />
          <p className="rc-reference">
            Receipt <code>{receipt.data.id}</code> · Current receipt snapshot{" "}
            <code>{receipt.data.snapshot}</code>
          </p>
          {!receipt.data.source_inputs_fresh && (
            <div className="rc-warning" role="alert">
              <strong>
                Source dependencies have changed since confirmation.
              </strong>
              <ul>
                {receipt.data.source_stale_reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              <p>
                The saved receipt remains readable. Current case versions and
                acknowledgements are reported separately.
              </p>
            </div>
          )}
          <div className="rc-filters">
            <button
              disabled={locked || receipt.isFetching}
              onClick={() => void refreshReceipt().catch(() => {})}
            >
              Refresh saved follow-up receipt
            </button>
            <button
              disabled={locked || receipt.isFetching}
              onClick={() => void download("json")}
            >
              Download follow-up JSON
            </button>
            <button
              disabled={locked || receipt.isFetching}
              onClick={() => void download("xlsx")}
            >
              Download follow-up XLSX
            </button>
          </div>
          {exportError && (
            <p className="rc-error" role="alert">
              {exportError}
            </p>
          )}
          {exporting && (
            <p role="status">Preparing complete follow-up receipt export…</p>
          )}
          {receipt.data.targets.map((target) => (
            <section
              key={target.association_id}
              aria-label={`Saved follow-up target ${target.target_key}`}
              style={{
                borderTop: "1px solid #d7e3df",
                paddingTop: "16px",
                marginTop: "18px",
              }}
            >
              <h4>
                {target.source}
                {(target.network_label || target.network_id) && (
                  <> · {target.network_label ?? target.network_id}</>
                )}
              </h4>
              <p>
                {target.action === "create"
                  ? "Created QA review case"
                  : "Associated existing case"}{" "}
                · {human(target.field)}
              </p>
              <dl>
                <dt>Case</dt>
                <dd>
                  <a
                    href={workspaceHref("work", { ...Object.fromEntries(route), case: target.case.id, view: "work" })}
                  >
                    Open work case
                  </a>
                </dd>
                <dt>Owner</dt>
                <dd>{target.case.owner ?? "Unassigned"}</dd>
                <dt>Work state</dt>
                <dd>
                  {human(target.case.status)} · Version {target.case.version} ·{" "}
                  {target.case.kind ?? "review"}
                </dd>
              </dl>
              <details>
                <summary>Saved target and existing work context</summary>
                <pre>
                  {show({
                    association_id: target.association_id,
                    target_key: target.target_key,
                    refs: target.refs,
                    network_id: target.network_id,
                    field: target.field,
                    case_proposal: target.case.proposal,
                    case_observed: target.case.observed,
                  })}
                </pre>
              </details>
              <Acknowledgement
                receiptId={receiptId}
                target={target}
                otherBusy={
                  otherBusy ||
                  mutation.isPending ||
                  exporting ||
                  receipt.isFetching ||
                  (pendingAck !== null && pendingAck !== target.association_id)
                }
                onPending={setAckPending}
                onRefresh={refreshReceipt}
              />
            </section>
          ))}
          <p>
            {receipt.data.total} saved follow-up targets in the complete
            receipt.
          </p>
          <Pages
            offset={receiptOffset}
            next={receipt.data.next_offset}
            label="Saved follow-up target pages"
            disabled={locked || receipt.isFetching}
            onChange={setReceiptOffset}
          />
        </>
      )}
    </section>
  );
}
