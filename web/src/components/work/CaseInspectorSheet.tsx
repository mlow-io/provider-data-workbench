import { useEffect, useMemo, useState } from "react";
import { ArrowRight, CheckCircle2, ChevronDown, Clock, Maximize2, Minimize2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { RiskBadge, StatusBadge } from "@/components/shared/StatusBadge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  clinicDisplayName,
  formatDateTime,
  formatPhone,
  formatShortDate,
  isValidNpi,
  statusLabel,
} from "@/lib/format";
import { RequestRejected } from "@/lib/dataClient";
import type { CaseActionInput, WorkCaseDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

interface CaseInspectorSheetProps {
  open: boolean;
  caseDetail: WorkCaseDetail | null;
  loading: boolean;
  onOpenChange: (open: boolean) => void;
  onRefresh: () => Promise<void>;
  onRecordEvent: (caseId: string, input: CaseActionInput) => Promise<void>;
}

function allowedActionsFor(detail: WorkCaseDetail): Array<{ value: CaseActionInput["action"]; label: string }> {
  const options: Array<{ value: CaseActionInput["action"]; label: string }> = [];
  if (detail.kind === "correction") {
    if (["new", "reopened", "deferred", "needs_information"].includes(detail.status)) {
      options.push({ value: "triage", label: "Triage & Confirm Discrepancy" });
    }
    if (detail.status === "triaged") {
      options.push({ value: "approve", label: "Approve Correction Proposal" });
    }
    if (detail.status === "approved") {
      options.push({ value: "submit", label: "Record Payer Submission" });
    }
    if (detail.status === "pending_verification") {
      options.push({ value: "verify", label: "Verify Observed Payer Directory" });
    }
  } else {
    if (["new", "reopened", "deferred", "needs_information"].includes(detail.status)) {
      options.push({ value: "triage", label: "Triage QA Item" });
    }
    if (["new", "triaged", "needs_information"].includes(detail.status)) {
      options.push({ value: "resolve", label: "Resolve QA Review" });
    }
  }
  options.push({ value: "outreach", label: "Log Clinic Outreach" });
  options.push({ value: "assign", label: "Assign / Set Follow-Up" });
  if (detail.status !== "needs_information") {
    options.push({ value: "needs_information", label: "Mark Needs Information" });
  }
  if (["new", "triaged", "reopened"].includes(detail.status)) {
    options.push({ value: "defer", label: "Defer" });
  }
  return options;
}

function formatDiffValue(fieldName: string, value: string | null | undefined): string {
  if (!value) return "Not supplied";
  if (fieldName === "phone") return formatPhone(value);
  return value;
}

export function CaseInspectorSheet({
  open,
  caseDetail,
  loading,
  onOpenChange,
  onRefresh,
  onRecordEvent,
}: CaseInspectorSheetProps) {
  const actions = useMemo(() => (caseDetail ? allowedActionsFor(caseDetail) : []), [caseDetail]);
  const [action, setAction] = useState<CaseActionInput["action"]>("triage");
  const [actor, setActor] = useState("M. Brooks");
  const [reason, setReason] = useState("");
  const [proposalPhone, setProposalPhone] = useState("");
  const [observedPhone, setObservedPhone] = useState("");
  const [submissionRef, setSubmissionRef] = useState("");
  const [verificationNote, setVerificationNote] = useState("");
  const [owner, setOwner] = useState("M. Brooks");
  const [followUp, setFollowUp] = useState("");
  const [outreachOutcome, setOutreachOutcome] = useState<
    "no_answer" | "message_left" | "response_received"
  >("response_received");
  const [outreachSummary, setOutreachSummary] = useState("");
  const [saving, setSaving] = useState(false);
  const [gateOpen, setGateOpen] = useState(false);
  const [focused, setFocused] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    if (!caseDetail) return;
    const first = allowedActionsFor(caseDetail)[0]?.value ?? "outreach";
    setAction(first);
    setActionError(null);
    setStale(false);
    setProposalPhone(caseDetail.reference_value ?? caseDetail.evidence.reference_value ?? "");
    setObservedPhone("");
    setSubmissionRef("");
    setVerificationNote("");
    setReason("");
    setOutreachSummary("");
    setOwner(caseDetail.owner ?? "M. Brooks");
    setFollowUp(caseDetail.follow_up ?? "");
  }, [caseDetail?.id, caseDetail?.status, caseDetail?.version]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!caseDetail) return;
    const cleanActor = actor.trim() || "M. Brooks";
    const cleanReason =
      reason.trim() ||
      (action === "triage"
        ? "Validated discrepancy against clinic source evidence"
        : action === "approve"
          ? "Approved proposed correction"
          : action === "resolve"
            ? "Reviewed and resolved against source evidence"
            : "Recorded workflow decision");
    setSaving(true);
    setActionError(null);
    try {
      const payload: CaseActionInput = {
        action,
        actor: cleanActor,
        reason: cleanReason,
        expected_version: caseDetail.version,
      };
      if (action === "assign") {
        payload.owner = owner.trim() || "M. Brooks";
        if (followUp) payload.follow_up = followUp;
      } else if (action === "approve") {
        payload.proposal = proposalPhone;
      } else if (action === "submit") {
        payload.submission_reference = submissionRef;
      } else if (action === "verify") {
        payload.observed = observedPhone;
        payload.verification_note = verificationNote;
      } else if (action === "outreach") {
        payload.contact_at = new Date().toISOString();
        payload.method = "phone";
        payload.outcome = outreachOutcome;
        payload.contact_target = clinicDisplayName(caseDetail.location_id);
        if (outreachOutcome === "response_received") {
          payload.respondent_role = "Practice Manager";
          payload.response_summary = outreachSummary.trim() || cleanReason;
          if (proposalPhone.replace(/\D/g, "").length === 10) {
            payload.reported_phone = proposalPhone;
          }
        }
      }
      await onRecordEvent(caseDetail.id, payload);
      toast.success("Case decision recorded", {
        description: `${caseDetail.provider_name} updated via ${action}.`,
      });
    } catch (err) {
      const conflict = err instanceof RequestRejected && err.status === 409;
      const message = conflict ? "This case may have changed or the action is no longer available. Refresh the case and review the latest evidence before recording your decision." : err instanceof Error ? err.message : "Could not record action";
      setStale(conflict);
      setActionError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }

  const npiRaw =
    caseDetail?.npi ??
    String(caseDetail?.evidence.normalized?.npi ?? "");
  const leieClear = caseDetail?.four_gate_evidence?.gate3_enrollment.leie_clear;
  const exclusionLabel = leieClear == null ? "LEIE unchecked" : leieClear ? "LEIE Clear" : "LEIE Alert";
  const accepting = caseDetail?.four_gate_evidence?.gate4_directory.accepting_new_patients;
  const npiValid = isValidNpi(npiRaw);
  const listingVal = caseDetail?.listing_value ?? caseDetail?.evidence.listing_value ?? null;
  const referenceVal = caseDetail?.reference_value ?? caseDetail?.evidence.reference_value ?? null;

  const events = [...(caseDetail?.history ?? [])].reverse();
  const approved = events.find((event) => event.action === "approve");
  const submitted = events.find((event) => event.action === "submit");
  const checked = events.find((event) => event.action === "verify");
  const captured = caseDetail?.evidence.retrieved_at;
  const sourceLine = `${caseDetail?.evidence.source || "Source unavailable"} · ${captured ? `Captured ${formatShortDate(captured)}` : "Capture date unavailable"}`;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className={cn("flex h-dvh max-h-dvh flex-col gap-0 overflow-hidden p-0 data-[side=right]:w-full", focused ? "data-[side=right]:sm:max-w-6xl" : "data-[side=right]:sm:max-w-xl")}
      >
        <SheetHeader className="shrink-0 border-b px-6 py-4">
          <div className="flex flex-wrap items-center gap-2 pr-6">
            <SheetTitle className="text-base font-semibold">
              {caseDetail?.provider_name ?? "Discrepancy Inspector"}
            </SheetTitle>
            {caseDetail && <RiskBadge risk={caseDetail.risk_level} />}
            {caseDetail && <StatusBadge status={caseDetail.status} />}
          </div>
          <SheetDescription className="flex flex-wrap items-center gap-2 text-xs">
            <span>{caseDetail ? clinicDisplayName(caseDetail.location_id) : "Loading…"}</span>
            {npiRaw && (
              <>
                <span>·</span>
                <span className="font-mono">NPI {npiRaw}</span>
                {npiValid && (
                  <Badge variant="secondary" className="gap-1">
                    <ShieldCheck className="size-3 text-status-success" />
                    Luhn Valid
                  </Badge>
                )}
              </>
            )}
            {caseDetail?.regulatory_regime && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="outline" className="cursor-help font-normal">
                      {caseDetail.regulatory_regime.label}
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent>{caseDetail.regulatory_regime.sla_note}</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </SheetDescription>
          <div className="flex flex-wrap items-center justify-between gap-2 pt-3 pr-8">
            {caseDetail && <p className="text-xs text-muted-foreground">Owner: {caseDetail.owner ?? "Unassigned"} · Follow-up: {caseDetail.follow_up ? formatShortDate(caseDetail.follow_up) : "Unscheduled"}</p>}
            <Button variant="outline" size="sm" onClick={() => setFocused((value) => !value)}>
              {focused ? <Minimize2 data-icon="inline-start" /> : <Maximize2 data-icon="inline-start" />}
              {focused ? "Quick inspector" : "Open focused workspace"}
            </Button>
          </div>
        </SheetHeader>

        <ScrollArea className="min-h-0 flex-1">
          {loading || !caseDetail ? (
            <div className="p-6 text-sm text-muted-foreground">Loading discrepancy evidence…</div>
          ) : (
            <div className={cn("case-workspace grid min-w-0 gap-4 p-4 sm:p-6", focused && "lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]")}>
              <div className="flex min-w-0 flex-col gap-4">
              <Card size="sm">
                <CardHeader>
                  <CardTitle className="text-sm font-medium">{caseDetail.issue}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <p className="text-xs text-muted-foreground">{caseDetail.risk_reason}</p>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
                    <div className="rounded-lg border bg-status-danger-bg/60 p-3">
                      <div className="text-xs font-medium text-muted-foreground">
                        Directory at intake ({caseDetail.field_name})
                      </div>
                      <div className="mt-1 break-words text-sm font-medium text-foreground">
                        {formatDiffValue(caseDetail.field_name, listingVal)}
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">Directory snapshot at intake · source date unavailable</p>
                    </div>
                    <ArrowRight className="hidden size-4 text-muted-foreground sm:block" />
                    <div className="rounded-lg border bg-accent/40 p-3">
                      <div className="text-xs font-medium text-muted-foreground">
                        Submitted / Reference Value
                      </div>
                      <div className="mt-1 break-words text-sm font-medium text-foreground">
                        {formatDiffValue(
                          caseDetail.field_name,
                          referenceVal
                        )}
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{sourceLine}</p>
                    </div>
                  </div>
                  {caseDetail.phone_conflict && (
                    <Alert>
                      <AlertTitle>
                        Phone Conflict Triage: {caseDetail.phone_conflict.label}
                      </AlertTitle>
                      <AlertDescription>{caseDetail.phone_conflict.guidance}</AlertDescription>
                    </Alert>
                  )}
                </CardContent>
              </Card>

              {caseDetail.kind === "correction" && caseDetail.field_name === "phone" && (
                <Card size="sm">
                  <CardHeader><CardTitle className="text-sm">Correction and follow-up</CardTitle></CardHeader>
                  <CardContent>
                    <dl className="grid gap-3 text-xs sm:grid-cols-2">
                      <div>
                        <dt className="text-muted-foreground">Approved correction</dt>
                        <dd>{approved ? `${formatPhone(String(approved.payload.proposal ?? ""))} · ${formatShortDate(approved.occurred_at)}` : "Awaiting approval"}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">Payer submission</dt>
                        <dd>{submitted ? `${String(submitted.payload.submission_reference ?? "Reference unavailable")} · ${formatShortDate(submitted.occurred_at)}` : "Awaiting submission"}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">Payer acknowledgment</dt>
                        <dd>Unrecorded</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">Latest recorded payer directory check</dt>
                        <dd>{checked ? `${formatPhone(String(checked.payload.observed ?? ""))} · ${formatShortDate(checked.occurred_at)} · ${checked.to_status === "verified" ? "Matches correction" : "Discrepancy remains"}` : "Awaiting a directory check"}</dd>
                        {checked && <dd className="text-muted-foreground">{String(checked.payload.verification_note ?? "")}</dd>}
                      </div>
                      <div className="border-t pt-2 sm:col-span-2">
                        <dt className="text-muted-foreground">Follow-up</dt>
                        <dd>{caseDetail.status === "verified" ? "Verified" : `${caseDetail.owner ?? "Unassigned"} · ${caseDetail.follow_up ? formatShortDate(caseDetail.follow_up) : "Date unscheduled"}`}</dd>
                      </div>
                    </dl>
                  </CardContent>
                </Card>
              )}

              {caseDetail.four_gate_evidence && (
                <Collapsible open={gateOpen} onOpenChange={setGateOpen}>
                  <Card size="sm">
                    <CardHeader className="flex flex-row items-center justify-between gap-2 py-2.5">
                      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
                        <CardTitle className="text-sm font-medium">Provider evidence</CardTitle>
                        <Badge variant="secondary" className="text-[11px] font-normal">
                          {caseDetail.four_gate_evidence.gate1_identity.label}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={cn(
                            "border-transparent text-[11px]",
                            caseDetail.four_gate_evidence.gate2_licensure.psv_required
                              ? "bg-status-warning-bg text-status-warning"
                              : "bg-status-success-bg text-status-success"
                          )}
                        >
                          {caseDetail.four_gate_evidence.gate2_licensure.psv_required
                            ? "PSV Required"
                            : "PSV Verified"}
                        </Badge>
                        <Badge variant="secondary" className="text-[11px] font-normal">
                          {exclusionLabel}
                        </Badge>
                        {caseDetail.four_gate_evidence.gate4_directory.hospital_based_newpt_leak && (
                          <Badge
                            variant="outline"
                            className="border-transparent bg-status-warning-bg text-[11px] text-status-warning"
                          >
                            Hospital-Based
                          </Badge>
                        )}
                      </div>
                      <CollapsibleTrigger asChild>
                        <Button variant="ghost" size="xs" className="shrink-0">
                          <span>Details</span>
                          <ChevronDown
                            data-icon="inline-end"
                            className={cn("transition-transform", gateOpen && "rotate-180")}
                          />
                        </Button>
                      </CollapsibleTrigger>
                    </CardHeader>
                    <CollapsibleContent>
                      <CardContent className="grid grid-cols-1 gap-2 border-t pt-3 sm:grid-cols-2">
                        <div className="rounded-md border bg-muted/30 p-2.5 text-xs">
                          <div className="font-medium text-muted-foreground">1. Identity</div>
                          <div className="mt-0.5 font-medium text-foreground">
                            {caseDetail.four_gate_evidence.gate1_identity.label}
                          </div>
                          <div className="text-[11px] text-muted-foreground">
                            {caseDetail.four_gate_evidence.gate1_identity.source}
                          </div>
                        </div>
                        <div className="rounded-md border bg-muted/30 p-2.5 text-xs">
                          <div className="font-medium text-muted-foreground">
                            2. State Licensure [PSV]
                          </div>
                          <div
                            className={cn(
                              "mt-0.5 font-medium",
                              caseDetail.four_gate_evidence.gate2_licensure.psv_required
                                ? "text-status-warning"
                                : "text-status-success"
                            )}
                          >
                            {caseDetail.four_gate_evidence.gate2_licensure.label}
                          </div>
                          <div className="text-[11px] text-muted-foreground">
                            {caseDetail.four_gate_evidence.gate2_licensure.psv_required
                              ? "PSV Required"
                              : "PSV Verified"}
                          </div>
                        </div>
                        <div className="rounded-md border bg-muted/30 p-2.5 text-xs">
                          <div className="font-medium text-muted-foreground">
                            3. Enrollment / LEIE
                          </div>
                          <div className="mt-0.5 font-medium text-foreground">
                            {caseDetail.four_gate_evidence.gate3_enrollment.label}
                          </div>
                          <div className="text-[11px] text-muted-foreground">
                            {exclusionLabel}
                          </div>
                        </div>
                        <div className="rounded-md border bg-muted/30 p-2.5 text-xs">
                          <div className="font-medium text-muted-foreground">
                            4. Directory / Panel
                          </div>
                          <div
                            className={cn(
                              "mt-0.5 font-medium",
                              caseDetail.four_gate_evidence.gate4_directory.hospital_based_newpt_leak
                                ? "text-status-warning"
                                : "text-foreground"
                            )}
                          >
                            {caseDetail.four_gate_evidence.gate4_directory.label}
                          </div>
                          <div className="text-[11px] text-muted-foreground">
                            {accepting == null ? "Panel status unknown" : accepting ? "Reported accepting new patients" : "Reported closed to new patients"}
                          </div>
                        </div>
                      </CardContent>
                    </CollapsibleContent>
                  </Card>
                </Collapsible>
              )}

              </div>
              <Tabs defaultValue="review" className="min-w-0">
                <TabsList className="h-auto min-h-8 w-full">
                  <TabsTrigger value="review" className="min-w-0 flex-1 whitespace-normal text-center text-xs leading-tight">
                    Review & Decide
                  </TabsTrigger>
                  <TabsTrigger value="timeline" className="min-w-0 flex-1 whitespace-normal text-center text-xs leading-tight">
                    Audit Timeline ({caseDetail.history.length})
                  </TabsTrigger>
                  <TabsTrigger value="evidence" className="min-w-0 flex-1 whitespace-normal text-center text-xs leading-tight">
                    Source Evidence
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="review" className="pt-4">
                  <form onSubmit={handleSubmit}>
                    <FieldGroup>
                      <Field>
                        <FieldLabel htmlFor="case-action">Workflow Action</FieldLabel>
                        <Select
                          value={action}
                          onValueChange={(v) => setAction(v as CaseActionInput["action"])}
                        >
                          <SelectTrigger id="case-action" className="w-full">
                            <SelectValue placeholder="Choose action" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectGroup>
                              {actions.map((opt) => (
                                <SelectItem key={opt.value} value={opt.value}>
                                  {opt.label}
                                </SelectItem>
                              ))}
                            </SelectGroup>
                          </SelectContent>
                        </Select>
                      </Field>

                      {action === "approve" && (
                        <Field>
                          <FieldLabel htmlFor="proposal-phone">Approved Phone (10 digits)</FieldLabel>
                          <Input
                            id="proposal-phone"
                            value={proposalPhone}
                            onChange={(e) => setProposalPhone(e.target.value)}
                            placeholder="6155550142"
                          />
                          <FieldDescription>
                            Approval records the proposed correction before payer submission.
                          </FieldDescription>
                        </Field>
                      )}

                      {action === "submit" && (
                        <Field>
                          <FieldLabel htmlFor="submission-ref">Payer Submission Reference</FieldLabel>
                          <Input
                            id="submission-ref"
                            required
                            value={submissionRef}
                            onChange={(e) => setSubmissionRef(e.target.value)}
                          />
                        </Field>
                      )}

                      {action === "verify" && (
                        <>
                          <Field>
                            <FieldLabel htmlFor="observed-phone">Observed Payer Directory Phone</FieldLabel>
                            <Input
                              id="observed-phone"
                            required
                              value={observedPhone}
                              onChange={(e) => setObservedPhone(e.target.value)}
                            />
                          </Field>
                          <Field>
                            <FieldLabel htmlFor="verification-note">Verification Note</FieldLabel>
                            <Input
                              id="verification-note"
                            required
                              value={verificationNote}
                              onChange={(e) => setVerificationNote(e.target.value)}
                            />
                          </Field>
                        </>
                      )}

                      {action === "assign" && (
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                          <Field>
                            <FieldLabel htmlFor="case-owner">Owner</FieldLabel>
                            <Input
                              id="case-owner"
                              value={owner}
                              onChange={(e) => setOwner(e.target.value)}
                            />
                          </Field>
                          <Field>
                            <FieldLabel htmlFor="case-followup">Follow-up Date</FieldLabel>
                            <Input
                              id="case-followup"
                              type="date"
                              value={followUp}
                              onChange={(e) => setFollowUp(e.target.value)}
                            />
                          </Field>
                        </div>
                      )}

                      {action === "outreach" && (
                        <>
                          <Field>
                            <FieldLabel htmlFor="outreach-outcome">Outreach Outcome</FieldLabel>
                            <Select
                              value={outreachOutcome}
                              onValueChange={(v) =>
                                setOutreachOutcome(
                                  v as "no_answer" | "message_left" | "response_received"
                                )
                              }
                            >
                              <SelectTrigger id="outreach-outcome" className="w-full">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectGroup>
                                  <SelectItem value="response_received">Response Received</SelectItem>
                                  <SelectItem value="message_left">Left Voicemail</SelectItem>
                                  <SelectItem value="no_answer">No Answer</SelectItem>
                                </SelectGroup>
                              </SelectContent>
                            </Select>
                          </Field>
                          {outreachOutcome === "response_received" && (
                            <Field>
                              <FieldLabel htmlFor="outreach-summary">Office Response Summary</FieldLabel>
                              <Input
                                id="outreach-summary"
                                value={outreachSummary}
                                onChange={(e) => setOutreachSummary(e.target.value)}
                                placeholder="Practice manager confirmed live scheduling number"
                              />
                            </Field>
                          )}
                        </>
                      )}

                      <Field>
                        <FieldLabel htmlFor="case-actor">Reviewer</FieldLabel>
                        <Input id="case-actor" value={actor} onChange={(e) => setActor(e.target.value)} />
                      </Field>

                      <Field>
                        <FieldLabel htmlFor="case-reason">Audit Rationale</FieldLabel>
                        <Textarea
                          id="case-reason"
                          rows={2}
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                          placeholder="Document the evidence supporting this transition…"
                        />
                      </Field>

                      {actionError && (
                        <Alert role="alert">
                          <AlertTitle>Decision not recorded</AlertTitle>
                          <AlertDescription>
                            <p>{actionError}</p>
                            {stale && <Button type="button" variant="outline" size="sm" className="mt-2" onClick={async () => {
                              try {
                                await onRefresh();
                                setStale(false);
                                setActionError(null);
                              } catch {
                                setActionError("Could not refresh the case. Try again before recording your decision.");
                              }
                            }}>Refresh case</Button>}
                          </AlertDescription>
                        </Alert>
                      )}
                      <Button type="submit" disabled={saving || stale}>
                        <CheckCircle2 data-icon="inline-start" />
                        {saving ? "Recording Decision…" : "Record Decision"}
                      </Button>
                      <p className="text-xs text-muted-foreground">Case revision {caseDetail.version}</p>
                    </FieldGroup>
                  </form>
                </TabsContent>

                <TabsContent value="timeline" className="pt-4">
                  {caseDetail.history.length === 0 ? (
                    <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                      No transitions recorded yet. Start by triaging or logging outreach.
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      {caseDetail.history.map((ev) => (
                        <div key={ev.id} className="rounded-lg border bg-card p-3.5 text-sm">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2 font-medium">
                              <Clock className="size-3.5 text-muted-foreground" />
                              <span className="capitalize">{ev.action}</span>
                              <span className="text-xs font-normal text-muted-foreground">
                                {statusLabel(ev.from_status)} → {statusLabel(ev.to_status)}
                              </span>
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {formatDateTime(ev.occurred_at)}
                            </span>
                          </div>
                          <p className="mt-1.5 text-xs text-foreground">{ev.reason}</p>
                          <p className="mt-1 text-xs text-muted-foreground">Actor: {ev.actor}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="evidence" className="flex flex-col gap-4 pt-4">
                  <div className="grid grid-cols-2 gap-3 rounded-lg border bg-muted/40 p-3.5 text-xs">
                    <div>
                      <span className="text-muted-foreground">Source Namespace</span>
                      <div className="mt-0.5 font-medium">{caseDetail.source}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Row Locator</span>
                      <div className="mt-0.5 font-mono font-medium">
                        {caseDetail.evidence.locator}
                      </div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Designation</span>
                      <div className="mt-0.5 font-medium capitalize">
                        {caseDetail.evidence.designation}
                      </div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Receipt ID</span>
                      <div className="mt-0.5 truncate font-mono font-medium">
                        {caseDetail.evidence.receipt_id}
                      </div>
                    </div>
                  </div>

                  <Collapsible>
                    <CollapsibleTrigger asChild>
                      <Button variant="outline" size="sm" className="w-full justify-between">
                        <span>Inspect Raw Payload JSON</span>
                        <ChevronDown data-icon="inline-end" />
                      </Button>
                    </CollapsibleTrigger>
                    <CollapsibleContent className="pt-2">
                      <pre className="max-h-64 overflow-auto rounded-lg border bg-muted p-3 font-mono text-xs text-foreground">
                        {JSON.stringify(
                          {
                            normalized: caseDetail.evidence.normalized,
                            original: caseDetail.evidence.original,
                          },
                          null,
                          2
                        )}
                      </pre>
                    </CollapsibleContent>
                  </Collapsible>
                </TabsContent>
              </Tabs>
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
