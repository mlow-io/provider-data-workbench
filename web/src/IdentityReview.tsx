import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";
import { NativeSelect, NativeSelectOption } from "./components/ui/native-select";
import { Textarea } from "./components/ui/textarea";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type IdentityKind = "clinician" | "location";
type Action = "approve" | "reject" | "defer";
type Revision = {
  id: string;
  kind: IdentityKind;
  ref: string;
  target_id: string;
  previous_id: string | null;
  decision_id: string;
  actor: string;
  reason: string;
  created_at: string;
};
type Decision = {
  id: string;
  decision: Action;
  actor: string;
  reason: string;
  created_at: string;
  target_id: string | null;
  run_id: string;
  candidate_id: string;
  pair_key: string;
};
type Target = { id: string; label: string };
type ReviewSnapshot = {
  candidate: {
    id: string;
    kind: IdentityKind;
    left: string;
    right: string;
    eligible: boolean;
  };
  review_snapshot: string;
  inputs_fresh: boolean;
  approval_allowed?: boolean;
  approval_blockers?: string[];
  current_links: Record<string, Revision | null>;
  latest_decision: Decision | null;
  history: Decision[];
  history_total?: number;
  history_next_offset?: number | null;
  targets: { clinicians: Target[]; locations: Target[] };
};
type ReviewRequest = {
  run_id: string;
  candidate_id: string;
  decision: Action;
  request_id: string;
  expected_snapshot: string;
  expected_revisions: Record<string, string | null>;
  expected_decision: string | null;
  actor: string;
  reason: string;
  target_id?: string;
  new_label?: string;
};
class ReviewError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}
async function request<T>(path: string, payload?: ReviewRequest): Promise<T> {
  const response = await fetch(
    path,
    payload
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      : undefined,
  );
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ReviewError(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail ?? `Request failed (${response.status})`),
      response.status,
    );
  }
  return response.json() as Promise<T>;
}

