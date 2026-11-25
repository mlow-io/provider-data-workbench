import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { ArrowUpRight, Building2, Eye, EyeOff, Info, Search, ShieldAlert, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { dataClient } from "@/lib/dataClient";
import { daysUntilNsaCheck, formatPhone } from "@/lib/format";
import type { DirectoryRecord } from "@/lib/types";
import { navigateWorkspace } from "@/workspaceNavigation";

export function ProviderDirectoryPage() {
  const [search, setSearch] = useState("");
  const [clinic, setClinic] = useState("all");
  const [network, setNetwork] = useState("all");
  const [visibility, setVisibility] = useState("all");
  const [quickFilter, setQuickFilter] = useState<"all" | "exceptions" | "issues" | "suppressed">("all");

  const directoryQuery = useQuery({
    queryKey: ["directory-records"],
    queryFn: () => dataClient.directory(),
  });

  const isExceptionRow = (item: DirectoryRecord) =>
    Boolean(
      item.hospital_based_newpt_risk ||
        !item.directory_visible ||
        item.four_gate_evidence?.gate2_licensure.status ===
          "out_of_state_license_only_unverified_psv"
    );

  const counts = useMemo(() => {
    const items = directoryQuery.data ?? [];
    return {
      all: items.length,
      exceptions: items.filter(isExceptionRow).length,
      issues: items.filter((i) => i.open_issues > 0).length,
      suppressed: items.filter((i) => !i.directory_visible).length,
    };
  }, [directoryQuery.data]);

  const clinics = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of directoryQuery.data ?? []) {
      if (!map.has(item.location_code)) {
        map.set(item.location_code, item.location_name);
      }
    }
    return Array.from(map.entries());
  }, [directoryQuery.data]);

  const networks = useMemo(() => {
    const set = new Set<string>();
    for (const item of directoryQuery.data ?? []) {
      item.networks.forEach((n) => set.add(n));
    }
    return Array.from(set).sort();
  }, [directoryQuery.data]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (directoryQuery.data ?? []).filter((item) => {
      if (quickFilter === "exceptions" && !isExceptionRow(item)) return false;
      if (quickFilter === "issues" && item.open_issues === 0) return false;
      if (quickFilter === "suppressed" && item.directory_visible) return false;
      if (clinic !== "all" && item.location_code !== clinic) return false;
      if (network !== "all" && !item.networks.includes(network)) return false;
      if (visibility === "listed" && !item.directory_visible) return false;
      if (visibility === "excluded" && item.directory_visible) return false;
      if (q) {
        const hay = `${item.provider_name} ${item.npi} ${item.specialty} ${item.location_name} ${item.city}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [directoryQuery.data, quickFilter, search, clinic, network, visibility]);

  const columns = useMemo<ColumnDef<DirectoryRecord>[]>(
    () => [
      {
        id: "clinician",
        header: "Clinician & Taxonomy",
        cell: ({ row }) => (
          <div className="flex flex-col">
            <span className="font-medium text-foreground">{row.original.provider_name}</span>
            <span className="text-xs text-muted-foreground">{row.original.specialty}</span>
            {row.original.hospital_based_newpt_risk && (
              <Badge
                variant="outline"
                className="mt-1 w-fit border-transparent bg-status-warning-bg text-status-warning"
              >
                Hospital-Based newpt
              </Badge>
            )}
          </div>
        ),
      },
      {
        id: "npi",
        header: () => (
          <div className="inline-flex items-center gap-1">
            <span>NPI & Checksum</span>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    aria-label="Primary-source licensure verification note"
                    className="inline-flex text-muted-foreground hover:text-foreground"
                  >
                    <Info className="size-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  Self-reported licensure states always require primary-source board verification (PSV).
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        ),
        cell: ({ row }) => (
          <div className="flex flex-col gap-1">
            <span className="font-mono text-xs font-medium tabular-nums">{row.original.npi}</span>
            {row.original.npi_luhn_valid ? (
              <Badge
                variant="outline"
                className="w-fit border-transparent bg-status-success-bg text-status-success"
              >
                <ShieldCheck className="size-3" />
                Luhn Valid
              </Badge>
            ) : (
              <Badge
                variant="outline"
                className="w-fit border-transparent bg-status-danger-bg text-status-danger"
              >
                <ShieldAlert className="size-3" />
                Invalid Checksum
              </Badge>
            )}
            {row.original.four_gate_evidence?.gate2_licensure.status ===
              "out_of_state_license_only_unverified_psv" && (
              <span className="text-xs font-medium text-status-warning">
                Out-of-state license · PSV Required
              </span>
            )}
          </div>
        ),
      },
      {
        id: "location",
        header: "Practice Location",
        cell: ({ row }) => (
          <div className="flex flex-col">
            <span className="font-medium text-foreground">{row.original.location_name}</span>
            <span className="text-xs text-muted-foreground">
              {row.original.address}, {row.original.city}, {row.original.state} {row.original.zip}
            </span>
          </div>
        ),
      },
      {
        id: "phone",
        header: "Scheduling Phone",
        cell: ({ row }) => (
          <span className="font-mono text-xs tabular-nums">
            {formatPhone(row.original.phone, row.original.phone_extension)}
          </span>
        ),
      },
      {
        id: "networks",
        header: "Networks & Visibility",
        cell: ({ row }) => (
          <div className="flex flex-col gap-1">
            <div className="flex flex-wrap gap-1">
              {row.original.networks.length > 0 ? (
                row.original.networks.map((net) => (
                  <Badge key={net} variant="secondary" className="text-xs font-normal">
                    {net}
                  </Badge>
                ))
              ) : (
                <span className="text-xs text-muted-foreground">Unassigned</span>
              )}
            </div>
            {row.original.directory_visible ? (
              <span className="inline-flex items-center gap-1 text-xs text-status-success">
                <Eye className="size-3" /> Publicly Listed
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-xs text-status-warning">
                <EyeOff className="size-3" /> Directory Suppressed
              </span>
            )}
            {row.original.regulatory_regimes && row.original.regulatory_regimes.length > 0 && (
              <span className="text-[11px] text-muted-foreground">
                {row.original.regulatory_regimes.map((r) => r.label).join(" · ")}
              </span>
            )}
          </div>
        ),
      },
      {
        id: "nsa",
        header: "NSA 90-Day",
        cell: ({ row }) => {
          const check = daysUntilNsaCheck(row.original.verified_at);
          return (
            <Badge
              variant="outline"
              className={
                check.compliant
                  ? "border-transparent bg-status-success-bg text-status-success"
                  : "border-transparent bg-status-warning-bg text-status-warning"
              }
            >
              {check.daysAgo === 0 ? "Verified today" : `Verified ${check.daysAgo}d ago`}
            </Badge>
          );
        },
      },
      {
        id: "issues",
        header: "Status",
        cell: ({ row }) =>
          row.original.open_issues > 0 && row.original.primary_case_id ? (
            <Button
              variant="outline"
              size="xs"
              onClick={() =>
                navigateWorkspace("work", { case: row.original.primary_case_id })
              }
            >
              {row.original.open_issues} Open Issue
              <ArrowUpRight data-icon="inline-end" />
            </Button>
          ) : (
            <Badge variant="secondary">Clean</Badge>
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

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Provider & Clinic Directory
        </h1>
        <p className="text-sm text-muted-foreground">
          Unified view of active Middle Tennessee clinician-location listings, CMS Luhn NPI checks,
          network memberships, and No Surprises Act 90-day freshness.
        </p>
      </div>

      <Card>
        <CardHeader className="border-b">
          <div className="flex flex-col gap-1">
            <CardTitle>Directory Listings ({filtered.length})</CardTitle>
            <CardDescription>
              Directory visibility stays separate from network participation so suppression flags
              never erase active contracts.
            </CardDescription>
          </div>
          <Tabs
            value={quickFilter}
            onValueChange={(v) => setQuickFilter(v as typeof quickFilter)}
            className="mt-3"
          >
            <TabsList className="flex-wrap">
              <TabsTrigger value="all">All ({counts.all})</TabsTrigger>
              <TabsTrigger value="exceptions">Exceptions ({counts.exceptions})</TabsTrigger>
              <TabsTrigger value="issues">Open Issues ({counts.issues})</TabsTrigger>
              <TabsTrigger value="suppressed">Suppressed ({counts.suppressed})</TabsTrigger>
            </TabsList>
          </Tabs>
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <div className="relative">
              <Search className="pointer-events-none absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
              <Input
                aria-label="Search directory"
                placeholder="Search clinician, NPI, taxonomy…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8"
              />
            </div>

            <Select value={clinic} onValueChange={setClinic}>
              <SelectTrigger aria-label="Filter by clinic" className="w-full">
                <SelectValue placeholder="All Clinics" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">All Practice Locations</SelectItem>
                  {clinics.map(([code, name]) => (
                    <SelectItem key={code} value={code}>
                      {name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>

            <Select value={network} onValueChange={setNetwork}>
              <SelectTrigger aria-label="Filter by network" className="w-full">
                <SelectValue placeholder="All Networks" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">All Payer Networks</SelectItem>
                  {networks.map((net) => (
                    <SelectItem key={net} value={net}>
                      {net}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>

            <Select value={visibility} onValueChange={setVisibility}>
              <SelectTrigger aria-label="Filter by visibility" className="w-full">
                <SelectValue placeholder="All Visibility" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">All Visibility States</SelectItem>
                  <SelectItem value="listed">Publicly Listed</SelectItem>
                  <SelectItem value="excluded">Directory Suppressed</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {directoryQuery.isLoading ? (
            <div className="flex flex-col gap-2 p-6">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : filtered.length === 0 ? (
            <Empty className="m-6 border">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <Building2 />
                </EmptyMedia>
                <EmptyTitle>No directory listings match</EmptyTitle>
                <EmptyDescription>
                  Adjust search or clinic filters to view clinician-location listings.
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSearch("");
                    setClinic("all");
                    setNetwork("all");
                    setVisibility("all");
                  }}
                >
                  Reset Filters
                </Button>
              </EmptyContent>
            </Empty>
          ) : (
            <Table>
              <TableHeader>
                {table.getHeaderGroups().map((hg) => (
                  <TableRow key={hg.id}>
                    {hg.headers.map((h) => (
                      <TableHead key={h.id}>
                        {flexRender(h.column.columnDef.header, h.getContext())}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {table.getRowModel().rows.map((row) => (
                  <TableRow key={row.original.id}>
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
