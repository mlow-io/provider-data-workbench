import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Download,
  FileWarning,
  Search,
} from "lucide-react";
import { toast } from "sonner";
import { RiskBadge, StatusBadge } from "@/components/shared/StatusBadge";
import { CaseInspectorSheet } from "@/components/work/CaseInspectorSheet";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
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
import { dataClient } from "@/lib/dataClient";
import {
  clinicDisplayName,
  extractLocationCode,
  formatPhone,
  formatShortDate,
} from "@/lib/format";
import type { CaseActionInput, WorkCaseSummary } from "@/lib/types";
import { updateWorkspaceQuery, useWorkspaceQuery } from "@/workspaceNavigation";

function compactDiff(row: WorkCaseSummary): string {
  const rightRaw = row.proposal ?? row.reference_value;
  if (!row.listing_value && !rightRaw) {
    return row.kind === "qa"
      ? "Verify accepted observation & suppression status"
      : "Inspect source record & normalization";
  }
  const left =
    row.field_name === "phone" && row.listing_value
      ? formatPhone(row.listing_value)
      : row.listing_value ?? "Not set";
  const right =
    row.field_name === "phone" && rightRaw
      ? formatPhone(rightRaw)
      : rightRaw ?? "Pending";
  return `${left} → ${right}`;
}