export function IdentityReview({
  runId,
  candidateId,
  kind,
}: {
  runId: string;
  candidateId: string;
  kind: IdentityKind;
}) {
  const client = useQueryClient();
  const [opened, setOpened] = useState(false);
  const [action, setAction] = useState<Action | "">("");
  const [actor, setActor] = useState("");
  const [reason, setReason] = useState("");
  const [mode, setMode] = useState("existing");
  const [targetId, setTargetId] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [evidenceReviewed, setEvidenceReviewed] = useState(false);
  const [requiresRefresh, setRequiresRefresh] = useState(false);
  const [pendingRequest, setPendingRequest] = useState<ReviewRequest | null>(
    null,
  );
  const [targetSearch, setTargetSearch] = useState("");
  const [targetOffset, setTargetOffset] = useState(0);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [saved, setSaved] = useState<Action | null>(null);
  const label = kind === "clinician" ? "clinician" : "practice location";
  const query = useQuery({
    queryKey: ["identity-review", runId, candidateId, historyOffset],
    enabled: opened,
    refetchOnWindowFocus: false,
    queryFn: () =>
      request<ReviewSnapshot>(
        `/api/reconciliation/runs/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(candidateId)}/review?offset=${historyOffset}&limit=20`,
      ),
  });
  const mutation = useMutation({
    mutationFn: (payload: ReviewRequest) =>
      request<{ decision: Decision; links: Revision[] }>(
        "/api/reconciliation/links",
        payload,
      ),
    onSuccess: async (response) => {
      setSaved(response.decision.decision);
      setPendingRequest(null);
      setAction("");
      setTargetId("");
      setNewLabel("");
      setHistoryOffset(0);
      setReason("");
      setEvidenceReviewed(false);
      setRequiresRefresh(false);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["identity-review"] }),
        client.invalidateQueries({ queryKey: ["identity-targets"] }),
        client.invalidateQueries({ queryKey: ["reconciliation-run", runId] }),
        client.invalidateQueries({
          queryKey: ["reconciliation-candidates", runId],
        }),
      ]);
    },
    onError: (error) => {
      if (error instanceof ReviewError && error.status < 500) {
        setPendingRequest(null);
        if (error.status === 409) {
          setRequiresRefresh(true);
          setEvidenceReviewed(false);
        }
      }
    },
  });
  const data = query.data;
  useEffect(() => {
    setEvidenceReviewed(false);
  }, [data?.review_snapshot]);
  const targetQuery = useQuery({
    queryKey: ["identity-targets", kind, targetSearch, targetOffset],
    enabled:
      opened && Boolean(data) && action === "approve" && mode === "existing",
    queryFn: () =>
      request<{ items: Target[]; total: number; next_offset: number | null }>(
        `/api/reconciliation/targets/${kind}?${new URLSearchParams({ search: targetSearch, offset: String(targetOffset), limit: "20" })}`,
      ),
  });
  const targets = data
    ? kind === "clinician"
      ? data.targets.clinicians
      : data.targets.locations
    : [];
  const selectableTargets = targetQuery.data?.items ?? [];
  const busy = mutation.isPending || query.isFetching;
  const locked = busy || pendingRequest !== null;
  const canSubmit =
    data?.inputs_fresh &&
    !requiresRefresh &&
    !query.isError &&
    !busy &&
    evidenceReviewed &&
    Boolean(action && actor.trim() && reason.trim()) &&
    (action !== "approve" ||
      (data.approval_allowed !== false &&
        (mode === "existing"
          ? Boolean(targetId) && !targetQuery.isFetching && !targetQuery.isError
          : Boolean(newLabel.trim()))));
  const refresh = async () => {
    setEvidenceReviewed(false);
    const result = await query.refetch();
    if (result.isSuccess) {
      setRequiresRefresh(false);
      mutation.reset();
    }
  };
  const submit = () => {
    if (pendingRequest) {
      mutation.mutate(pendingRequest);
      return;
    }
    if (!data || !canSubmit || !action) return;
    const payload: ReviewRequest = {
      run_id: runId,
      candidate_id: candidateId,
      decision: action,
      request_id: crypto.randomUUID(),
      expected_snapshot: data.review_snapshot,
      expected_revisions: {
        [data.candidate.left]:
          data.current_links[data.candidate.left]?.id ?? null,
        [data.candidate.right]:
          data.current_links[data.candidate.right]?.id ?? null,
      },
      expected_decision: data.latest_decision?.id ?? null,
      actor: actor.trim(),
      reason: reason.trim(),
      ...(action === "approve"
        ? mode === "existing"
          ? { target_id: targetId }
          : { new_label: newLabel.trim() }
        : {}),
    };
    setSaved(null);
    setPendingRequest(payload);
    mutation.mutate(payload);
  };
  if (!opened)
    return <Button variant="outline" onClick={() => setOpened(true)}>Review {label} link</Button>;
  return (
    <section aria-label={`${label} link review`} className="rc-evidence">
      <h3>Review {label} link</h3>
      <p>
        This decision applies to both retained references for this {label}.
        Clinician and location links are independent. Source acceptance and
        source values stay separate.
      </p>
      <Button variant="outline"
        disabled={busy || pendingRequest !== null}
        onClick={() => void refresh()}
      >
        Refresh review snapshot
      </Button>
      {query.isFetching && (
        <p role="status">Loading current links and review history…</p>
      )}
      {query.error && (
        <p role="alert" className="rc-error">
          {query.error.message}
        </p>
      )}
      {saved && (
        <p role="status">
          {saved === "approve"
            ? `Approved ${label} link saved for both references.`
            : `${saved === "reject" ? "Rejection" : "Deferral"} saved for this pair. Existing links were preserved.`}
        </p>
      )}
      {data && (
        <>
          <p className="rc-reference">
            Review snapshot <code>{data.review_snapshot}</code> ·{" "}
            {data.inputs_fresh
              ? "Source inputs current at this review snapshot"
              : "Stale source inputs"}
          </p>
          {!data.inputs_fresh && (
            <p role="alert" className="rc-warning">
              These source inputs are stale. Create a fresh candidate run before
              recording a decision. Existing links and history remain readable.
            </p>
          )}
          {requiresRefresh && (
            <p role="alert" className="rc-warning">
              Review state changed. Refresh the review snapshot, inspect current
              links and history, then review the evidence again.
            </p>
          )}
          {data.approval_allowed === false && (
            <div className="rc-warning">
              <h4>Approval requires compatible identity evidence</h4>
              <ul>
                {(data.approval_blockers ?? []).map((blocker) => (
                  <li key={blocker}>{blocker}</li>
                ))}
              </ul>
              <p>
                Reject or defer this pair, or create a new run after resolving
                the source type declaration.
              </p>
            </div>
          )}
          {!data.candidate.eligible && data.approval_allowed !== false && (
            <p className="rc-warning">
              The rules found unresolved or conflicting evidence. You may still
              make an explicit manual decision after reviewing the source
              assertions and recording your reason.
            </p>
          )}
          <h4>Current {label} links</h4>
          {[data.candidate.left, data.candidate.right].map((ref, index) => {
            const link = data.current_links[ref];
            return (
              <div key={ref}>
                <p className="rc-reference">
                  {index === 0 ? "Left" : "Right"} reference <code>{ref}</code>
                </p>
                {link ? (
                  <p>
                    Linked to{" "}
                    <strong>
                      {targets.find((target) => target.id === link.target_id)
                        ?.label ?? link.target_id}
                    </strong>{" "}
                    · Target <code>{link.target_id}</code> · Revision{" "}
                    <code>{link.id}</code> · {link.actor}: {link.reason}
                  </p>
                ) : (
                  <p>No reviewed {label} link.</p>
                )}
              </div>
            );
          })}
          <fieldset
            disabled={locked}
            style={{
              border: "1px solid #d7e3df",
              padding: "16px",
              minWidth: 0,
            }}
          >
            <legend>Record an explicit {label} decision</legend>
            <div className="rc-create">
              <label>
                Link decision
                <NativeSelect
                  aria-label="Link decision"
                  value={action}
                  onChange={(event) =>
                    setAction(event.target.value as Action | "")
                  }
                >
                  <NativeSelectOption value="">Choose a decision</NativeSelectOption>
                  <NativeSelectOption
                    value="approve"
                    disabled={data.approval_allowed === false}
                  >
                    Approve both references to one target
                  </NativeSelectOption>
                  <NativeSelectOption value="reject">Reject this candidate pair</NativeSelectOption>
                  <NativeSelectOption value="defer">Defer this candidate pair</NativeSelectOption>
                </NativeSelect>
              </label>
              {action === "approve" && (
                <>
                  <label>
                    Target selection
                    <NativeSelect
                      aria-label="Target selection"
                      value={mode}
                      onChange={(event) => setMode(event.target.value)}
                    >
                      <NativeSelectOption value="existing">Existing {label}</NativeSelectOption>
                      <NativeSelectOption value="new">Create a new labeled {label}</NativeSelectOption>
                    </NativeSelect>
                  </label>
                  {mode === "existing" ? (
                    <div>
                      <label>
                        Find {label} target
                        <Input
                          aria-label={`Find ${label} target`}
                          type="search"
                          value={targetSearch}
                          onChange={(event) => {
                            setTargetSearch(event.target.value);
                            setTargetOffset(0);
                            setTargetId("");
                          }}
                          placeholder="Label text or exact target ID"
                        />
                      </label>
                      {targetQuery.isFetching && (
                        <p role="status">Loading {label} targets…</p>
                      )}
                      {targetQuery.error && (
                        <p role="alert" className="rc-error">
                          {targetQuery.error.message}
                        </p>
                      )}
                      <label>
                        Target {label}
                        <NativeSelect
                          aria-label={`Target ${label}`}
                          value={targetId}
                          disabled={
                            targetQuery.isFetching || targetQuery.isError
                          }
                          onChange={(event) => setTargetId(event.target.value)}
                        >
                          <NativeSelectOption value="">Select a {label}</NativeSelectOption>
                          {selectableTargets.map((target) => (
                            <NativeSelectOption key={target.id} value={target.id}>
                              {target.label} · {target.id}
                            </NativeSelectOption>
                          ))}
                        </NativeSelect>
                      </label>
                      {targetQuery.data && (
                        <>
                          <p>
                            {targetQuery.data.total} matching {label} targets.
                          </p>
                          {!targetQuery.data.total && (
                            <p>
                              No targets match this search. Refine the search or
                              choose a new labeled {label}.
                            </p>
                          )}
                          <div
                            className="rc-pager"
                            role="group"
                            aria-label={`${label} target pages`}
                          >
                            <Button variant="outline"
                              type="button"
                              disabled={targetOffset === 0}
                              onClick={() => {
                                setTargetOffset(Math.max(0, targetOffset - 20));
                                setTargetId("");
                              }}
                            >
                              Previous targets
                            </Button>
                            <span>From {targetOffset + 1}</span>
                            <Button variant="outline"
                              type="button"
                              disabled={targetQuery.data.next_offset === null}
                              onClick={() => {
                                setTargetOffset(targetQuery.data!.next_offset!);
                                setTargetId("");
                              }}
                            >
                              Next targets
                            </Button>
                          </div>
                        </>
                      )}
                    </div>
                  ) : (
                    <label>
                      New {label} label
                      <Input
                        aria-label={`New ${label} label`}
                        value={newLabel}
                        onChange={(event) => setNewLabel(event.target.value)}
                      />
                    </label>
                  )}
                </>
              )}
              <label>
                Review actor
                <Input
                  aria-label="Review actor"
                  value={actor}
                  onChange={(event) => setActor(event.target.value)}
                />
              </label>
              <label>
                Review reason
                <Textarea
                  aria-label="Review reason"
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
                marginTop: "16px",
              }}
            >
              <input
                type="checkbox"
                checked={evidenceReviewed}
                onChange={(event) => setEvidenceReviewed(event.target.checked)}
              />
              I reviewed both source assertions, contradictions and missing
              evidence for this {label} decision.
            </label>
          </fieldset>
          {action === "approve" && (
            <p>
              Approval links both exact retained references to the selected
              target. It does not approve a location when reviewing a clinician,
              or a clinician when reviewing a location.
            </p>
          )}
          {(action === "reject" || action === "defer") && (
            <p>
              Rejecting or deferring this pair records a decision and preserves
              any existing links.
            </p>
          )}
          {mutation.error && (
            <p role="alert" className="rc-error">
              {mutation.error.message}
            </p>
          )}
          {pendingRequest && mutation.isError && (
            <p role="status">
              The outcome is unconfirmed. Retry sends the identical request ID
              and decision payload.
            </p>
          )}
          <Button variant="outline"
            className="button button-primary"
            disabled={pendingRequest ? busy : !canSubmit}
            onClick={submit}
          >
            {mutation.isPending
              ? "Saving review decision…"
              : pendingRequest
                ? "Retry same review decision"
                : "Save link decision"}
          </Button>
          <h4>Append-only review history</h4>
          <p>
            {data.history_total ?? data.history.length} decisions recorded for
            this pair.
          </p>
          <div
            className="rc-pager"
            role="group"
            aria-label="Review history pages"
          >
            <Button variant="outline"
              disabled={busy || historyOffset === 0}
              onClick={() => {
                setHistoryOffset(Math.max(0, historyOffset - 20));
                setEvidenceReviewed(false);
              }}
            >
              Previous history
            </Button>
            <span>From {historyOffset + 1}</span>
            <Button variant="outline"
              disabled={busy || data.history_next_offset == null}
              onClick={() => {
                setHistoryOffset(data.history_next_offset!);
                setEvidenceReviewed(false);
              }}
            >
              Next history
            </Button>
          </div>
          {data.latest_decision && (
            <p>
              Latest decision: {data.latest_decision.decision} ·{" "}
              <code>{data.latest_decision.id}</code>
            </p>
          )}
          {!data.history.length ? (
            <p>No decisions recorded for this pair.</p>
          ) : (
            <ol className="history">
              {data.history.map((decision) => (
                <li key={decision.id}>
                  <b>{decision.decision}</b>
                  <span>
                    {decision.actor}: {decision.reason}
                  </span>
                  {decision.target_id && (
                    <small>Target {decision.target_id}</small>
                  )}
                  <small>Decision {decision.id}</small>
                  <time>{decision.created_at}</time>
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </section>
  );
}
