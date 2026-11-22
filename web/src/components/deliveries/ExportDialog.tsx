import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { dataClient } from "@/lib/dataClient";
import type { ExportPreviewResult } from "@/lib/types";

interface ExportDialogProps {
  open: boolean;
  versionId: string | null;
  availableLocations: Array<{ code: string; name: string }>;
  onOpenChange: (open: boolean) => void;
}

export function ExportDialog({
  open,
  versionId,
  availableLocations,
  onOpenChange,
}: ExportDialogProps) {
  const [scope, setScope] = useState<string>("ALL");
  const [preview, setPreview] = useState<ExportPreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!open || !versionId) return;
    let active = true;
    setLoading(true);
    setError(null);
    setPreview(null);
    const locationId = scope === "ALL" ? null : scope;
    dataClient
      .previewFeedExport(versionId, locationId)
      .then((res) => {
        if (active) setPreview(res);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Could not preview export");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [open, versionId, scope]);

  async function handleDownload(format: "xlsx" | "json") {
    if (!versionId || !preview) return;
    setDownloading(true);
    try {
      await dataClient.downloadExport({
        versionId,
        format,
        snapshotToken: preview.snapshot_token,
        locationId: scope === "ALL" ? null : scope,
      });
      toast.success(`Downloaded ${format.toUpperCase()} roster export`, {
        description:
          scope === "ALL"
            ? `${preview.directory_count} approved listings across all clinics.`
            : `${preview.directory_count} approved listings scoped to ${scope}.`,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Export failed");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Export Approved Directory Snapshot</DialogTitle>
          <DialogDescription>
            Downloads are pinned to the exact reviewed snapshot token so exported rows always match
            this preview.
          </DialogDescription>
        </DialogHeader>

        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="export-scope">Export Scope</FieldLabel>
            <Select value={scope} onValueChange={setScope}>
              <SelectTrigger id="export-scope" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="ALL">Entire Approved Network (All Clinics)</SelectItem>
                  {availableLocations.map((loc) => (
                    <SelectItem key={loc.code} value={loc.code}>
                      {loc.code} · {loc.name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
        </FieldGroup>

        {loading && <div className="text-sm text-muted-foreground">Computing snapshot preview…</div>}

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Scope Unavailable</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {preview && !error && (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-lg border p-2.5">
                <div className="text-xs text-muted-foreground">Listings</div>
                <div className="mt-0.5 text-lg font-semibold tabular-nums">
                  {preview.directory_count}
                </div>
              </div>
              <div className="rounded-lg border p-2.5">
                <div className="text-xs text-muted-foreground">Open Issues</div>
                <div className="mt-0.5 text-lg font-semibold tabular-nums">
                  {preview.unresolved_issues_count}
                </div>
              </div>
              <div className="rounded-lg border p-2.5">
                <div className="text-xs text-muted-foreground">Quarantined</div>
                <div className="mt-0.5 text-lg font-semibold tabular-nums">
                  {preview.quarantined_count}
                </div>
              </div>
              <div className="rounded-lg border p-2.5">
                <div className="text-xs text-muted-foreground">Corrections</div>
                <div className="mt-0.5 text-lg font-semibold tabular-nums">
                  {preview.reviewed_corrections_count}
                </div>
              </div>
            </div>
            <div className="rounded-lg bg-muted/60 px-3 py-2 font-mono text-xs text-muted-foreground">
              Snapshot pin: {preview.snapshot_token.slice(0, 24)}
            </div>
          </div>
        )}

        <DialogFooter className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={!preview || Boolean(error) || downloading}
            onClick={() => handleDownload("json")}
          >
            <Download data-icon="inline-start" />
            Download JSON
          </Button>
          <Button
            disabled={!preview || Boolean(error) || downloading}
            onClick={() => handleDownload("xlsx")}
          >
            <Download data-icon="inline-start" />
            {dataClient.isDemoMode() ? "Download CSV" : "Download Workbook XLSX"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
