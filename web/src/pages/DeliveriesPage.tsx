import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, CheckCircle2, Download, PhoneCall, ShieldCheck, XCircle } from "lucide-react";
import { toast } from "sonner";
import { ExportDialog } from "@/components/deliveries/ExportDialog";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { dataClient } from "@/lib/dataClient";
import { clinicDisplayName, formatPhone, formatShortDate } from "@/lib/format";
import type { FeedVersionSummary } from "@/lib/types";
import { useWorkspaceQuery } from "@/workspaceNavigation";

function versionTitle(ver: Pick<FeedVersionSummary, "kind" | "period">) {
  return ver.kind === "derived_field_candidate"
    ? "Reviewed phone correction"
    : `${formatShortDate(ver.period)} Delivery`;
}

export function DeliveriesPage() {
  const queryClient = useQueryClient();
  const requestedVersion = useWorkspaceQuery().get("version");
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(requestedVersion);
  const [rowFilter, setRowFilter] = useState("all");
  const [rowSearch, setRowSearch] = useState("");
  const [exportOpen, setExportOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const feedsQuery = useQuery({
    queryKey: ["managed-feeds"],
    queryFn: () => dataClient.feeds(),
  });

  const primaryFeed = feedsQuery.data?.[0] ?? null;

  useEffect(() => {
    if (requestedVersion) setSelectedVersionId(requestedVersion);
  }, [requestedVersion]);

  useEffect(() => {
    if (!primaryFeed || selectedVersionId) return;
    const candidate = primaryFeed.versions.find((v) => v.state === "candidate");
    setSelectedVersionId(candidate?.id ?? primaryFeed.versions[0]?.id ?? null);
  }, [primaryFeed, selectedVersionId]);

  const versionQuery = useQuery({
    queryKey: ["feed-version", selectedVersionId],
    queryFn: () => dataClient.feedVersion(selectedVersionId!),
    enabled: Boolean(selectedVersionId),
  });

  const version = versionQuery.data ?? null;

  const availableLocations = useMemo(() => {
    const map = new Map<string, string>();
    for (const row of version?.rows ?? []) {
      const code = String(row.normalized.location_id ?? "");
      if (code && !map.has(code)) {
        map.set(code, clinicDisplayName(code));
      }
    }
    return Array.from(map.entries()).map(([code, name]) => ({ code, name }));
  }, [version]);

  const filteredRows = useMemo(() => {
    const q = rowSearch.trim().toLowerCase();
    return (version?.rows ?? []).filter((row) => {
      const hasProblems = row.problems.length > 0;
      if (rowFilter === "quarantined" && !hasProblems) return false;
      if (rowFilter === "changed" && row.comparison !== "changed") return false;
      if (rowFilter === "new" && row.comparison !== "new") return false;
      if (q) {
        const hay = `${row.normalized.provider_name ?? ""} ${row.normalized.npi ?? ""} ${row.normalized.location_id ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [version, rowFilter, rowSearch]);

  const softHolds = useMemo(
    () => (version?.report.findings ?? []).filter((f) => f.severity === "hold"),
    [version]
  );
  const acknowledgedCodes = useMemo(
    () =>
      new Set(
        (version?.review ?? [])
          .filter((r) => r.disposition === "acknowledged")
          .map((r) => r.code)
      ),
    [version]
  );
  const allHoldsAcked = softHolds.every((h) => acknowledgedCodes.has(h.code));
  const lineage = version?.manifest?.materialization ?? null;

  async function handleAcknowledge(code: string) {
    if (!version) return;
    setBusy(true);
    try {
      await dataClient.acknowledgeHold({
        versionId: version.id,
        code,
        expectedReport: version.report_hash,
        actor: "M. Brooks",
        reason: `Reviewed ${code} quality impact before release decision`,
      });
      await queryClient.invalidateQueries({ queryKey: ["feed-version", version.id] });
      toast.success(`Acknowledged hold: ${code}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not acknowledge hold");
    } finally {
      setBusy(false);
    }
  }

  async function handleDecide(decision: "approved" | "rejected") {
    if (!version || !primaryFeed) return;
    setBusy(true);
    try {
      await dataClient.decideFeedVersion({
        versionId: version.id,
        decision,
        expectedReport: version.report_hash,
        expectedCurrent: primaryFeed.current_version,
        actor: "Operations Lead",
        reason: lineage
          ? decision === "approved"
            ? "Approved reviewed phone correction"
            : "Rejected reviewed phone correction candidate"
          : decision === "approved"
            ? "Acknowledged holds and approved roster version"
            : "Rejected incomplete candidate to protect active baseline",
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["managed-feeds"] }),
        queryClient.invalidateQueries({ queryKey: ["feed-version", version.id] }),
        queryClient.invalidateQueries({ queryKey: ["workbench-overview"] }),
      ]);
      toast.success(
        decision === "approved" ? "Dataset version approved" : "Candidate rejected"
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Decision failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Recurring Deliveries & Approved Exports
        </h1>
        <p className="text-sm text-muted-foreground">
          Incomplete rosters are held automatically so missing clinics never drop from the active
          approved directory.
        </p>
      </div>

      {feedsQuery.isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : !primaryFeed ? (
        <Alert>
          <AlertTitle>No recurring feeds registered</AlertTitle>
          <AlertDescription>Register or seed a feed to compare versions.</AlertDescription>
        </Alert>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="flex flex-col gap-4 lg:col-span-4">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-base">{primaryFeed.name}</CardTitle>
                  <Badge variant="secondary">Enabled</Badge>
                </div>
                <CardDescription>
                  Source: <span className="font-mono">{primaryFeed.source}</span> · Owner:{" "}
                  {primaryFeed.config.owner}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-2.5">
                {primaryFeed.versions.map((ver) => {
                  const active = ver.id === selectedVersionId;
                  const isCurrent = ver.id === primaryFeed.current_version;
                  return (
                    <button
                      key={ver.id}
                      type="button"
                      onClick={() => setSelectedVersionId(ver.id)}
                      className={`flex flex-col gap-1.5 rounded-lg border p-3.5 text-left transition-colors ${
                        active
                          ? "border-primary bg-accent/60"
                          : "bg-card hover:bg-muted/40"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-foreground">
                          {versionTitle(ver)}
                        </span>
                        <StatusBadge
                          status={ver.state}
                          label={
                            ver.kind === "derived_field_candidate" && ver.state === "candidate"
                              ? "Awaiting Approval"
                              : undefined
                          }
                        />
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span className="font-mono">
                          {ver.kind === "derived_field_candidate"
                            ? `from ${ver.delivery_id}`
                            : ver.delivery_id}
                        </span>
                        {isCurrent && (
                          <Badge
                            variant="outline"
                            className="border-transparent bg-status-success-bg text-status-success"
                          >
                            Live Consumer Baseline
                          </Badge>
                        )}
                      </div>
                    </button>
                  );
                })}
              </CardContent>
            </Card>
          </div>

          <div className="flex flex-col gap-4 lg:col-span-8">
            {versionQuery.isLoading || !version ? (
              <Skeleton className="h-96 w-full" />
            ) : (
              <Card>
                <CardHeader className="border-b">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <CardTitle>
                          {lineage ? "Reviewed phone correction" : version.delivery.filename}
                        </CardTitle>
                        <StatusBadge
                          status={version.state}
                          label={lineage && version.state === "candidate" ? "Awaiting Approval" : undefined}
                        />
                      </div>
                      <CardDescription>
                        {lineage
                          ? `Derived from the approved ${formatShortDate(version.delivery.period)} roster`
                          : `Period ${formatShortDate(version.delivery.period)} · ${version.delivery.delivery_id}`}
                      </CardDescription>
                    </div>
                    <Button
                      disabled={version.state !== "approved"}
                      onClick={() => setExportOpen(true)}
                    >
                      <Download data-icon="inline-start" />
                      Export Approved Roster
                    </Button>
                  </div>
                </CardHeader>

                <CardContent className="flex flex-col gap-5 pt-5">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <div className="rounded-lg border p-3">
                      <div className="text-xs text-muted-foreground">Raw Rows</div>
                      <div className="mt-1 text-xl font-semibold tabular-nums">
                        {version.report.counts.raw ?? version.row_count}
                      </div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="text-xs text-muted-foreground">Valid Rows</div>
                      <div className="mt-1 text-xl font-semibold tabular-nums">
                        {version.report.counts.valid ?? 0}
                      </div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="text-xs text-muted-foreground">Missing from Baseline</div>
                      <div className="mt-1 text-xl font-semibold tabular-nums">
                        {version.report.comparison?.missing_from_this_delivery ?? 0}
                      </div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="text-xs text-muted-foreground">Quarantined</div>
                      <div className="mt-1 text-xl font-semibold tabular-nums">
                        {version.report.counts.quarantined ?? 0}
                      </div>
                    </div>
                  </div>

                  {lineage && (
                    <div className="flex flex-col gap-3 rounded-lg border p-3.5">
                      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                        <PhoneCall className="size-4 text-muted-foreground" aria-hidden="true" />
                        Correction lineage
                      </div>
                      <div className="flex flex-wrap items-center gap-3 font-mono text-sm">
                        <span className="line-through decoration-muted-foreground/60">
                          {formatPhone(lineage.old_value.number, lineage.old_value.extension)}
                        </span>
                        <ArrowRight className="size-4 text-muted-foreground" aria-label="changed to" />
                        <span className="font-medium">
                          {formatPhone(lineage.new_value.number, lineage.new_value.extension)}
                        </span>
                        <span className="text-xs text-muted-foreground">row {lineage.row_locator}</span>
                      </div>
                      <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-xs sm:grid-cols-[max-content_1fr]">
                        <dt className="text-muted-foreground">Selected source</dt>
                        <dd className="font-mono">
                          {lineage.selected_evidence.source} · {lineage.selected_evidence.locator}
                        </dd>
                        <dt className="text-muted-foreground">Phone decision</dt>
                        <dd>{lineage.decision_reason}</dd>
                        <dt className="text-muted-foreground">Candidate</dt>
                        <dd>
                          {lineage.actor}: {lineage.reason}
                        </dd>
                      </dl>
                      {version.state === "candidate" && (
                        <p className="text-xs text-muted-foreground">
                          Every other row matches the approved base. Approval rechecks the base, links,
                          decision and source file, and rejects the candidate if any changed.
                        </p>
                      )}
                    </div>
                  )}

                  {version.state === "candidate" && (
                    <Alert>
                      {softHolds.length > 0 ? (
                        <AlertTriangle className="size-4 text-status-warning" />
                      ) : (
                        <ShieldCheck className="size-4" />
                      )}
                      <AlertTitle>
                        {softHolds.length > 0
                          ? "Candidate Held Automatically — Active Approved Baseline Protected"
                          : "Candidate Awaiting Approval — Active Approved Baseline Protected"}
                      </AlertTitle>
                      <AlertDescription className="mt-2 flex flex-col gap-3">
                        <div className="flex flex-col gap-2">
                          {softHolds.map((hold) => {
                            const acked = acknowledgedCodes.has(hold.code);
                            return (
                              <div
                                key={hold.code}
                                className="flex flex-col gap-2 rounded-lg border bg-card p-3 sm:flex-row sm:items-center sm:justify-between"
                              >
                                <div className="flex flex-col gap-0.5">
                                  <span className="font-mono text-xs font-medium text-foreground">
                                    {hold.code}
                                  </span>
                                  <span className="text-xs text-muted-foreground">
                                    {hold.message}
                                  </span>
                                </div>
                                <Button
                                  variant={acked ? "secondary" : "outline"}
                                  size="xs"
                                  disabled={acked || busy}
                                  onClick={() => handleAcknowledge(hold.code)}
                                >
                                  <CheckCircle2 data-icon="inline-start" />
                                  {acked ? "Acknowledged" : "Acknowledge Hold"}
                                </Button>
                              </div>
                            );
                          })}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            disabled={!allHoldsAcked || busy}
                            onClick={() => handleDecide("approved")}
                          >
                            <ShieldCheck data-icon="inline-start" />
                            Approve & Promote Version
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={busy}
                            onClick={() => handleDecide("rejected")}
                          >
                            <XCircle data-icon="inline-start" />
                            Reject Candidate
                          </Button>
                        </div>
                      </AlertDescription>
                    </Alert>
                  )}

                  {version.decision && (
                    <div className="rounded-lg border bg-muted/40 p-3 text-xs text-muted-foreground">
                      <span className="font-medium text-foreground capitalize">
                        {version.decision.decision}
                      </span>{" "}
                      by {version.decision.actor} on {formatShortDate(version.decision.created_at)}:{" "}
                      {version.decision.reason}
                    </div>
                  )}

                  <Tabs defaultValue="rows">
                    <TabsList>
                      <TabsTrigger value="rows">
                        Delivery Rows ({version.rows.length})
                      </TabsTrigger>
                      <TabsTrigger value="findings">
                        Quality Findings ({version.report.findings.length})
                      </TabsTrigger>
                    </TabsList>

                    <TabsContent value="rows" className="flex flex-col gap-3 pt-4">
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <Input
                          aria-label="Filter delivery rows"
                          placeholder="Filter by clinician, NPI, clinic…"
                          value={rowSearch}
                          onChange={(e) => setRowSearch(e.target.value)}
                        />
                        <Select value={rowFilter} onValueChange={setRowFilter}>
                          <SelectTrigger aria-label="Filter row change state" className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectGroup>
                              <SelectItem value="all">All Delivery Rows</SelectItem>
                              <SelectItem value="changed">Changed Rows</SelectItem>
                              <SelectItem value="new">New Rows</SelectItem>
                              <SelectItem value="quarantined">Quarantined Only</SelectItem>
                            </SelectGroup>
                          </SelectContent>
                        </Select>
                      </div>

                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Clinician</TableHead>
                            <TableHead>Clinic</TableHead>
                            <TableHead>Phone</TableHead>
                            <TableHead>Comparison</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {filteredRows.map((row) => (
                            <TableRow key={row.locator}>
                              <TableCell>
                                <div className="flex flex-col">
                                  <span className="font-medium">
                                    {String(row.normalized.provider_name ?? "—")}
                                  </span>
                                  <span className="font-mono text-xs text-muted-foreground">
                                    {String(row.normalized.npi ?? "")}
                                  </span>
                                </div>
                              </TableCell>
                              <TableCell className="text-xs">
                                {clinicDisplayName(String(row.normalized.location_id ?? ""))}
                              </TableCell>
                              <TableCell className="font-mono text-xs">
                                {formatPhone(
                                  String(row.normalized.phone ?? ""),
                                  (row.normalized.phone_extension as string | null | undefined) ?? null
                                )}
                              </TableCell>
                              <TableCell>
                                {row.materialization ? (
                                  <Badge
                                    variant="outline"
                                    className="border-transparent bg-status-success-bg text-status-success"
                                  >
                                    Corrected
                                  </Badge>
                                ) : row.problems.length > 0 ? (
                                  <Badge
                                    variant="outline"
                                    className="border-transparent bg-status-danger-bg text-status-danger"
                                  >
                                    Quarantined: {row.problems[0]}
                                  </Badge>
                                ) : (
                                  <Badge variant="secondary" className="capitalize">
                                    {row.comparison ?? "valid"}
                                  </Badge>
                                )}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TabsContent>

                    <TabsContent value="findings" className="flex flex-col gap-2 pt-4">
                      {version.report.findings.map((finding, idx) => (
                        <div
                          key={`${finding.code}-${idx}`}
                          className="flex flex-col gap-1 rounded-lg border p-3 text-xs"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-mono font-medium">{finding.code}</span>
                            <Badge variant="secondary">{finding.severity}</Badge>
                          </div>
                          <span className="text-muted-foreground">{finding.message}</span>
                        </div>
                      ))}
                    </TabsContent>
                  </Tabs>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}

      <ExportDialog
        open={exportOpen}
        versionId={version?.id ?? null}
        availableLocations={availableLocations}
        onOpenChange={setExportOpen}
      />
    </div>
  );
}
