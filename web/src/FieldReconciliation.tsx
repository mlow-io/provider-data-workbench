import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";
import { NativeSelect, NativeSelectOption } from "./components/ui/native-select";
import { Textarea } from "./components/ui/textarea";
import { useWorkspaceQuery, updateWorkspaceQuery } from "./workspaceNavigation";
import { ChangeImpact } from "./ChangeImpact";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { SupportingReference } from "./NativeEvidencePanel";

type Target = { id: string; label: string };
type Page<T> = { items: T[]; total: number; next_offset: number | null };
type FieldName = "provider_name" | "npi" | "phone" | "address";
type FieldDecision = {
  id: string;
  decision: "select" | "conflict";
  selected_ref?: string | null;
  value?: unknown;
  snapshot: string;
  actor: string;
  reason: string;
  created_at: string;
  stale?: boolean;
};
type FieldEvidence = {
  field: FieldName;
  options: {
    ref: string;
    source: string;
    network_id?: string | null;
    network_label?: string | null;
    value: unknown;
    comparison_value: unknown;
    selectable: boolean;
    findings: unknown;
    link_ids: string[];
    supporting_refs?: SupportingReference[];
    source_network_reference?: string | null;
    native_validation?: { profile: string; terminology: string };
  }[];
  option_count: number;
  decision: FieldDecision | null;
  history: FieldDecision[];
  history_total?: number;
  history_next_offset?: number | null;
};
type EvidenceView = {
  scope: { clinician_id: string; location_id: string | null };
  clinician: Target;
  location: Target | null;
  snapshot: string;
  inputs_fresh: boolean;
  source_count: number;
  scope_problems?: string[];
  records: Record<string, unknown>[];
  total: number;
  next_offset: number | null;
  fields: FieldEvidence[];
  notice: string;
};
type DecisionRequest = {
  clinician_id: string;
  location_id: string | null;
  field: FieldName;
  decision: "select" | "conflict";
  selected_ref?: string;
  expected_snapshot: string;
  expected_decision: string | null;
  request_id: string;
  actor: string;
  reason: string;
};
class FieldError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}
async function checked(response: Response) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new FieldError(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail ?? `Request failed (${response.status})`),
      response.status,
    );
  }
  return response;
}
async function request<T>(path: string, payload?: DecisionRequest): Promise<T> {
  return (
    await checked(
      await fetch(
        path,
        payload
          ? {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            }
          : undefined,
      ),
    )
  ).json() as Promise<T>;
}
const human = (text: string) => text.replaceAll("_", " ");
const show = (value: unknown) =>
  value === undefined ? "[absent]" : JSON.stringify(value, null, 2);