export function WorkQueuePage() {
  const queryClient = useQueryClient();
  const urlQuery = useWorkspaceQuery();
  const requestedCaseId = urlQuery.get("case");

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("open");
  const [riskFilter, setRiskFilter] = useState("all");
  const [clinicFilter, setClinicFilter] = useState("all");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(requestedCaseId);

  useEffect(() => {
    if (requestedCaseId) setSelectedCaseId(requestedCaseId);
  }, [requestedCaseId]);

  const overviewQuery = useQuery({
    queryKey: ["workbench-overview"],
    queryFn: () => dataClient.overview(),
  });

  const casesQuery = useQuery({
    queryKey: ["work-queue"],
    queryFn: () => dataClient.workQueue(),
  });

  const detailQuery = useQuery({
    queryKey: ["work-case-detail", selectedCaseId],
    queryFn: () => dataClient.caseDetail(selectedCaseId!),
    enabled: Boolean(selectedCaseId),
  });

  const clinics = useMemo(() => {
    const items = casesQuery.data ?? [];
    const seen = new Map<string, string>();
    for (const item of items) {
      const code = item.location_code ?? extractLocationCode(item.location_id);
      if (code && !seen.has(code)) {
        seen.set(code, item.clinic_name ?? clinicDisplayName(code));
      }
    }
    return Array.from(seen.entries());
  }, [casesQuery.data]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (casesQuery.data ?? []).filter((item) => {
      const isClosed = ["verified", "resolved", "deferred"].includes(item.status);
      if (statusFilter === "open" && isClosed) return false;
      if (statusFilter !== "all" && statusFilter !== "open" && item.status !== statusFilter) {
        return false;
      }
      if (riskFilter !== "all" && item.risk_level !== riskFilter) return false;
      const code = item.location_code ?? extractLocationCode(item.location_id);
      if (clinicFilter !== "all" && code !== clinicFilter) return false;
      if (q) {
        const hay = `${item.provider_name} ${item.npi ?? ""} ${item.issue} ${code} ${item.clinic_name ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [casesQuery.data, search, statusFilter, riskFilter, clinicFilter]);

  const columns = useMemo<ColumnDef<WorkCaseSummary>[]>(
    () => [
      {
        id: "provider",
        header: "Clinician & NPI",
        cell: ({ row }) => (
          <div className="flex flex-col">
            <span className="font-medium text-foreground">{row.original.provider_name}</span>
            <span className="font-mono text-xs text-muted-foreground">
              {row.original.npi ? `NPI ${row.original.npi}` : row.original.source}
            </span>
          </div>
        ),
      },
      {
        id: "clinic",
        header: "Clinic Site",
        cell: ({ row }) => {
          const code = row.original.location_code ?? extractLocationCode(row.original.location_id);
          return (
            <div className="flex flex-col">
              <span className="text-foreground">
                {row.original.clinic_name ?? clinicDisplayName(code)}
              </span>
              <span className="font-mono text-xs text-muted-foreground">{code}</span>
            </div>
          );
        },
      },
      {
        id: "discrepancy",
        header: "Discrepancy & Diff",
        cell: ({ row }) => (
          <div className="flex max-w-md flex-col gap-0.5">
            <span className="truncate font-medium text-foreground">{row.original.issue}</span>
            <span className="truncate font-mono text-xs text-muted-foreground">
              {compactDiff(row.original)}
            </span>
          </div>
        ),
      },
      {
        id: "risk",
        header: "Risk",
        cell: ({ row }) => <RiskBadge risk={row.original.risk_level} />,
      },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
      },
      {
        id: "sla",
        header: "Updated",
        cell: ({ row }) => (
          <div className="flex flex-col text-xs text-muted-foreground tabular-nums">
            <span>{formatShortDate(row.original.updated_at)}</span>
            {row.original.follow_up && (
              <span>Due {formatShortDate(row.original.follow_up)}</span>
            )}
          </div>
        ),
      },
    ],
    []
  );

  const table = useReactTable({
    data: filtered,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  async function handleRecordEvent(caseId: string, payload: CaseActionInput) {
    await dataClient.recordCaseEvent(caseId, payload);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["work-queue"] }),
      queryClient.invalidateQueries({ queryKey: ["work-case-detail", caseId] }),
      queryClient.invalidateQueries({ queryKey: ["workbench-overview"] }),
      queryClient.invalidateQueries({ queryKey: ["directory-records"] }),
    ]);
  }

  function openCase(caseId: string) {
    setSelectedCaseId(caseId);
    updateWorkspaceQuery({ case: caseId }, true);
  }

  function closeSheet(nextOpen: boolean) {
    if (!nextOpen) {
      setSelectedCaseId(null);
      updateWorkspaceQuery({ case: null }, true);
    }
  }

  const ov = overviewQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Provider Discrepancy Work Queue
        </h1>
        <p className="text-sm text-muted-foreground">
          Investigate directory phone, suite, and visibility discrepancies with side-by-side source
          diffs and an append-only audit trail.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card size="sm">
          <CardHeader className="pb-1">
            <CardDescription className="flex items-center justify-between">
              <span>Directory Clean Rate</span>
              <CheckCircle2 className="size-4 text-status-success" />
            </CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums">
              {ov ? `${ov.clean_rate_pct}%` : <Skeleton className="h-7 w-16" />}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground">
            {ov
              ? `${ov.total_providers} clinicians across ${ov.total_locations} Middle TN clinics`
              : "Loading metrics…"}
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader className="pb-1">
            <CardDescription className="flex items-center justify-between">
              <span>Open Discrepancies</span>
              <AlertTriangle className="size-4 text-status-warning" />
            </CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums">
              {ov ? ov.open_discrepancies : <Skeleton className="h-7 w-12" />}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground">
            {ov ? `${ov.high_risk_discrepancies} high-risk patient contact items` : "Loading…"}
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader className="pb-1">
            <CardDescription className="flex items-center justify-between">
              <span>Held Deliveries</span>
              <FileWarning className="size-4 text-status-danger" />
            </CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums">
              {ov ? ov.held_deliveries : <Skeleton className="h-7 w-12" />}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground">
            {ov
              ? `${ov.quarantined_rows} quarantined ${ov.quarantined_rows === 1 ? "row" : "rows"} held safely off live roster`
              : "Loading…"}
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader className="pb-1">
            <CardDescription className="flex items-center justify-between">
              <span>NSA 2-Day SLA At-Risk</span>
              <Clock className="size-4 text-primary" />
            </CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums">
              {ov ? ov.sla_at_risk : <Skeleton className="h-7 w-12" />}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground">
            {ov
              ? `${ov.schema_variants_count} reviewed schema ${ov.schema_variants_count === 1 ? "variant" : "variants"} active`
              : "Loading…"}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="border-b">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle>Active Cases</CardTitle>
              <CardDescription>
                Select any row to compare current directory data against incoming clinic or NPPES
                evidence.
              </CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  await dataClient.downloadWorkQueueCsv(filtered);
                  toast.success("Exported work queue CSV");
                }}
              >
                <Download data-icon="inline-start" />
                Export CSV
              </Button>
            </div>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <div className="relative">
              <Search className="pointer-events-none absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
              <Input
                aria-label="Search work queue"
                placeholder="Search clinician, NPI, clinic…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8"
              />
            </div>

            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger aria-label="Filter by status" className="w-full">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="open">Open Cases</SelectItem>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="new">New</SelectItem>
                  <SelectItem value="triaged">Triaged</SelectItem>
                  <SelectItem value="pending_verification">Awaiting Verification</SelectItem>
                  <SelectItem value="needs_information">Needs Info</SelectItem>
                  <SelectItem value="verified">Verified</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>

            <Select value={riskFilter} onValueChange={setRiskFilter}>
              <SelectTrigger aria-label="Filter by risk" className="w-full">
                <SelectValue placeholder="Risk" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">All Risk Levels</SelectItem>
                  <SelectItem value="high">High Risk</SelectItem>
                  <SelectItem value="medium">Medium Risk</SelectItem>
                  <SelectItem value="low">Low Risk</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>

            <Select value={clinicFilter} onValueChange={setClinicFilter}>
              <SelectTrigger aria-label="Filter by clinic" className="w-full">
                <SelectValue placeholder="All Clinics" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">All Middle TN Clinics</SelectItem>
                  {clinics.map(([code, name]) => (
                    <SelectItem key={code} value={code}>
                      {name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {casesQuery.isLoading ? (
            <div className="flex flex-col gap-2 p-6">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : filtered.length === 0 ? (
            <Empty className="m-6 border">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <CheckCircle2 />
                </EmptyMedia>
                <EmptyTitle>No matching discrepancies</EmptyTitle>
                <EmptyDescription>
                  No work queue cases match the active filters. Clear filters to view all cases.
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSearch("");
                    setStatusFilter("all");
                    setRiskFilter("all");
                    setClinicFilter("all");
                  }}
                >
                  Show All Cases
                </Button>
              </EmptyContent>
            </Empty>
          ) : (
            <Table>
              <TableHeader>
                {table.getHeaderGroups().map((headerGroup) => (
                  <TableRow key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <TableHead key={header.id}>
                        {flexRender(header.column.columnDef.header, header.getContext())}
                      </TableHead>
                    ))}
                    <TableHead className="w-10" />
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {table.getRowModel().rows.map((row) => (
                  <TableRow
                    key={row.original.id}
                    className="cursor-pointer"
                    onClick={() => openCase(row.original.id)}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    ))}
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`Inspect ${row.original.provider_name}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          openCase(row.original.id);
                        }}
                      >
                        <ArrowRight />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <CaseInspectorSheet
        open={Boolean(selectedCaseId)}
        caseDetail={detailQuery.data ?? null}
        loading={detailQuery.isLoading}
        onOpenChange={closeSheet}
        onRecordEvent={handleRecordEvent}
      />
    </div>
  );
}
