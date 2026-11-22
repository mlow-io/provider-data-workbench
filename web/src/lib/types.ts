export type WorkspaceView = "work" | "intake" | "deliveries" | "directory";

export interface WorkbenchOverview {
  total_providers: number;
  total_locations: number;
  total_directory_listings: number;
  clean_rate_pct: number;
  open_discrepancies: number;
  high_risk_discrepancies: number;
  held_deliveries: number;
  approved_feeds: number;
  sla_at_risk: number;
  quarantined_rows: number;
  schema_variants_count: number;
  mode: "live" | "demo";
  generated_at: string;
}

export interface DirectoryRecord {
  id: string;
  provider_name: string;
  npi: string;
  npi_luhn_valid: boolean;
  specialty: string;
  location_code: string;
  location_name: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  phone: string;
  phone_extension: string | null;
  networks: string[];
  directory_visible: boolean;
  verified_at: string;
  open_issues: number;
  primary_case_id: string | null;
  source: string;
}

export interface SchemaVariantSummary {
  id: string;
  source: string;
  payer: string | null;
  network: string | null;
  source_version: string | null;
  contract: string;
  grain: string;
  headers: string[];
  mapping: Record<string, string>;
  transforms: Record<string, unknown[]>;
  source_notes: Record<string, string>;
}

export interface SchemaCatalogStatus {
  enabled: boolean;
  catalog_revision: number;
  variants: SchemaVariantSummary[];
}

export interface WorkCaseSummary {
  id: string;
  kind: "correction" | "qa";
  provider_name: string;
  location_id: string | null;
  location_label: string | null;
  field_name: string;
  issue: string;
  risk_level: "high" | "medium" | "low";
  risk_reason: string;
  status: string;
  owner: string | null;
  follow_up: string | null;
  version: number;
  proposal: string | null;
  observed: string | null;
  source: string;
  created_at: string;
  updated_at: string;
  listing_value?: string | null;
  reference_value?: string | null;
  npi?: string | null;
  location_code?: string | null;
  clinic_name?: string | null;
}

export interface WorkEvent {
  id: number;
  case_id: string;
  action: string;
  actor: string;
  reason: string;
  payload: Record<string, unknown>;
  from_status: string;
  to_status: string;
  occurred_at: string;
}

export interface WorkCaseDetail extends WorkCaseSummary {
  evidence: {
    designation: string;
    listing_value: string | null;
    reference_value: string | null;
    location_id: string | null;
    locator: string;
    source: string;
    provider_id: string | null;
    receipt_id: string;
    observation_id: string;
    normalized: Record<string, unknown>;
    original: Record<string, unknown>;
  };
  history: WorkEvent[];
}

export interface CaseActionInput {
  action:
    | "assign"
    | "outreach"
    | "triage"
    | "approve"
    | "submit"
    | "verify"
    | "needs_information"
    | "defer"
    | "resolve";
  actor: string;
  reason: string;
  expected_version: number;
  owner?: string;
  follow_up?: string;
  proposal?: string;
  observed?: string;
  submission_reference?: string;
  verification_note?: string;
  contact_at?: string;
  method?: "phone" | "email" | "portal" | "other";
  outcome?: "no_answer" | "message_left" | "response_received" | "unable_to_contact";
  contact_target?: string;
  respondent_role?: string;
  response_summary?: string;
  reported_phone?: string;
}

export interface IntakeSampleOption {
  id: string;
  title: string;
  subtitle: string;
  filename: string;
  source: string;
  payer?: string;
  sourceVersion?: string;
  profile: "flat" | "fhir-plannet-r4";
  badge: string;
  payloadText: string;
}

export interface SourceSchemaInspection {
  inspection: {
    context: {
      source: string;
      delivery_id: string;
      payer: string | null;
      network: string | null;
      completeness: string;
      source_version: string | null;
    };
    artifact_sha256: string;
    format: string;
    fields: string[];
    row_count: number;
    signature: string;
  };
  recognition: {
    status: "exact" | "compatible_with_drift" | "ambiguous" | "unknown";
    selected_id: string | null;
    candidates: Array<{ variant_id: string; match: string; missing_fields?: string[] }>;
    catalog_revision: number;
  };
  draft: Record<string, unknown>;
  variants: Array<{ id: string; definition: SchemaVariantSummary }>;
  catalog_revision: number;
  fields: string[];
  host_attempt: string;
  notice: string;
}

export interface SourceSchemaPreview {
  preview_token: string;
  host_attempt: string;
  catalog_revision: number;
  report: {
    variant_id: string;
    row_count: number;
    coverage: string;
    uninterpreted_fields: string[];
    eligibility: { policy: string; state: string; reasons: string[]; approved: boolean };
    findings: {
      total: number;
      counts: Record<string, number>;
      items: Array<{
        code: string;
        layer: string;
        locator: string;
        message: string;
        severity: string;
      }>;
    };
    rows: Array<{
      locator: string;
      normalized: Record<string, unknown>;
      lineage?: Record<string, unknown>;
    }>;
  };
}

export interface IntakeSession {
  receipt_id: string;
  attempt_id: string;
  filename: string;
  source: string;
  profile: "flat" | "fhir-plannet-r4";
  state: string;
  payer: string | null;
  source_version: string | null;
  schema_inspection: SourceSchemaInspection | null;
  schema_preview: SourceSchemaPreview | null;
  host_preview: {
    headers: string[];
    total: number;
    valid_count: number;
    quarantined_count: number;
    rows: Array<{
      locator: string;
      original: Record<string, unknown>;
      normalized: Record<string, unknown>;
      problems: string[];
    }>;
  };
}

export interface FeedVersionSummary {
  id: string;
  created_at: string;
  state: "candidate" | "approved" | "rejected";
  delivery_id: string;
  period: string;
  kind: string;
}

export interface ManagedFeedSummary {
  id: string;
  name: string;
  source: string;
  scope: string;
  current_version: string | null;
  config: {
    owner: string;
    enabled: boolean;
    start_date: string;
  };
  versions: FeedVersionSummary[];
}

export interface FeedVersionDetail {
  id: string;
  feed_id: string;
  state: "candidate" | "approved" | "rejected";
  current_version: string | null;
  created_at: string;
  row_count: number;
  delivery: {
    delivery_id: string;
    period: string;
    as_of: string;
    filename: string;
  };
  decision: {
    decision: string;
    actor: string;
    reason: string;
    created_at: string;
  } | null;
  review: Array<{
    code: string;
    disposition: string;
    actor: string;
    reason: string;
    created_at: string;
  }>;
  report_hash: string;
  report: {
    counts: {
      raw: number | null;
      valid: number | null;
      quarantined: number | null;
      unique: number | null;
    };
    findings: Array<{
      code: string;
      severity: string;
      message: string;
    }>;
    comparison: {
      counts?: { new: number; changed: number; unchanged: number; unresolved: number };
      missing_from_this_delivery?: number;
      entries?: Array<{
        key?: unknown;
        status?: string;
        locator?: string;
        changes?: Record<string, { before: unknown; after: unknown }>;
        normalized?: Record<string, unknown>;
      }>;
    } | null;
  };
  rows: Array<{
    locator: string;
    original: Record<string, unknown>;
    normalized: Record<string, unknown>;
    problems: string[];
    comparison?: string;
  }>;
}

export interface ExportPreviewResult {
  version_id: string;
  location_id: string | null;
  snapshot_token: string;
  directory_count: number;
  unresolved_issues_count: number;
  quarantined_count: number;
  reviewed_corrections_count: number;
  directory_sample: Array<Record<string, unknown>>;
}