function Pages({
  offset,
  next,
  label,
  disabled,
  onChange,
}: {
  offset: number;
  next: number | null;
  label: string;
  disabled: boolean;
  onChange: (offset: number) => void;
}) {
  return (
    <div className="rc-pager" role="group" aria-label={label}>
      <Button variant="outline"
        disabled={disabled || offset === 0}
        onClick={() => onChange(Math.max(0, offset - 20))}
      >
        Previous
      </Button>
      <span>From {offset + 1}</span>
      <Button variant="outline"
        disabled={disabled || next === null}
        onClick={() => next !== null && onChange(next)}
      >
        Next
      </Button>
    </div>
  );
}
function TargetPicker({
  kind,
  value,
  onChange,
  disabled,
}: {
  kind: "clinician" | "location";
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}) {
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const label = kind === "clinician" ? "clinician" : "practice location";
  const targets = useQuery({
    queryKey: ["field-targets", kind, search, offset],
    queryFn: () =>
      request<Page<Target>>(
        `/api/reconciliation/targets/${kind}?${new URLSearchParams({ search, offset: String(offset), limit: "20" })}`,
      ),
  });
  return (
    <div style={{ minWidth: 0, flex: "1 1 280px", maxWidth: "100%" }}>
      <label>
        Find reviewed {label}
        <Input
          aria-label={`Find reviewed ${label}`}
          type="search"
          value={search}
          disabled={disabled}
          onChange={(event) => {
            setSearch(event.target.value);
            setOffset(0);
            onChange("");
          }}
          placeholder="Label text or exact ID"
        />
      </label>
      <label>
        Reviewed {label}
        <NativeSelect
          aria-label={`Reviewed ${label}`}
          disabled={disabled || targets.isFetching || targets.isError}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          <NativeSelectOption value="">Choose a reviewed {label}</NativeSelectOption>
          {value && !targets.data?.items.some(target => target.id === value) && <NativeSelectOption value={value}>Selected {label} · {value}</NativeSelectOption>}
          {targets.data?.items.map((target) => (
            <NativeSelectOption key={target.id} value={target.id}>
              {target.label} · {target.id}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      </label>
      {targets.isFetching && (
        <p role="status">Loading reviewed {label} targets…</p>
      )}
      {targets.error && (
        <p role="alert" className="rc-error">
          {targets.error.message}
        </p>
      )}
      {targets.data && (
        <>
          <p>
            {targets.data.total} reviewed {label} targets in this search.
          </p>
          <Pages
            offset={offset}
            next={targets.data.next_offset}
            label={`Reviewed ${label} target pages`}
            disabled={disabled || targets.isFetching}
            onChange={(next) => {
              setOffset(next);
              onChange("");
            }}
          />
        </>
      )}
    </div>
  );
}
function FieldPanel({
  evidence,
  view,
  otherBusy,
  onPending,
  onRefresh,
  historyOffset,
  onHistoryChange,
}: {
  evidence: FieldEvidence;
  view: EvidenceView;
  otherBusy: boolean;
  onPending: (field: FieldName | null) => void;
  onRefresh: () => Promise<void>;
  historyOffset: number;
  onHistoryChange: (offset: number) => void;
}) {
  const client = useQueryClient();
  const [action, setAction] = useState<"select" | "conflict" | "">("");
  const [selectedRef, setSelectedRef] = useState("");
  const [actor, setActor] = useState("");
  const [reason, setReason] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [requiresRefresh, setRequiresRefresh] = useState(false);
  const [pending, setPending] = useState<DecisionRequest | null>(null);
  const [saved, setSaved] = useState<"select" | "conflict" | null>(null);
  const fieldLabel = human(evidence.field);
  useEffect(() => {
    setReviewed(false);
  }, [view.snapshot, evidence.decision?.id, historyOffset]);
  const mutation = useMutation({
    mutationFn: (payload: DecisionRequest) =>
      request<FieldDecision>("/api/reconciliation/field-decisions", payload),
    onSuccess: async (_response, payload) => {
      setSaved(payload.decision);
      setPending(null);
      onPending(null);
      setAction("");
      setSelectedRef("");
      setReason("");
      setReviewed(false);
      setRequiresRefresh(false);
      await client.invalidateQueries({
        queryKey: [
          "field-reconciliation",
          view.scope.clinician_id,
          view.scope.location_id,
        ],
      });
    },
    onError: (error) => {
      if (error instanceof FieldError && error.status < 500) {
        setPending(null);
        onPending(null);
        if (error.status === 409) {
          setRequiresRefresh(true);
          setReviewed(false);
        }
      }
    },
  });
  const locked = mutation.isPending || pending !== null || otherBusy;
  const canSubmit =
    view.inputs_fresh &&
    !requiresRefresh &&
    !locked &&
    reviewed &&
    actor.trim() &&
    reason.trim() &&
    action &&
    (action === "conflict" ||
      evidence.options.some(
        (option) => option.ref === selectedRef && option.selectable,
      ));
  const submit = () => {
    if (pending) {
      mutation.mutate(pending);
      return;
    }
    if (!canSubmit || !action) return;
    const payload: DecisionRequest = {
      ...view.scope,
      field: evidence.field,
      decision: action,
      ...(action === "select" ? { selected_ref: selectedRef } : {}),
      expected_snapshot: view.snapshot,
      expected_decision: evidence.decision?.id ?? null,
      request_id: crypto.randomUUID(),
      actor: actor.trim(),
      reason: reason.trim(),
    };
    setSaved(null);
    setPending(payload);
    onPending(evidence.field);
    mutation.mutate(payload);
  };
  return (
    <section
      aria-label={`${fieldLabel} reconciliation`}
      style={{
        borderTop: "1px solid #d7e3df",
        paddingTop: "18px",
        marginTop: "24px",
        minWidth: 0,
      }}
    >
      <h3>{fieldLabel}</h3>
      <p>
        {evidence.option_count} source assertions for this field.{" "}
        {evidence.field === "address"
          ? "Choose one coherent address assertion; individual components are never assembled across sources."
          : evidence.field === "phone"
            ? "Phone number and extension are reviewed together for this practice location."
            : "This field belongs to the selected clinician."}
      </p>
      {evidence.decision ? (
        <div
          className={evidence.decision.stale ? "rc-warning" : "rc-run-summary"}
        >
          <p>
            Current decision:{" "}
            <strong>
              {evidence.decision.decision === "select"
                ? "Selected source assertion"
                : "Retained conflict"}
            </strong>
            {evidence.decision.stale && (
              <b> · Stale decision — review the current evidence</b>
            )}
          </p>
          {evidence.decision.selected_ref && (
            <p className="rc-reference">
              Selected reference <code>{evidence.decision.selected_ref}</code>
            </p>
          )}
          <pre>{show(evidence.decision.value)}</pre>
          <p>
            {evidence.decision.actor}: {evidence.decision.reason} ·{" "}
            {evidence.decision.created_at}
          </p>
        </div>
      ) : (
        <p>
          No preferred value or retained-conflict decision has been recorded. No
          source is selected by default.
        </p>
      )}
      <fieldset
        disabled={locked}
        style={{ minWidth: 0, border: "1px solid #d7e3df", padding: "16px" }}
      >
        <legend>Review {fieldLabel}</legend>
        <label>
          Decision for {fieldLabel}
          <NativeSelect
            aria-label={`Decision for ${fieldLabel}`}
            value={action}
            onChange={(event) =>
              setAction(event.target.value as "select" | "conflict" | "")
            }
          >
            <NativeSelectOption value="">Choose a decision</NativeSelectOption>
            <NativeSelectOption value="select">Select one source assertion</NativeSelectOption>
            <NativeSelectOption value="conflict">Retain an explicit conflict</NativeSelectOption>
          </NativeSelect>
        </label>
        <div
          className="rc-scroll"
          role="region"
          aria-label={`${fieldLabel} source assertions`}
          tabIndex={0}
        >
          <table>
            <thead>
              <tr>
                <th>Choice / attribution</th>
                <th>Retained source value</th>
                <th>Comparison value</th>
                <th>Findings</th>
              </tr>
            </thead>
            <tbody>
              {evidence.options.map((option) => (
                <tr key={option.ref}>
                  <th
                    scope="row"
                    style={{
                      textTransform: "none",
                      letterSpacing: "normal",
                      fontWeight: 400,
                    }}
                  >
                    <label
                      style={{
                        fontWeight: 400,
                        flexDirection: "row",
                        alignItems: "start",
                        gap: "8px",
                      }}
                    >
                      <input
                        type="radio"
                        aria-label={`Choose ${fieldLabel} from ${option.source} ${option.ref}`}
                        name={`${evidence.field}-source`}
                        checked={selectedRef === option.ref}
                        disabled={action !== "select" || !option.selectable}
                        onChange={() => setSelectedRef(option.ref)}
                      />
                      <span>
                        <strong>{option.source}</strong>
                        {(option.network_id || option.network_label) && (
                          <span
                            className="rc-reference"
                            style={{ display: "block" }}
                          >
                            Network {option.network_label ?? "Unlabeled"}
                            {option.network_id && (
                              <>
                                {" "}
                                · <code>{option.network_id}</code>
                              </>
                            )}
                          </span>
                        )}
                      </span>
                    </label>
                    <details>
                      <summary>Source provenance</summary>
                      {option.supporting_refs && <div>
                        <p>Contributing FHIR resources · local network binding remains separately reviewed.</p>
                        {option.supporting_refs.map((ref, index) => <p className="rc-reference" key={index}>{ref.field}: <code>{ref.locator}.{ref.path}</code> · Attempt <code>{ref.attempt_id}</code></p>)}
                        <p>Source network: {option.source_network_reference ?? "Unknown"} · Profile: {option.native_validation?.profile ?? "not_run"} · Terminology: {option.native_validation?.terminology ?? "not_run"}</p>
                      </div>}
                      <p className="rc-reference">
                        Retained reference <code>{option.ref}</code>
                      </p>
                      <p className="rc-reference">
                        Reviewed link revisions:{" "}
                        {option.link_ids.join(", ") || "[none]"}
                      </p>
                    </details>
                    {!option.selectable && (
                      <span>
                        Unavailable for selection; retained as evidence.
                      </span>
                    )}
                  </th>
                  <td>
                    <pre>{show(option.value)}</pre>
                  </td>
                  <td>
                    <pre>{show(option.comparison_value)}</pre>
                  </td>
                  <td>
                    <pre>{show(option.findings)}</pre>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!evidence.options.length && <p>No field assertions on this page.</p>}
        <div className="rc-create">
          <label>
            Actor for {fieldLabel}
            <Input
              aria-label={`Actor for ${fieldLabel}`}
              value={actor}
              onChange={(event) => setActor(event.target.value)}
            />
          </label>
          <label>
            Reason for {fieldLabel}
            <Textarea
              aria-label={`Reason for ${fieldLabel}`}
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
            aria-label={`I reviewed ${fieldLabel} source evidence`}
            checked={reviewed}
            onChange={(event) => setReviewed(event.target.checked)}
          />
          I reviewed the source attribution, conflicts and missing values for
          this {fieldLabel} decision.
        </label>
      </fieldset>
      {requiresRefresh && (
        <p className="rc-warning" role="alert">
          The field snapshot or prior decision changed. Refresh field evidence
          and review it again before saving.
        </p>
      )}
      {requiresRefresh && (
        <Button variant="outline"
          disabled={otherBusy || mutation.isPending}
          onClick={async () => {
            setReviewed(false);
            try {
              await onRefresh();
              setRequiresRefresh(false);
              mutation.reset();
            } catch {
              // The parent exposes the refresh error; retain the stale gate.
            }
          }}
        >
          Refresh {fieldLabel} evidence
        </Button>
      )}
      {mutation.error && (
        <p className="rc-error" role="alert">
          {mutation.error.message}
        </p>
      )}
      {pending && mutation.isError && (
        <p role="status">
          The result is unconfirmed. Retry sends the identical request ID and
          field decision.
        </p>
      )}
      {saved && (
        <p role="status">
          {saved === "select"
            ? `Selected ${fieldLabel} source assertion saved.`
            : `Explicit ${fieldLabel} conflict saved.`}{" "}
          Source observations were preserved.
        </p>
      )}
      <Button variant="outline"
        disabled={pending ? mutation.isPending || otherBusy : !canSubmit}
        onClick={submit}
      >
        {mutation.isPending
          ? `Saving ${fieldLabel} decision…`
          : pending
            ? `Retry same ${fieldLabel} decision`
            : `Save ${fieldLabel} decision`}
      </Button>
      <details>
        <summary>
          {fieldLabel} decision history · {evidence.history.length} shown of{" "}
          {evidence.history_total ?? evidence.history.length}
        </summary>
        <Pages
          offset={historyOffset}
          next={evidence.history_next_offset ?? null}
          label={`${fieldLabel} decision history pages`}
          disabled={locked}
          onChange={onHistoryChange}
        />
        {evidence.history.length ? (
          <ol className="history">
            {evidence.history.map((decision) => (
              <li key={decision.id}>
                <b>{decision.decision}</b>
                <span>
                  {decision.actor}: {decision.reason}
                </span>
                <small>
                  Decision {decision.id} · Source{" "}
                  {decision.selected_ref ?? "explicit conflict"}
                </small>
                <time>{decision.created_at}</time>
              </li>
            ))}
          </ol>
        ) : (
          <p>No decisions recorded for this field.</p>
        )}
      </details>
    </section>
  );
}
export function FieldReconciliation() {
  const route = useWorkspaceQuery();
  const [opened, setOpened] = useState(Boolean(route.get("clinician")));
  const clinicianId = route.get("clinician") ?? "";
  const setClinicianId = (value: string) => {
    updateWorkspaceQuery({ clinician: value, location: null, proposal: null, followup: null });
  };
  const [useLocation, setUseLocation] = useState(Boolean(route.get("location")));
  const locationId = route.get("location") ?? "";
  const setLocationId = (value: string) => {
    updateWorkspaceQuery({ location: value, proposal: null, followup: null });
  };
  const routeClinician = route.get("clinician") ?? "";
  const routeLocation = route.get("location") ?? "";
  useEffect(() => {
    setUseLocation(Boolean(routeLocation));
    if (routeClinician) setOpened(true);
  }, [routeClinician, routeLocation]);
  const [offset, setOffset] = useState(0);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [impactPending, setImpactPending] = useState(false);
  const [pendingField, setPendingField] = useState<FieldName | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportError, setExportError] = useState("");
  const routeProposal = route.get("proposal") ?? "";
  useEffect(() => { setImpactPending(false); setPendingField(null); }, [routeClinician, routeLocation, routeProposal]);
  const selectedLocation = useLocation ? locationId || null : null;
  const ready =
    opened && Boolean(clinicianId) && (!useLocation || Boolean(locationId));
  const query = useQuery({
    queryKey: [
      "field-reconciliation",
      clinicianId,
      selectedLocation,
      offset,
      historyOffset,
    ],
    enabled: ready,
    refetchOnWindowFocus: false,
    queryFn: () =>
      request<EvidenceView>(
        `/api/reconciliation/fields/${encodeURIComponent(clinicianId)}?${new URLSearchParams({ ...(selectedLocation ? { location_id: selectedLocation } : {}), offset: String(offset), limit: "20", history_offset: String(historyOffset) })}`,
      ),
  });
  const locked = pendingField !== null || exporting !== null || impactPending;
  const refresh = async () => {
    const result = await query.refetch();
    if (result.isError) throw result.error;
  };
  const download = async (format: "json" | "xlsx") => {
    if (!query.data) return;
    setExportError("");
    setExporting(format);
    try {
      const response = await checked(
        await fetch(
          `/api/reconciliation/identities/clinician/${encodeURIComponent(clinicianId)}/export?${new URLSearchParams({ ...(selectedLocation ? { location_id: selectedLocation } : {}), expected_snapshot: query.data.snapshot, format })}`,
        ),
      );
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `reconciled-${clinicianId}-${selectedLocation ?? "clinician"}.${format}`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "Export failed");
    } finally {
      setExporting(null);
    }
  };
  if (!opened)
    return (
      <section className="iw-card" id="reconciled-fields">
        <h2>Reconciled field evidence</h2>
        <p>
          Choose a reviewed clinician and optional practice location to compare
          approved source assertions and record field decisions.
        </p>
        <Button variant="outline" onClick={() => setOpened(true)}>
          Open reconciled field evidence
        </Button>
      </section>
    );
  return (
    <section className="iw-card" id="reconciled-fields" aria-label="Reconciled field evidence">
      <h2>Reconciled field evidence</h2>
      <p>
        Clinician names and identifiers have their own scope. Select a reviewed
        location to reconcile its phones and coherent addresses. Every preferred
        field keeps its source attribution.
      </p>
      <div className="rc-create">
        <TargetPicker
          kind="clinician"
          value={clinicianId}
          disabled={locked}
          onChange={(value) => {
            setClinicianId(value);
            setLocationId("");
            setOffset(0);
            setExportError("");
            setHistoryOffset(0);
          }}
        />
        <label style={{ flexDirection: "row", alignItems: "start" }}>
          <input
            type="checkbox"
            aria-label="Include a reviewed practice location"
            checked={useLocation}
            disabled={locked}
            onChange={(event) => {
              setUseLocation(event.target.checked);
              setLocationId("");
              setOffset(0);
              setExportError("");
              setHistoryOffset(0);
            }}
          />
          Include a reviewed practice location
        </label>
        {useLocation && (
          <TargetPicker
            kind="location"
            value={locationId}
            disabled={locked}
            onChange={(value) => {
              setLocationId(value);
              setOffset(0);
              setExportError("");
              setHistoryOffset(0);
            }}
          />
        )}
      </div>
      {!ready && (
        <p>Choose the reviewed identity scope explicitly to load evidence.</p>
      )}
      {query.error && ready && (
        <p className="rc-error" role="alert">
          {query.error.message}
        </p>
      )}
      {query.isFetching && ready && (
        <p role="status">
          Loading approved source assertions and field decisions…
        </p>
      )}
      {query.data && ready && (
        <>
          <h3>
            {query.data.clinician.label}
            {query.data.location
              ? ` · ${query.data.location.label}`
              : " · Clinician fields"}
          </h3>
          <p>
            {query.data.source_count} contributing sources · {query.data.total}{" "}
            approved source records · Snapshot{" "}
            <code>{query.data.snapshot}</code>
          </p>
          <p>{query.data.notice}</p>
          {Boolean(query.data.scope_problems?.length) && (
            <div role="alert" className="rc-warning">
              <strong>Identity scope needs review</strong>
              <ul>
                {query.data.scope_problems!.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            </div>
          )}
          {!query.data.inputs_fresh && (
            <p className="rc-warning" role="alert">
              {query.data.total === 0
                ? "No approved source assertions connect this identity scope. Review the clinician and location links before making a field decision."
                : "Approved source dependencies need renewed review. New field decisions require compatible, current dependencies; exports preserve the displayed status."}
            </p>
          )}
          <div className="rc-filters">
            <Button variant="outline"
              disabled={locked || query.isFetching}
              onClick={() => void refresh().catch(() => {})}
            >
              Refresh field evidence
            </Button>
            <Button variant="outline"
              disabled={locked || query.isFetching}
              onClick={() => void download("json")}
            >
              Download reconciled JSON
            </Button>
            <Button variant="outline"
              disabled={locked || query.isFetching}
              onClick={() => void download("xlsx")}
            >
              Download reconciled XLSX
            </Button>
          </div>
          {exporting && (
            <p role="status">
              Preparing complete {exporting.toUpperCase()} evidence export…
            </p>
          )}
          {exportError && (
            <p className="rc-error" role="alert">
              {exportError}
            </p>
          )}
          {query.data.fields.map((evidence) => (
            <FieldPanel
              key={`${clinicianId}:${selectedLocation}:${offset}:${evidence.field}`}
              evidence={evidence}
              view={query.data!}
              otherBusy={
                query.isFetching ||
                exporting !== null ||
                impactPending ||
                (pendingField !== null && pendingField !== evidence.field)
              }
              onPending={setPendingField}
              onRefresh={refresh}
              historyOffset={historyOffset}
              onHistoryChange={setHistoryOffset}
            />
          ))}
          <details>
            <summary>
              Approved source records · {query.data.records.length} shown of{" "}
              {query.data.total}
            </summary>
            {query.data.records.map((record, index) => (
              <details key={String(record.ref ?? index)}>
                <summary>
                  Source assertion {offset + index + 1} ·{" "}
                  {String(record.source ?? "Unknown source")}
                </summary>
                <pre>{show(record)}</pre>
              </details>
            ))}
          </details>
          <p>
            Field options and source records use the same evidence page.
            Downloads include the complete pinned scope.
          </p>
          <Pages
            offset={offset}
            next={query.data.next_offset}
            label="Reconciled evidence pages"
            disabled={locked || query.isFetching}
            onChange={setOffset}
          />
          <ChangeImpact
            key={`${clinicianId}:${selectedLocation}`}
            clinicianId={clinicianId}
            locationId={selectedLocation}
            snapshot={query.data.snapshot}
            inputsFresh={query.data.inputs_fresh}
            fields={query.data.fields}
            otherBusy={
              pendingField !== null || exporting !== null || query.isFetching
            }
            onPendingChange={setImpactPending}
            onRefresh={refresh}
          />
        </>
      )}
    </section>
  );
}
