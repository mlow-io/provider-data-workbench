import { demoClient, resetDemoState } from "@/demo/tennesseeSeed";
import { triggerDownload } from "@/lib/format";
import type {
  CaseActionInput,
  DirectoryRecord,
  ExportPreviewResult,
  FeedVersionDetail,
  IntakeSession,
  ManagedFeedSummary,
  PhoneReviewScope,
  SchemaCatalogStatus,
  SchemaVariantSummary,
  SourceSchemaInspection,
  SourceSchemaPreview,
  WorkCaseDetail,
  WorkCaseSummary,
  WorkbenchOverview,
} from "@/lib/types";

export function isDemoMode(): boolean {
  if (import.meta.env.VITE_DEMO_MODE === "true") return true;
  if (typeof window !== "undefined") {
    return new URLSearchParams(window.location.search).get("demo") === "1";
  }
  return false;
}

/** A response the server refused; a request without one may still have been applied. */
export class RequestRejected extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function httpJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
    throw new RequestRejected(
      typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`,
      response.status
    );
  }
  return response.json() as Promise<T>;
}

function postJson<T>(path: string, payload: unknown): Promise<T> {
  return httpJson<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

const liveSessions = new Map<string, { payloadText: string; mapping: Record<string, string> }>();

export const dataClient = {
  isDemoMode,
  resetDemo: resetDemoState,

  async overview(): Promise<WorkbenchOverview> {
    if (isDemoMode()) return demoClient.overview();
    return httpJson<WorkbenchOverview>("/api/workbench/overview");
  },

  async directory(filters?: {
    search?: string;
    location?: string;
    network?: string;
  }): Promise<DirectoryRecord[]> {
    if (isDemoMode()) return demoClient.directory(filters);
    const params = new URLSearchParams();
    if (filters?.search) params.set("search", filters.search);
    if (filters?.location) params.set("location", filters.location);
    if (filters?.network) params.set("network", filters.network);
    const res = await httpJson<{ items: DirectoryRecord[] }>(`/api/workbench/directory?${params}`);
    return res.items;
  },

  async schemaCatalog(): Promise<SchemaCatalogStatus> {
    if (isDemoMode()) return demoClient.schemaCatalog();
    return httpJson<SchemaCatalogStatus>("/api/schema-catalog/status");
  },

  async workQueue(): Promise<WorkCaseSummary[]> {
    if (isDemoMode()) return demoClient.workQueue();
    const res = await httpJson<{ items: WorkCaseSummary[] }>("/api/workbench/work");
    return res.items;
  },

  async caseDetail(caseId: string): Promise<WorkCaseDetail> {
    if (isDemoMode()) return demoClient.caseDetail(caseId);
    return httpJson<WorkCaseDetail>(`/api/work/${encodeURIComponent(caseId)}`);
  },

  async recordCaseEvent(caseId: string, payload: CaseActionInput): Promise<WorkCaseDetail> {
    if (isDemoMode()) return demoClient.recordCaseEvent(caseId, payload);
    return httpJson<WorkCaseDetail>(`/api/work/${encodeURIComponent(caseId)}/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  async uploadAndInspectIntake(params: {
    filename: string;
    payloadText: string;
    source: string;
    profile: "flat" | "fhir-plannet-r4";
    payer?: string;
    sourceVersion?: string;
  }): Promise<IntakeSession> {
    if (isDemoMode()) return demoClient.uploadAndInspectIntake(params);

    const query = new URLSearchParams({
      filename: params.filename,
      source: params.source,
      designation: "synthetic",
      profile: params.profile,
      completeness: params.profile === "fhir-plannet-r4" ? "bounded" : "unknown",
    });
    const receipt = await httpJson<{
      id: string;
      attempt_id: string;
      label: string;
      source: string;
      profile: "flat" | "fhir-plannet-r4";
      state: string;
      preview: {
        headers?: string[];
        total?: number;
        valid_count?: number;
        quarantined_count?: number;
        rows?: IntakeSession["host_preview"]["rows"];
      } | null;
    }>(`/api/intakes/files?${query}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: params.payloadText,
    });

    let schemaInspection: SourceSchemaInspection | null = null;
    let schemaPreview: SourceSchemaPreview | null = null;
    const contextPayload: Record<string, string> = {};
    if (params.payer) contextPayload.payer = params.payer;
    if (params.sourceVersion) contextPayload.source_version = params.sourceVersion;

    if (params.profile === "flat" && params.filename.toLowerCase().endsWith(".csv")) {
      const catalog = await this.schemaCatalog().catch(() => ({ enabled: false }));
      if (catalog.enabled) {
        try {
          schemaInspection = await httpJson<SourceSchemaInspection>(
            `/api/intakes/${encodeURIComponent(receipt.id)}/source-schema/inspect`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                expected_attempt: receipt.attempt_id,
                ...(Object.keys(contextPayload).length ? { context: contextPayload } : {}),
              }),
            }
          );
        const draft = structuredClone(schemaInspection.draft);
        const mapping = (draft.mapping as Record<string, string>) ?? {};
        const headers = schemaInspection.inspection.fields;
        // Enrich heuristic draft for common renamed headers and exclusion flags
        const extraAliases: Record<string, string[]> = {
          record_id: ["member_record_id", "record_id"],
          practitioner_npi: ["clinician_npi", "npi", "practitioner_npi"],
          provider_name: ["full_name", "provider_name"],
          specialty: ["nucc_taxonomy", "specialty"],
          location_id: ["clinic_code", "location_id"],
          address: ["street_addr", "address"],
          city: ["city"],
          state: ["state"],
          zip: ["postal_code", "zip"],
          phone: ["scheduling_phone", "phone"],
          directory_visible: ["dir_exclude_flag", "directory_visible"],
          source_updated_at: ["updated_date", "source_updated_at"],
        };
        if (schemaInspection.recognition.status === "unknown") {
          for (const [field, alts] of Object.entries(extraAliases)) {
            if (!mapping[field]) {
              const found = headers.find((h) => alts.includes(h.toLowerCase()));
              if (found) mapping[field] = found;
            }
          }
          draft.mapping = mapping;
          const transforms = (draft.transforms as Record<string, unknown[]>) ?? {};
          if (mapping.phone && !transforms.phone) transforms.phone = [{ op: "phone_us" }];
          if (mapping.zip && !transforms.zip) transforms.zip = [{ op: "zip_us" }];
          if (mapping.state && !transforms.state) transforms.state = [{ op: "state_us" }];
          if (mapping.directory_visible && /exclud|flag/i.test(mapping.directory_visible)) {
            transforms.directory_visible = [{ op: "value_map", values: { Y: false, N: true } }];
            draft.evidence_refs = ["operator-review-note"];
            draft.source_notes = {
              "operator-review-note": `${mapping.directory_visible}=Y suppresses public directory visibility without ending network participation.`,
            };
          }
          draft.transforms = transforms;
          draft.ignored_fields = headers.filter((h) => !Object.values(mapping).includes(h));
          if ((draft.ignored_fields as string[]).length > 0 && !(draft.evidence_refs as string[] | undefined)?.length) {
            draft.evidence_refs = ["operator-review-note"];
            draft.source_notes = { "operator-review-note": "Ignored auxiliary display columns during intake." };
          }
          schemaInspection.draft = draft;
        }
        schemaPreview = await httpJson<SourceSchemaPreview>(
          `/api/intakes/${encodeURIComponent(receipt.id)}/source-schema/preview`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              expected_attempt: receipt.attempt_id,
              definition: draft,
              expected_catalog_revision: schemaInspection.catalog_revision,
              ...(Object.keys(contextPayload).length ? { context: contextPayload } : {}),
            }),
          }
        );
        } catch {
          schemaInspection = null;
        }
      }
    }

    liveSessions.set(receipt.id, {
      payloadText: params.payloadText,
      mapping: ((schemaInspection?.draft?.mapping as Record<string, string>) ?? {}),
    });

    const previewRows = receipt.preview?.rows ?? [];
    return {
      receipt_id: receipt.id,
      attempt_id: receipt.attempt_id,
      filename: receipt.label,
      source: receipt.source,
      profile: receipt.profile,
      state: receipt.state,
      payer: params.payer ?? null,
      source_version: params.sourceVersion ?? null,
      schema_inspection: schemaInspection,
      schema_preview: schemaPreview,
      host_preview: {
        headers: receipt.preview?.headers ?? [],
        total: receipt.preview?.total ?? previewRows.length,
        valid_count: receipt.preview?.valid_count ?? previewRows.filter((r) => !r.problems?.length).length,
        quarantined_count:
          receipt.preview?.quarantined_count ?? previewRows.filter((r) => Boolean(r.problems?.length)).length,
        rows: previewRows,
      },
    };
  },

  async previewSourceSchema(
    receiptId: string,
    definition: Record<string, unknown>,
    options?: {
      expectedAttempt?: string;
      expectedCatalogRevision?: number;
      payer?: string | null;
      sourceVersion?: string | null;
    }
  ): Promise<SourceSchemaPreview> {
    if (isDemoMode()) return demoClient.previewSourceSchema(receiptId, definition);
    const contextPayload: Record<string, string> = {};
    if (options?.payer) contextPayload.payer = options.payer;
    if (options?.sourceVersion) contextPayload.source_version = options.sourceVersion;
    return httpJson<SourceSchemaPreview>(
      `/api/intakes/${encodeURIComponent(receiptId)}/source-schema/preview`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_attempt: options?.expectedAttempt,
          definition,
          expected_catalog_revision: options?.expectedCatalogRevision ?? 0,
          ...(Object.keys(contextPayload).length ? { context: contextPayload } : {}),
        }),
      }
    );
  },

  async saveAndReviewVariant(params: {
    receiptId: string;
    definition: Record<string, unknown>;
    actor: string;
    reason: string;
    expectedAttempt?: string;
    expectedCatalogRevision?: number;
    previewToken?: string;
    payer?: string | null;
    sourceVersion?: string | null;
  }): Promise<SchemaVariantSummary> {
    if (isDemoMode()) return demoClient.saveAndReviewVariant(params);
    const contextPayload: Record<string, string> = {};
    if (params.payer) contextPayload.payer = params.payer;
    if (params.sourceVersion) contextPayload.source_version = params.sourceVersion;

    const proposal = await httpJson<{ id: string }>(
      `/api/intakes/${encodeURIComponent(params.receiptId)}/source-schema/proposals`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_attempt: params.expectedAttempt,
          definition: params.definition,
          expected_catalog_revision: params.expectedCatalogRevision ?? 0,
          preview_token: params.previewToken,
          request_id: `ui-prop-${params.receiptId}-${Date.now()}`,
          ...(Object.keys(contextPayload).length ? { context: contextPayload } : {}),
        }),
      }
    );
    await httpJson(
      `/api/intakes/${encodeURIComponent(params.receiptId)}/source-schema/proposals/${encodeURIComponent(proposal.id)}/review`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_attempt: params.expectedAttempt,
          actor: params.actor,
          reason: params.reason,
          expected_catalog_revision: params.expectedCatalogRevision ?? 0,
          preview_token: params.previewToken,
        }),
      }
    );
    const status = await this.schemaCatalog();
    return status.variants[0];
  },

  async acceptIntake(params: {
    receiptId: string;
    attemptId: string;
    profile: "flat" | "fhir-plannet-r4";
    state: string;
    schemaMapping?: Record<string, string>;
    actor: string;
    reason: string;
  }): Promise<{ committed: number; quarantined: number }> {
    if (isDemoMode()) return demoClient.acceptIntake(params);
    let latestAttemptId = params.attemptId;
    if (params.profile === "flat" && params.state !== "preview_ready" && params.schemaMapping) {
      const hostMap: Record<string, string> = {};
      for (const [k, v] of Object.entries(params.schemaMapping)) {
        const hostKey = k === "practitioner_npi" ? "npi" : k;
        if (
          [
            "record_id",
            "npi",
            "provider_name",
            "address",
            "city",
            "state",
            "zip",
            "phone",
            "location_id",
            "specialty",
            "source_updated_at",
          ].includes(hostKey)
        ) {
          hostMap[hostKey] = v;
        }
      }
      const mapped = await httpJson<{ attempt_id: string }>(
        `/api/intakes/${encodeURIComponent(params.receiptId)}/mapping`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mapping: hostMap }),
        }
      );
      latestAttemptId = mapped.attempt_id;
    }
    const committed = await httpJson<{
      preview?: { valid_count?: number; quarantined_count?: number } | null;
    }>(`/api/intakes/${encodeURIComponent(params.receiptId)}/commit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actor: params.actor,
        reason: params.reason,
        policy: "valid_rows",
        expected_attempt: latestAttemptId,
      }),
    });
    return {
      committed: committed.preview?.valid_count ?? 0,
      quarantined: committed.preview?.quarantined_count ?? 0,
    };
  },

  async phoneReviews(): Promise<PhoneReviewScope[]> {
    if (isDemoMode()) return demoClient.phoneReviews();
    const res = await httpJson<{ items: PhoneReviewScope[] }>("/api/workbench/phone-reviews");
    return res.items;
  },

  async decidePhone(params: {
    scope: PhoneReviewScope;
    selectedRef: string;
    requestId: string;
    actor: string;
    reason: string;
  }): Promise<void> {
    if (isDemoMode()) return demoClient.decidePhone(params);
    await postJson("/api/reconciliation/field-decisions", {
      clinician_id: params.scope.clinician_id,
      location_id: params.scope.location_id,
      field: "phone",
      decision: "select",
      selected_ref: params.selectedRef,
      expected_snapshot: params.scope.snapshot,
      expected_decision: params.scope.decision?.id ?? null,
      request_id: params.requestId,
      actor: params.actor,
      reason: params.reason,
    });
  },

  async createPhoneCandidate(params: {
    scope: PhoneReviewScope;
    idempotencyKey: string;
    actor: string;
    reason: string;
  }): Promise<FeedVersionDetail> {
    const { scope } = params;
    if (!scope.base_version || !scope.decision) throw new Error("A selected phone decision and approved base are required");
    if (isDemoMode()) return demoClient.createPhoneCandidate(params);
    return postJson<FeedVersionDetail>(
      `/api/feed-versions/${encodeURIComponent(scope.base_version)}/field-materialization`,
      {
        clinician_id: scope.clinician_id,
        location_id: scope.location_id,
        snapshot: scope.snapshot,
        decision_id: scope.decision.id,
        actor: params.actor,
        reason: params.reason,
        idempotency_key: params.idempotencyKey,
      }
    );
  },

  async feeds(): Promise<ManagedFeedSummary[]> {
    if (isDemoMode()) return demoClient.feeds();
    const res = await httpJson<{ items: ManagedFeedSummary[] }>("/api/feeds");
    return res.items;
  },

  async feedVersion(versionId: string): Promise<FeedVersionDetail> {
    if (isDemoMode()) return demoClient.feedVersion(versionId);
    return httpJson<FeedVersionDetail>(`/api/feed-versions/${encodeURIComponent(versionId)}`);
  },

  async acknowledgeHold(params: {
    versionId: string;
    code: string;
    expectedReport: string;
    actor: string;
    reason: string;
  }): Promise<FeedVersionDetail> {
    if (isDemoMode()) return demoClient.acknowledgeHold(params);
    return httpJson<FeedVersionDetail>(
      `/api/feed-versions/${encodeURIComponent(params.versionId)}/exceptions`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: params.code,
          disposition: "acknowledged",
          expected_report: params.expectedReport,
          actor: params.actor,
          reason: params.reason,
        }),
      }
    );
  },

  async decideFeedVersion(params: {
    versionId: string;
    decision: "approved" | "rejected";
    expectedReport: string;
    expectedCurrent: string | null;
    actor: string;
    reason: string;
  }): Promise<FeedVersionDetail> {
    if (isDemoMode()) return demoClient.decideFeedVersion(params);
    return httpJson<FeedVersionDetail>(
      `/api/feed-versions/${encodeURIComponent(params.versionId)}/decide`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision: params.decision,
          expected_report: params.expectedReport,
          expected_current: params.expectedCurrent,
          idempotency_key: `ui-${params.decision}-${params.versionId}-${Date.now()}`,
          actor: params.actor,
          reason: params.reason,
        }),
      }
    );
  },

  async previewFeedExport(
    versionId: string,
    locationId?: string | null
  ): Promise<ExportPreviewResult> {
    if (isDemoMode()) return demoClient.previewFeedExport(versionId, locationId);
    const params = new URLSearchParams();
    if (locationId) params.set("location_id", locationId);
    const raw = await httpJson<Record<string, unknown>>(
      `/api/feed-versions/${encodeURIComponent(versionId)}/review-preview?${params}`
    );
    const counts = (raw.counts as Record<string, number> | undefined) ?? {};
    return {
      version_id: versionId,
      location_id: locationId ?? null,
      snapshot_token: String(raw.snapshot_id ?? ""),
      directory_count: Number(counts.directory ?? 0),
      unresolved_issues_count: Number(counts.unresolved_issues ?? 0),
      quarantined_count: Number(counts.quarantined_rows ?? 0),
      reviewed_corrections_count: Number(counts.corrections ?? 0),
      directory_sample: (raw.directory as Array<Record<string, unknown>> | undefined) ?? [],
    };
  },

  async downloadExport(params: {
    versionId: string;
    format: "xlsx" | "json";
    snapshotToken: string;
    locationId?: string | null;
  }): Promise<void> {
    if (isDemoMode()) {
      const payload = await demoClient.buildExportPayload(
        params.versionId,
        params.format === "xlsx" ? "csv" : "json",
        params.locationId
      );
      triggerDownload(payload.filename, payload.content, payload.mimeType);
      return;
    }
    const query = new URLSearchParams({
      format: params.format,
      expected_snapshot: params.snapshotToken,
    });
    if (params.locationId) query.set("location_id", params.locationId);
    const res = await fetch(
      `/api/feed-versions/${encodeURIComponent(params.versionId)}/review-export?${query}`
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Export download failed" }));
      throw new Error(typeof err.detail === "string" ? err.detail : "Export download failed");
    }
    const blob = await res.blob();
    const ext = params.format;
    const scope = params.locationId ? `-${params.locationId.toLowerCase()}` : "";
    triggerDownload(
      `reviewed-directory-${params.versionId}${scope}.${ext}`,
      blob,
      params.format === "xlsx"
        ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        : "application/json"
    );
  },

  async downloadWorkQueueCsv(cases: WorkCaseSummary[]): Promise<void> {
    const headers = ["id", "provider_name", "npi", "clinic", "field", "issue", "risk", "status", "follow_up"];
    const lines = [
      headers.join(","),
      ...cases.map((c) =>
        [
          c.id,
          c.provider_name,
          c.npi ?? "",
          c.clinic_name ?? c.location_code ?? "",
          c.field_name,
          c.issue,
          c.risk_level,
          c.status,
          c.follow_up ?? "",
        ]
          .map((cell) => JSON.stringify(String(cell)))
          .join(",")
      ),
    ];
    triggerDownload("provider-work-queue.csv", lines.join("\n"), "text/csv");
  },
};
