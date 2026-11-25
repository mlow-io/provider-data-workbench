import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, ExternalLink, FilePlus2, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { dataClient, RequestRejected } from "@/lib/dataClient";
import { formatPhone, formatShortDate } from "@/lib/format";
import type { PhoneReviewScope, PhoneValue } from "@/lib/types";
import { cn } from "@/lib/utils";
import { navigateWorkspace } from "@/workspaceNavigation";

const REVIEWER = "M. Brooks";

const SOURCE_LABELS: Record<string, string> = {
  "cumberland-clinic": "Cumberland clinic roster",
  "volunteer-directory": "Volunteer payer directory extract",
};

type Stage = "needs_decision" | "agrees" | "ready" | "pending_approval" | "approved" | "no_change" | "blocked";

const STAGES: Record<Stage, { label: string; tone: string }> = {
  needs_decision: { label: "Sources disagree", tone: "bg-status-danger-bg text-status-danger" },
  agrees: { label: "Sources agree", tone: "bg-secondary text-secondary-foreground" },
  ready: { label: "Ready for candidate", tone: "bg-status-warning-bg text-status-warning" },
  pending_approval: { label: "Awaiting approval", tone: "bg-status-warning-bg text-status-warning" },
  approved: { label: "Correction approved", tone: "bg-status-success-bg text-status-success" },
  no_change: { label: "Roster matches", tone: "bg-secondary text-secondary-foreground" },
  blocked: { label: "Needs attention", tone: "bg-status-danger-bg text-status-danger" },
};

export function stageOf(scope: PhoneReviewScope): Stage {
  const current = scope.candidates.filter((c) => c.decision_id === scope.decision?.id);
  if (current.some((c) => c.state === "candidate")) return "pending_approval";
  if (current.some((c) => c.state === "approved")) return "approved";
  if (!scope.decision) return scope.sources_agree ? "agrees" : "needs_decision";
  if (scope.correction.status === "eligible") return "ready";
  if (scope.correction.status === "no_change") return "no_change";
  return "blocked";
}

function phoneText(value: PhoneValue) {
  return value.number ? formatPhone(value.number, value.extension) : "Not supplied";
}

function scopeKey(scope: PhoneReviewScope) {
  return `${scope.clinician_id}:${scope.location_id}`;
}

/**
 * A request whose outcome is unknown keeps its key, so retrying cannot create a
 * second decision or candidate; a refused request is discarded.
 */
interface PendingRequest {
  kind: "decision" | "candidate";
  scope: string;
  key: string;
  selectedRef?: string;
  reason: string;
}

function StageBadge({ stage }: { stage: Stage }) {
  return (
    <Badge variant="outline" className={cn("border-transparent font-medium", STAGES[stage].tone)}>
      {STAGES[stage].label}
    </Badge>
  );
}

function StepHeading({ step, title, done }: { step: number; title: string; done: boolean }) {
  return (
    <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
      <span
        className={cn(
          "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs tabular-nums",
          done ? "border-transparent bg-status-success-bg text-status-success" : "bg-card"
        )}
        aria-hidden="true"
      >
        {done ? <CheckCircle2 className="size-3.5" /> : step}
      </span>
      {title}
    </h3>
  );
}

