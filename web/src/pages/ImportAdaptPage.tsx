import { useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BookmarkCheck,
  CheckCircle2,
  FileSpreadsheet,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SAMPLE_OPTIONS } from "@/demo/tennesseeSeed";
import { dataClient } from "@/lib/dataClient";
import { formatPhone, isValidNpi } from "@/lib/format";
import type { IntakeSampleOption, IntakeSession } from "@/lib/types";

const TARGET_FIELDS = [
  "record_id",
  "practitioner_npi",
  "provider_name",
  "specialty",
  "location_id",
  "address",
  "city",
  "state",
  "zip",
  "phone",
  "directory_visible",
  "source_updated_at",
];

const FIELD_LABELS: Record<string, string> = {
  record_id: "Record ID",
  practitioner_npi: "Practitioner NPI",
  provider_name: "Clinician Name",
  specialty: "NUCC Specialty",
  location_id: "Location Code",
  address: "Street Address",
  city: "City",
  state: "State",
  zip: "ZIP Code",
  phone: "Phone",
  directory_visible: "Visibility",
  source_updated_at: "Updated",
};

export function ImportAdaptPage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [session, setSession] = useState<IntakeSession | null>(null);
  const [draftMapping, setDraftMapping] = useState<Record<string, string>>({});
  const [uploadSource, setUploadSource] = useState("cumberland-clinic");
  const [reviewer, setReviewer] = useState("M. Brooks");
  const [reviewNote, setReviewNote] = useState(
    "Verified header mapping and Dir_Exclude_Flag=Y suppression semantics"
  );
  const [busy, setBusy] = useState(false);

  const catalogQuery = useQuery({
    queryKey: ["schema-catalog-status"],
    queryFn: () => dataClient.schemaCatalog(),
  });

  async function loadSample(sample: IntakeSampleOption) {
    setBusy(true);
    try {
      const next = await dataClient.uploadAndInspectIntake({
        filename: sample.filename,
        payloadText: sample.payloadText,
        source: sample.source,
        profile: sample.profile,
        payer: sample.payer,
        sourceVersion: sample.sourceVersion,
      });
      setSession(next);
      const map = (next.schema_inspection?.draft?.mapping as Record<string, string>) ?? {};
      setDraftMapping(map);
      toast.success(`Inspected ${sample.filename}`, {
        description:
          next.schema_inspection?.recognition.status === "exact"
            ? "Matched saved schema variant offline with 0 LLM calls."
            : "Header profile and quality checks ready for review.",
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not inspect sample");
    } finally {
      setBusy(false);
    }
  }

  async function handleFileSelect(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    try {
      const text = await file.text();
      const isJson = file.name.toLowerCase().endsWith(".json");
      const next = await dataClient.uploadAndInspectIntake({
        filename: file.name,
        payloadText: text,
        source: uploadSource.trim() || "clinic-upload",
        profile: isJson ? "fhir-plannet-r4" : "flat",
      });
      setSession(next);
      setDraftMapping((next.schema_inspection?.draft?.mapping as Record<string, string>) ?? {});
      toast.success(`Uploaded & inspected ${file.name}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload inspection failed");
    } finally {
      setBusy(false);
    }
  }

  function buildUpdatedDefinition(): Record<string, unknown> {
    if (!session?.schema_inspection) return {};
    const base = structuredClone(session.schema_inspection.draft);
    const cleanMapping: Record<string, string> = {};
    for (const [k, v] of Object.entries(draftMapping)) {
      if (v && v !== "__none__") cleanMapping[k] = v;
    }
    base.mapping = cleanMapping;
    const headers = session.schema_inspection.inspection.fields;
    base.ignored_fields = headers.filter((h) => !Object.values(cleanMapping).includes(h));
    const transforms = ((base.transforms as Record<string, unknown[]>) ?? {});
    if (cleanMapping.phone && !transforms.phone) transforms.phone = [{ op: "phone_us" }];
    if (cleanMapping.zip && !transforms.zip) transforms.zip = [{ op: "zip_us" }];
    if (cleanMapping.state && !transforms.state) transforms.state = [{ op: "state_us" }];
    if (cleanMapping.directory_visible) {
      transforms.directory_visible = [{ op: "value_map", values: { Y: false, N: true } }];
    }
    base.transforms = transforms;
    if (
      (base.ignored_fields as string[]).length > 0 ||
      Boolean(cleanMapping.directory_visible)
    ) {
      base.evidence_refs = ["operator-review-note"];
      base.source_notes = {
        "operator-review-note": reviewNote.trim() || "Operator reviewed field meanings.",
      };
    }
    return base;
  }

  async function refreshPreview() {
    if (!session?.schema_inspection) return;
    setBusy(true);
    try {
      const def = buildUpdatedDefinition();
      const preview = await dataClient.previewSourceSchema(session.receipt_id, def, {
        expectedAttempt: session.attempt_id,
        expectedCatalogRevision: session.schema_inspection.catalog_revision,
        payer: session.payer,
        sourceVersion: session.source_version,
      });
      setSession((prev) =>
        prev
          ? {
              ...prev,
              schema_inspection: prev.schema_inspection
                ? { ...prev.schema_inspection, draft: def }
                : null,
              schema_preview: preview,
            }
          : null
      );
      toast.success("Updated normalization preview");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveVariant() {
    if (!session?.schema_inspection || !session.schema_preview) return;
    setBusy(true);
    try {
      const def = buildUpdatedDefinition();
      const saved = await dataClient.saveAndReviewVariant({
        receiptId: session.receipt_id,
        definition: def,
        actor: reviewer.trim() || "M. Brooks",
        reason: reviewNote.trim() || "Reviewed source column mapping",
        expectedAttempt: session.attempt_id,
        expectedCatalogRevision: session.schema_inspection.catalog_revision,
        previewToken: session.schema_preview.preview_token,
        payer: session.payer,
        sourceVersion: session.source_version,
      });
      await queryClient.invalidateQueries({ queryKey: ["schema-catalog-status"] });
      await queryClient.invalidateQueries({ queryKey: ["workbench-overview"] });
      setSession((prev) =>
        prev && prev.schema_inspection
          ? {
              ...prev,
              schema_inspection: {
                ...prev.schema_inspection,
                recognition: {
                  ...prev.schema_inspection.recognition,
                  status: "exact",
                  selected_id: saved.id,
                },
              },
            }
          : prev
      );
      toast.success("Saved reviewed variant to catalog", {
        description: "Future deliveries from this source will match deterministically with AI off.",
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save variant");
    } finally {
      setBusy(false);
    }
  }

  async function handleAcceptValidRows() {
    if (!session) return;
    setBusy(true);
    try {
      const result = await dataClient.acceptIntake({
        receiptId: session.receipt_id,
        attemptId: session.attempt_id,
        profile: session.profile,
        state: session.state,
        schemaMapping: draftMapping,
        actor: reviewer.trim() || "M. Brooks",
        reason: "Accepted reviewed valid roster rows to staging",
      });
      setSession((prev) => (prev ? { ...prev, state: "committed" } : null));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["workbench-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["directory-records"] }),
        queryClient.invalidateQueries({ queryKey: ["work-queue"] }),
      ]);
      toast.success(`Accepted ${result.committed} valid rows`, {
        description:
          result.quarantined > 0
            ? `${result.quarantined} invalid row(s) remained quarantined.`
            : "All valid rows staged into directory observations.",
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Acceptance failed");
    } finally {
      setBusy(false);
    }
  }

  const inspection = session?.schema_inspection ?? null;
  const schemaReport = session?.schema_preview?.report ?? null;
  const activeStep = !session ? 1 : session.state === "committed" ? 3 : 2;
  const exclusionMapped = Boolean(
    draftMapping.directory_visible && /exclud|flag/i.test(draftMapping.directory_visible)
  );

  const previewRows = useMemo(() => {
    if (schemaReport?.rows?.length) {
      return schemaReport.rows.map((r) => {
        const npi = String(r.normalized.practitioner_npi ?? r.normalized.npi ?? "");
        const luhnOk = !npi || isValidNpi(npi);
        return {
          locator: r.locator,
          providerName: String(r.normalized.provider_name ?? "—"),
          npi,
          luhnOk,
          locationId: String(r.normalized.location_id ?? "—"),
          phone: String(r.normalized.phone ?? ""),
          directoryVisible:
            typeof r.normalized.directory_visible === "boolean"
              ? r.normalized.directory_visible
              : true,
        };
      });
    }
    return (session?.host_preview.rows ?? []).map((r) => {
      const npi = String(r.normalized.npi ?? "");
      return {
        locator: r.locator,
        providerName: String(r.normalized.provider_name ?? r.normalized.resourceType ?? "—"),
        npi,
        luhnOk: !npi || isValidNpi(npi),
        locationId: String(r.normalized.location_id ?? r.normalized.id ?? "—"),
        phone: String(r.normalized.phone ?? ""),
        directoryVisible: true,
      };
    });
  }, [schemaReport, session]);

  const findingsItems = schemaReport?.findings.items ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Import & Schema Adaptation
          </h1>
          <p className="text-sm text-muted-foreground">
            Powered by <span className="font-mono text-xs">provider-network-intake</span>: inspect
            messy rosters once, review exclusion semantics, and reuse variants offline forever.
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-1.5 text-xs sm:flex-nowrap">
          <Badge variant={activeStep === 1 ? "default" : "secondary"}>1. Select Source</Badge>
          <Badge variant={activeStep === 2 ? "default" : "secondary"}>
            2. Variant & Semantics
          </Badge>
          <Badge variant={activeStep === 3 ? "default" : "secondary"}>3. Stage Valid Rows</Badge>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Choose a Sample Delivery or Upload Roster</CardTitle>
          <CardDescription>
            Compare a known Cumberland roster (deterministic offline match) against an unfamiliar
            payer delta with renamed headers, an inverted exclusion flag, and a bad NPI checksum.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {SAMPLE_OPTIONS.map((sample) => (
              <button
                key={sample.id}
                type="button"
                disabled={busy}
                onClick={() => loadSample(sample)}
                className="flex flex-col items-start gap-2 rounded-xl border bg-card p-4 text-left transition-colors hover:border-primary/50 hover:bg-accent/40 disabled:opacity-50"
              >
                <div className="flex w-full items-center justify-between gap-2">
                  <FileSpreadsheet className="size-4 text-primary" />
                  <Badge variant="secondary">{sample.badge}</Badge>
                </div>
                <div className="text-sm font-medium text-foreground">{sample.title}</div>
                <div className="text-xs text-muted-foreground">{sample.subtitle}</div>
              </button>
            ))}
          </div>

          <div className="flex flex-col gap-3 rounded-xl border border-dashed bg-muted/30 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium">Upload your own CSV or FHIR Bundle JSON</span>
              <span className="text-xs text-muted-foreground">
                Original bytes are hashed (SHA-256) and never sent to external models.
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                aria-label="Source namespace"
                value={uploadSource}
                onChange={(e) => setUploadSource(e.target.value)}
                placeholder="source-name"
                className="w-44"
              />
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.json"
                className="sr-only"
                onChange={(e) => handleFileSelect(e.target.files?.[0])}
              />
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload data-icon="inline-start" />
                Choose File
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {session && (
        <div className="flex flex-col gap-3">
          {inspection ? (
            <Alert>
              {inspection.recognition.status === "exact" ? (
                <CheckCircle2 className="size-4 text-status-success" />
              ) : (
                <Sparkles className="size-4 text-status-warning" />
              )}
              <AlertTitle className="flex flex-wrap items-center gap-2">
                <span>{session.filename}</span>
                <StatusBadge status={inspection.recognition.status} />
                {inspection.recognition.status === "exact" && (
                  <Badge variant="secondary">Deterministic · 0 LLM Calls</Badge>
                )}
              </AlertTitle>
              <AlertDescription className="mt-1 flex flex-col gap-1">
                <span>
                  {inspection.recognition.status === "exact"
                    ? `Matched reviewed variant (${inspection.recognition.selected_id?.slice(0, 14)}) for source "${session.source}".`
                    : `Unfamiliar schema for "${session.source}". Review the heuristic column draft below before saving a reusable variant.`}
                </span>
                {exclusionMapped && (
                  <span className="font-medium text-status-warning">
                    Exclusion Flag Semantics Detected: {draftMapping.directory_visible} = Y maps to
                    directory_visible = false (suppresses public directory listing without
                    terminating network participation).
                  </span>
                )}
              </AlertDescription>
            </Alert>
          ) : session.profile === "fhir-plannet-r4" ? (
            <Alert>
              <ShieldCheck className="size-4 text-primary" />
              <AlertTitle>{session.filename} · Saved FHIR R4 / Plan-Net 1.2 Bundle</AlertTitle>
              <AlertDescription>
                Parsed {session.host_preview.total} FHIR resources conservatively without assuming
                missing network extensions.
              </AlertDescription>
            </Alert>
          ) : (
            <Alert>
              <ShieldCheck className="size-4 text-primary" />
              <AlertTitle>{session.filename} · Host CSV Intake Preview</AlertTitle>
              <AlertDescription>
                Validated {session.host_preview.total} rows with the built-in workbench CSV parser
                (optional schema-adaptation plugin not active).
              </AlertDescription>
            </Alert>
          )}

          {inspection && (
            <Card size="sm">
              <CardHeader className="border-b">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <CardTitle className="text-base">Schema Column Mapping & Review</CardTitle>
                    <CardDescription>
                      Bind source headers to canonical healthcare fields. Saving a variant updates
                      the catalog without committing rows.
                    </CardDescription>
                  </div>
                  <Button variant="outline" size="sm" disabled={busy} onClick={refreshPreview}>
                    Re-run Preview
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="pt-3">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  {TARGET_FIELDS.filter(
                    (f) => draftMapping[f] || inspection.inspection.fields.length > 0
                  )
                    .slice(0, 12)
                    .map((target) => (
                      <Field key={target}>
                        <FieldLabel
                          htmlFor={`map-${target}`}
                          className="flex items-baseline justify-between gap-2 text-xs"
                        >
                          <span>{FIELD_LABELS[target] ?? target}</span>
                          <span className="font-mono text-[11px] font-normal text-muted-foreground">
                            {target}
                          </span>
                        </FieldLabel>
                        <Select
                          value={draftMapping[target] ?? "__none__"}
                          onValueChange={(val) =>
                            setDraftMapping((prev) => ({
                              ...prev,
                              [target]: val === "__none__" ? "" : val,
                            }))
                          }
                        >
                          <SelectTrigger id={`map-${target}`} className="w-full">
                            <SelectValue placeholder="Unmapped" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectGroup>
                              <SelectItem value="__none__">— Unmapped —</SelectItem>
                              {inspection.inspection.fields.map((col) => (
                                <SelectItem key={col} value={col}>
                                  {col}
                                </SelectItem>
                              ))}
                            </SelectGroup>
                          </SelectContent>
                        </Select>
                      </Field>
                    ))}
                </div>

                <FieldGroup className="mt-2.5 grid grid-cols-1 gap-3 border-t pt-2.5 sm:grid-cols-2">
                  <Field>
                    <FieldLabel htmlFor="variant-reviewer">Variant Reviewer</FieldLabel>
                    <Input
                      id="variant-reviewer"
                      value={reviewer}
                      onChange={(e) => setReviewer(e.target.value)}
                    />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="variant-note">Source Guide Evidence Note</FieldLabel>
                    <Input
                      id="variant-note"
                      value={reviewNote}
                      onChange={(e) => setReviewNote(e.target.value)}
                    />
                  </Field>
                </FieldGroup>
              </CardContent>
              <CardFooter className="flex flex-wrap justify-between gap-2">
                <span className="text-xs text-muted-foreground">
                  Catalog Revision {inspection.catalog_revision} · Separate from row acceptance
                </span>
                <Button
                  variant="outline"
                  disabled={busy || inspection.recognition.status === "exact"}
                  onClick={handleSaveVariant}
                >
                  <BookmarkCheck data-icon="inline-start" />
                  {inspection.recognition.status === "exact"
                    ? "Variant Reviewed in Catalog"
                    : "Save Reviewed Variant"}
                </Button>
              </CardFooter>
            </Card>
          )}

          <Card size="sm">
            <CardHeader className="border-b">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <CardTitle className="text-base">Interpreted Rows & Quality Checks</CardTitle>
                  <CardDescription>
                    Every NPI is validated with CMS ISO 7812 Luhn check-digit verification; invalid
                    records are quarantined before staging.
                  </CardDescription>
                </div>
                <Button
                  size="sm"
                  disabled={busy || session.state === "committed" || previewRows.length === 0}
                  onClick={handleAcceptValidRows}
                >
                  <CheckCircle2 data-icon="inline-start" />
                  {session.state === "committed"
                    ? "Accepted to Staging"
                    : "Accept Valid Rows to Staging"}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-3">
              <Tabs defaultValue="rows">
                <TabsList>
                  <TabsTrigger value="rows">Preview Rows ({previewRows.length})</TabsTrigger>
                  <TabsTrigger value="findings">
                    Findings & Quarantine ({findingsItems.length})
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="rows" className="pt-2">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Locator</TableHead>
                        <TableHead>Clinician / Resource</TableHead>
                        <TableHead>NPI Validation</TableHead>
                        <TableHead>Clinic / ID</TableHead>
                        <TableHead>Phone</TableHead>
                        <TableHead>Visibility</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {previewRows.map((row) => (
                        <TableRow key={row.locator}>
                          <TableCell className="font-mono text-xs text-muted-foreground">
                            {row.locator}
                          </TableCell>
                          <TableCell className="font-medium">{row.providerName}</TableCell>
                          <TableCell>
                            {row.npi ? (
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-xs">{row.npi}</span>
                                {row.luhnOk ? (
                                  <Badge
                                    variant="outline"
                                    className="border-transparent bg-status-success-bg text-status-success"
                                  >
                                    <ShieldCheck className="size-3" />
                                    Luhn Valid
                                  </Badge>
                                ) : (
                                  <Badge
                                    variant="outline"
                                    className="border-transparent bg-status-danger-bg text-status-danger"
                                  >
                                    <ShieldAlert className="size-3" />
                                    Invalid Checksum
                                  </Badge>
                                )}
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground">—</span>
                            )}
                          </TableCell>
                          <TableCell className="font-mono text-xs">{row.locationId}</TableCell>
                          <TableCell className="font-mono text-xs">
                            {row.phone ? formatPhone(row.phone) : "—"}
                          </TableCell>
                          <TableCell>
                            {row.directoryVisible ? (
                              <Badge variant="secondary">Listed</Badge>
                            ) : (
                              <Badge
                                variant="outline"
                                className="border-transparent bg-status-warning-bg text-status-warning"
                              >
                                Suppressed (Y→false)
                              </Badge>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TabsContent>

                <TabsContent value="findings" className="pt-4">
                  {findingsItems.length === 0 ? (
                    <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                      No structural or checksum errors detected in this preview.
                    </div>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {findingsItems.map((item, idx) => (
                        <Alert
                          key={`${item.code}-${idx}`}
                          variant={item.severity === "error" ? "destructive" : "default"}
                        >
                          <AlertTriangle className="size-4" />
                          <AlertTitle className="font-mono text-xs">
                            {item.code} · {item.locator}
                          </AlertTitle>
                          <AlertDescription className="text-xs">{item.message}</AlertDescription>
                        </Alert>
                      ))}
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader className="border-b">
          <CardTitle>
            Saved Schema Variants ({catalogQuery.data?.variants.length ?? 0})
          </CardTitle>
          <CardDescription>
            Reviewed source-scoped variants persisted in{" "}
            <span className="font-mono text-xs">provider-network-intake</span> for deterministic
            repeat runs.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source</TableHead>
                <TableHead>Scope (Payer / Version)</TableHead>
                <TableHead>Grain</TableHead>
                <TableHead>Mapped Fields</TableHead>
                <TableHead>Evidence Note</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(catalogQuery.data?.variants ?? []).map((v) => (
                <TableRow key={v.id}>
                  <TableCell className="font-medium">{v.source}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {[v.payer, v.source_version].filter(Boolean).join(" · ") || "Default scope"}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{v.grain}</Badge>
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {Object.keys(v.mapping).length} fields
                  </TableCell>
                  <TableCell className="max-w-md truncate text-xs text-muted-foreground">
                    {Object.values(v.source_notes)[0] ?? "Reviewed operator variant"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