function ScopeDetail({ scope }: { scope: PhoneReviewScope }) {
  const queryClient = useQueryClient();
  const stage = stageOf(scope);
  const [selectedRef, setSelectedRef] = useState(scope.decision?.selected_ref ?? "");
  const [decisionReason, setDecisionReason] = useState("");
  const [candidateReason, setCandidateReason] = useState(`Apply reviewed ${scope.location_label} phone`);
  const [pending, setPending] = useState<PendingRequest | null>(null);
  const [unknownOutcome, setUnknownOutcome] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setSelectedRef(scope.decision?.selected_ref ?? "");
  }, [scope.decision?.selected_ref]);

  const openCandidate = scope.candidates.find((c) => c.state === "candidate");
  const locked = Boolean(openCandidate) || busy || unknownOutcome;
  const decisionChanged = Boolean(selectedRef) && selectedRef !== scope.decision?.selected_ref;

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["phone-reviews"] }),
      queryClient.invalidateQueries({ queryKey: ["managed-feeds"] }),
      queryClient.invalidateQueries({ queryKey: ["workbench-overview"] }),
    ]);
  }

  async function send(request: PendingRequest) {
    setBusy(true);
    setError("");
    setPending(request);
    try {
      if (request.kind === "decision") {
        await dataClient.decidePhone({
          scope,
          selectedRef: request.selectedRef!,
          requestId: request.key,
          actor: REVIEWER,
          reason: request.reason,
        });
        setDecisionReason("");
        toast.success("Phone decision recorded. The roster is unchanged until a candidate is approved.");
      } else {
        const candidate = await dataClient.createPhoneCandidate({
          scope,
          idempotencyKey: request.key,
          actor: REVIEWER,
          reason: request.reason,
        });
        toast.success("Roster candidate created. Approve it separately in Deliveries.", {
          action: { label: "Open", onClick: () => navigateWorkspace("deliveries", { version: candidate.id }) },
        });
      }
      setPending(null);
      setUnknownOutcome(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Request failed";
      if (err instanceof RequestRejected || dataClient.isDemoMode()) {
        // The server refused it, so nothing was applied; inspect fresh state before retrying.
        setPending(null);
        setUnknownOutcome(false);
        setError(`${message}. Review the latest evidence before trying again.`);
      } else {
        setUnknownOutcome(true);
        setError(`${message}. The outcome is unknown; retry sends the same request and cannot apply it twice.`);
      }
    } finally {
      await refresh();
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader className="border-b">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex flex-col gap-1">
            <CardTitle>{scope.clinician_label}</CardTitle>
            <CardDescription>
              {scope.location_label} · reviewed clinician and office links
            </CardDescription>
          </div>
          <StageBadge stage={stage} />
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-6 pt-5">
        {!scope.inputs_fresh && (
          <Alert variant="destructive">
            <AlertTitle>Evidence changed</AlertTitle>
            <AlertDescription>A source or link revision changed this scope. Its earlier decision cannot be reused.</AlertDescription>
          </Alert>
        )}
        {error && (
          <Alert variant={unknownOutcome ? "default" : "destructive"}>
            <AlertTitle>{unknownOutcome ? "Outcome unknown" : "Action not completed"}</AlertTitle>
            <AlertDescription className="flex flex-col gap-3">
              <span>{error}</span>
              {unknownOutcome && pending && (
                <Button size="sm" variant="outline" className="self-start" disabled={busy} onClick={() => void send(pending)}>
                  <RotateCcw data-icon="inline-start" />
                  Retry same request
                </Button>
              )}
            </AlertDescription>
          </Alert>
        )}

        {!scope.sources_agree && scope.phone_conflict && (
          <Alert>
            <AlertTitle>Phone Conflict Triage · {scope.phone_conflict.label}</AlertTitle>
            <AlertDescription>{scope.phone_conflict.guidance}</AlertDescription>
          </Alert>
        )}

        <section aria-labelledby="phone-step-compare" className="flex flex-col gap-3">
          <div id="phone-step-compare">
            <StepHeading step={1} title="Choose the office phone" done={Boolean(scope.decision)} />
          </div>
          <fieldset className="flex flex-col gap-2" disabled={locked}>
            <legend className="sr-only">Phone assertions for {scope.location_label}</legend>
            {scope.options.map((option) => {
              const checked = selectedRef === option.ref;
              return (
                <label
                  key={option.ref}
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-lg border p-3.5 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                    checked ? "border-primary bg-accent/60" : "bg-card hover:bg-muted/40",
                    (!option.selectable || locked) && "cursor-not-allowed opacity-70"
                  )}
                >
                  <input
                    type="radio"
                    name={`phone-${scopeKey(scope)}`}
                    value={option.ref}
                    checked={checked}
                    disabled={!option.selectable}
                    onChange={() => setSelectedRef(option.ref)}
                    className="mt-1 accent-primary"
                  />
                  <span className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-medium text-foreground">
                        {phoneText(option)}
                      </span>
                      {option.from_approved_roster && <Badge variant="secondary">In approved roster</Badge>}
                      {scope.decision?.selected_ref === option.ref && <Badge variant="outline">Current decision</Badge>}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {SOURCE_LABELS[option.source] ?? option.source} ·{" "}
                      <span className="font-mono">{option.locator}</span>
                    </span>
                    {!option.selectable && (
                      <span className="text-xs text-status-danger">Not selectable: {option.findings.join(", ") || "invalid value"}</span>
                    )}
                  </span>
                </label>
              );
            })}
          </fieldset>
          {scope.decision && (
            <p className="text-xs text-muted-foreground">
              Decided by {scope.decision.actor} on {formatShortDate(scope.decision.created_at)}: {scope.decision.reason}
            </p>
          )}
          {!locked && decisionChanged && (
            <Field>
              <FieldLabel htmlFor={`decision-reason-${scopeKey(scope)}`}>Decision reason</FieldLabel>
              <Textarea
                id={`decision-reason-${scopeKey(scope)}`}
                value={decisionReason}
                onChange={(e) => setDecisionReason(e.target.value)}
                placeholder="Which evidence supports this phone?"
              />
              <FieldDescription>
                Recorded as {REVIEWER}. A decision changes no roster value by itself.
              </FieldDescription>
            </Field>
          )}
          {!locked && decisionChanged && (
            <Button
              className="self-start"
              disabled={!decisionReason.trim()}
              onClick={() =>
                void send({ kind: "decision", scope: scopeKey(scope), key: crypto.randomUUID(), selectedRef, reason: decisionReason.trim() })
              }
            >
              Record phone decision
            </Button>
          )}
        </section>

        <section aria-labelledby="phone-step-candidate" className="flex flex-col gap-3 border-t pt-5">
          <div id="phone-step-candidate">
            <StepHeading step={2} title="Create a roster candidate" done={scope.candidates.some((c) => c.decision_id === scope.decision?.id)} />
          </div>
          {stage === "pending_approval" || stage === "approved" ? (
            <p className="text-sm text-muted-foreground">A candidate exists for this decision.</p>
          ) : scope.correction.status === "not_selected" ? (
            <p className="text-sm text-muted-foreground">Record a phone decision first.</p>
          ) : scope.correction.status === "no_change" ? (
            <p className="text-sm text-muted-foreground">
              The approved roster already lists this phone, so no candidate is needed.
            </p>
          ) : scope.correction.status === "eligible" ? (
            <>
              <div className="flex flex-col gap-2 rounded-lg border p-3.5 sm:flex-row sm:items-center sm:gap-4">
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">Approved roster ({scope.correction.row_locator})</span>
                  <span className="font-mono text-sm line-through decoration-muted-foreground/60">
                    {phoneText(scope.correction.old_value)}
                  </span>
                </div>
                <ArrowRight className="hidden size-4 text-muted-foreground sm:block" aria-hidden="true" />
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">Candidate value</span>
                  <span className="font-mono text-sm font-medium text-foreground">
                    {phoneText(scope.correction.new_value)}
                  </span>
                </div>
              </div>
              <Field>
                <FieldLabel htmlFor={`candidate-reason-${scopeKey(scope)}`}>Candidate reason</FieldLabel>
                <Textarea
                  id={`candidate-reason-${scopeKey(scope)}`}
                  value={candidateReason}
                  disabled={locked}
                  onChange={(e) => setCandidateReason(e.target.value)}
                />
                <FieldDescription>
                  Copies the complete approved roster and changes only this row. The approved directory stays live until a separate approval.
                </FieldDescription>
              </Field>
              <Button
                className="self-start"
                disabled={locked || !candidateReason.trim()}
                onClick={() =>
                  void send({ kind: "candidate", scope: scopeKey(scope), key: crypto.randomUUID(), reason: candidateReason.trim() })
                }
              >
                <FilePlus2 data-icon="inline-start" />
                Create roster candidate
              </Button>
            </>
          ) : (
            <Alert variant="destructive">
              <AlertTitle>Cannot create a candidate</AlertTitle>
              <AlertDescription>{"reason" in scope.correction ? scope.correction.reason : "No approved roster covers this office."}</AlertDescription>
            </Alert>
          )}
        </section>

        <section aria-labelledby="phone-step-approve" className="flex flex-col gap-3 border-t pt-5">
          <div id="phone-step-approve">
            <StepHeading step={3} title="Approve separately in Deliveries" done={stage === "approved"} />
          </div>
          {scope.candidates.length === 0 ? (
            <p className="text-sm text-muted-foreground">No candidate yet.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {scope.candidates.map((candidate) => (
                <li
                  key={candidate.version_id}
                  className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <span className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-mono">{phoneText(candidate.new_value)}</span>
                    <StatusBadge
                      status={candidate.state}
                      label={candidate.state === "candidate" ? "Awaiting Approval" : undefined}
                    />
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => navigateWorkspace("deliveries", { version: candidate.version_id })}
                  >
                    <ExternalLink data-icon="inline-start" />
                    {candidate.state === "candidate" ? "Review and approve" : "Open version"}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </CardContent>
    </Card>
  );
}

export function PhoneCorrectionsPage() {
  const reviewsQuery = useQuery({
    queryKey: ["phone-reviews"],
    queryFn: () => dataClient.phoneReviews(),
  });
  const scopes = useMemo(() => reviewsQuery.data ?? [], [reviewsQuery.data]);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    if (selected || scopes.length === 0) return;
    const first = scopes.find((s) => stageOf(s) === "needs_decision") ?? scopes[0];
    setSelected(scopeKey(first));
  }, [scopes, selected]);

  const active = scopes.find((s) => scopeKey(s) === selected) ?? null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Reviewed Phone Corrections</h1>
        <p className="text-sm text-muted-foreground">
          Choose an office phone where sources disagree, turn it into a complete roster candidate, then approve that
          candidate separately. A clinician's offices are reviewed one at a time.
        </p>
      </div>

      {reviewsQuery.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : reviewsQuery.isError ? (
        <Alert variant="destructive">
          <AlertTitle>Could not load phone reviews</AlertTitle>
          <AlertDescription>{reviewsQuery.error instanceof Error ? reviewsQuery.error.message : "Request failed"}</AlertDescription>
        </Alert>
      ) : scopes.length === 0 ? (
        <Alert>
          <AlertTitle>No reviewed office scopes</AlertTitle>
          <AlertDescription>
            Phones appear here after a clinician and an office are both linked across sources.
          </AlertDescription>
        </Alert>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <Card className="self-start lg:col-span-4">
            <CardHeader>
              <CardTitle className="text-base">Reviewed office scopes</CardTitle>
              <CardDescription>{scopes.length} clinician–office pairs with phone evidence</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2.5">
              {scopes.map((scope) => {
                const key = scopeKey(scope);
                return (
                  <button
                    key={key}
                    type="button"
                    aria-current={key === selected ? "true" : undefined}
                    onClick={() => setSelected(key)}
                    className={cn(
                      "flex flex-col gap-1.5 rounded-lg border p-3.5 text-left transition-colors",
                      key === selected ? "border-primary bg-accent/60" : "bg-card hover:bg-muted/40"
                    )}
                  >
                    <span className="font-medium text-foreground">{scope.location_label}</span>
                    <span className="text-xs text-muted-foreground">{scope.clinician_label}</span>
                    <StageBadge stage={stageOf(scope)} />
                  </button>
                );
              })}
            </CardContent>
          </Card>
          <div className="lg:col-span-8">{active && <ScopeDetail key={scopeKey(active)} scope={active} />}</div>
        </div>
      )}
    </div>
  );
}
