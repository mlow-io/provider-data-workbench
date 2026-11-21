import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";
import { NativeSelect, NativeSelectOption } from "./components/ui/native-select";
import { Textarea } from "./components/ui/textarea";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import "./normalization-panel.css";
import { EvidenceComparison } from "./EvidenceComparison";
const MappingAssistantPanel = lazy(() => import("./MappingAssistantPanel").then(module => ({ default: module.MappingAssistantPanel })));

type Operation = { op: string; format?: string };
type Definition = {
  version: number;
  mapping: Record<string, string>;
  transforms: Record<string, Operation[]>;
  required: string[];
};
type Column = {
  name: string;
  nonempty: number;
  missing: number;
  distinct_count: number;
  examples: unknown[];
  null_count: number;
  blank_count: number;
  absent_count: number;
};
type Profile = {
  row_count: number;
  columns: Column[];
  suggested_mapping: Record<string, string>;
  mapping_candidates: Record<string, string[]>;
  next_offset: number | null;
};
type Revision = {
  id: string;
  name: string;
  state: "proposed" | "approved";
  definition: Definition;
  actor?: string;
  reason?: string;
  receipt_id?: string;
  attempt_id?: string;
};
type Preview = {
  total: number;
  valid_count: number;
  quarantined_count: number;
  next_offset: number | null;
  rows: {
    original: unknown;
    normalized: unknown;
    normalization: unknown;
    locator: unknown;
    problems: string[];
  }[];
};
type Compatibility = {
  notice: string;
  total: number;
  next_offset: number | null;
  items: { revision_id: string; name: string; status: string; reusable: boolean; missing_mapped_columns: string[]; ambiguous_columns?: string[]; added_columns: string[]; removed_columns: string[] }[];
};
type Props = {
  receiptId: string;
  attemptId: string;
  currentMapping?: Record<string, string>;
  appliedRecipeId?: string | null;
  accepted?: boolean;
  supported?: boolean;
  onChanged: () => Promise<void>;
};
const requiredFields = [
  "npi",
  "provider_name",
  "address",
  "city",
  "state",
  "zip",
  "phone",
];
const fields = [
  ...requiredFields,
  "suite",
  "address_line2",
  "record_id",
  "location_id",
  "listing_id",
  "reference_phone",
  "phone_extension",
  "reference_phone_extension",
  "specialty",
  "status",
  "source_updated_at",
];
const label = (field: string) => field.replaceAll("_", " ");
const show = (value: unknown) => JSON.stringify(value, null, 2);
async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    path,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      message =
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail);
    } catch {
      /* HTTP status remains available */
    }
    throw new Error(message);
  }
  return response.json();
}

export function NormalizationPanel(props: Props) {
  return (
    <NormalizationDraft
      key={`${props.receiptId}:${props.attemptId}`}
      {...props}
    />
  );
}
function NormalizationDraft({
  receiptId,
  attemptId,
  currentMapping = {},
  appliedRecipeId = null,
  accepted = false,
  supported = true,
  onChanged,
}: Props) {
  const base = `/api/intakes/${encodeURIComponent(receiptId)}`;
  const [open, setOpen] = useState(false),
    [profile, setProfile] = useState<Profile | null>(null);
  const [definition, setDefinition] = useState<Definition>({
    version: 1,
    mapping: Object.fromEntries(
      Object.entries(currentMapping).filter(([field]) =>
        fields.includes(field),
      ),
    ),
    transforms: {},
    required: requiredFields,
  });
  const [preview, setPreview] = useState<Preview | null>(null),
    [revisions, setRevisions] = useState<Revision[]>([]);
  const [saved, setSaved] = useState<Revision | null>(null),
    [selected, setSelected] = useState("");
  const [inspectedProposal, setInspectedProposal] = useState<Revision | null>(
    null,
  );
  const [name, setName] = useState(""),
    [actor, setActor] = useState(""),
    [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [status, setStatus] = useState("");
  const [compatibility, setCompatibility] = useState<Compatibility | null>(null);
  const alive = useRef(true);
  const appliedInitialized = useRef(false);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setStatus("");
    try {
      await action();
    } catch (e) {
      if (alive.current) setError((e as Error).message);
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  const load = () =>
    run(async () => {
      const [data, recipes] = await Promise.all([
        api<Profile>(`${base}/profile?offset=0&limit=100`),
        api<{ items: Revision[] }>(`${base}/recipes`),
      ]);
      if (alive.current) {
        setProfile(data);
        setRevisions(recipes.items);
        if (!appliedInitialized.current) {
          const applied = recipes.items.find(
            (item) => item.id === appliedRecipeId && item.state === "approved",
          );
          if (applied) {
            setDefinition(applied.definition);
            setStatus(
              "Editor shows the exact applied recipe. Changes require a new preview and proposal.",
            );
          }
          appliedInitialized.current = true;
        }
      }
    });
  const edit = (next: Definition) => {
    setDefinition(next);
    setPreview(null);
    setSaved(null);
    setSelected("");
    setStatus("Rules changed. Preview again before saving.");
  };
  const setOperations = (field: string, ops: Operation[]) =>
    edit({
      ...definition,
      transforms: { ...definition.transforms, [field]: ops },
    });
  const previewDefinition = (offset = 0) =>
    run(async () => {
      const result = await api<Preview>(`${base}/normalization/preview`, {
        definition,
        expected_attempt: attemptId,
        offset,
        limit: 5,
      });
      if (alive.current) {
        setPreview(result);
        setStatus(
          "Preview only. Review the counts and field evidence before saving.",
        );
      }
    });
  const reviewed = Boolean(name.trim() && actor.trim() && reason.trim());
  const currentProposal =
    saved?.state === "proposed" &&
    saved.receipt_id === receiptId &&
    saved.attempt_id === attemptId;
  const inspectedDecision = saved ?? inspectedProposal;
  const appliedRevision = revisions.find(
    (item) => item.id === appliedRecipeId && item.state === "approved",
  );
  const binding = (field: string) => {
    const column = definition.mapping[field] ?? "";
    const operations = definition.transforms[field] ?? [];
    const format = operations.find((op) =>
      ["phone_us", "state_us", "zip_us", "date"].includes(op.op),
    );
    const options: Operation[] =
      field === "phone" || field === "reference_phone"
        ? [{ op: "phone_us" }]
        : field === "zip"
          ? [{ op: "zip_us" }]
          : field === "state"
            ? [{ op: "state_us" }]
            : field === "source_updated_at"
              ? ["%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"].map((value) => ({
                  op: "date",
                  format: value,
                }))
              : [];
    return (
      <div
        className="np-field"
        role="group"
        aria-label={`${label(field)} normalization rules`}
        key={field}
      >
        <label>
          {label(field)} source
          <NativeSelect
            aria-label={`Normalize ${label(field)} source`}
            value={column}
            disabled={busy}
            onChange={(event) => {
              const mapping = { ...definition.mapping };
              const transforms = { ...definition.transforms };
              if (event.target.value) mapping[field] = event.target.value;
              else {
                delete mapping[field];
                delete transforms[field];
              }
              edit({ ...definition, mapping, transforms });
            }}
          >
            <NativeSelectOption value="">Unmapped</NativeSelectOption>
            {profile?.columns.map((item) => (
              <NativeSelectOption key={item.name} value={item.name}>
                {item.name}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </label>
        <div className="np-rules">
          <label className="np-check">
            <input
              aria-label={`Trim ${label(field)} edges`}
              type="checkbox"
              disabled={!column || busy}
              checked={operations.some((op) => op.op === "trim")}
              onChange={(event) =>
                setOperations(
                  field,
                  event.target.checked
                    ? [{ op: "trim" }, ...operations]
                    : operations.filter((op) => op.op !== "trim"),
                )
              }
            />
            Trim edges
          </label>
          <label className="np-check">
            <input
              aria-label={`Collapse ${label(field)} spaces`}
              type="checkbox"
              disabled={!column || busy}
              checked={operations.some((op) => op.op === "collapse_spaces")}
              onChange={(event) =>
                setOperations(
                  field,
                  event.target.checked
                    ? [...operations, { op: "collapse_spaces" }]
                    : operations.filter((op) => op.op !== "collapse_spaces"),
                )
              }
            />
            Collapse spaces
          </label>
          <label>
            Case
            <NativeSelect
              aria-label={`${label(field)} case`}
              disabled={!column || busy}
              value={
                operations.find((op) =>
                  ["uppercase", "lowercase"].includes(op.op),
                )?.op ?? ""
              }
              onChange={(event) =>
                setOperations(field, [
                  ...operations.filter(
                    (op) => !["uppercase", "lowercase"].includes(op.op),
                  ),
                  ...(event.target.value ? [{ op: event.target.value }] : []),
                ])
              }
            >
              <NativeSelectOption value="">Keep case</NativeSelectOption>
              <NativeSelectOption value="uppercase">Uppercase</NativeSelectOption>
              <NativeSelectOption value="lowercase">Lowercase</NativeSelectOption>
            </NativeSelect>
          </label>
          {options.length > 0 && (
            <label>
              Format
              <NativeSelect
                aria-label={`${label(field)} format`}
                disabled={!column || busy}
                value={format?.format ?? format?.op ?? ""}
                onChange={(event) =>
                  setOperations(field, [
                    ...operations.filter(
                      (op) =>
                        !["phone_us", "state_us", "zip_us", "date"].includes(
                          op.op,
                        ),
                    ),
                    ...options.filter(
                      (op) => (op.format ?? op.op) === event.target.value,
                    ),
                  ])
                }
              >
                <NativeSelectOption value="">Keep source format</NativeSelectOption>
                {options.map((op) => (
                  <NativeSelectOption key={op.format ?? op.op} value={op.format ?? op.op}>
                    {op.format
                      ? `Date ${op.format}`
                      : op.op === "phone_us"
                        ? "US phone + separate extension"
                        : op.op === "zip_us"
                          ? "US ZIP / ZIP+4"
                          : "US state abbreviation"}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </label>
          )}
          <label className="np-check">
            <input
              aria-label={`Require ${label(field)}`}
              type="checkbox"
              disabled={busy}
              checked={definition.required.includes(field)}
              onChange={(event) =>
                edit({
                  ...definition,
                  required: event.target.checked
                    ? [...definition.required, field]
                    : definition.required.filter((item) => item !== field),
                })
              }
            />
            Required
          </label>
        </div>
      </div>
    );
  };
  return (
    <section className="np-panel" aria-label="Profile and normalization">
      <div className="np-heading">
        <Button variant="outline"
          type="button"
          aria-expanded={open}
          onClick={() => {
            setOpen(!open);
            if (!open && supported && !profile) void load();
          }}
        >
          Profile and normalize
        </Button>
        {accepted && supported && (
          <a href={`${base}/dataset`}>Download validated dataset JSON</a>
        )}
      </div>
      {appliedRecipeId && (
        <p className="np-applied" aria-label="Applied normalization recipe">
          Applied normalization recipe:{" "}
          {appliedRevision ? `${appliedRevision.name} / ` : ""}
          <code>{appliedRecipeId}</code>. This approved revision controls the
          current interpretation.
        </p>
      )}
      {open &&
        (!supported ? (
          <p className="iw-notice">
            Normalization recipes support retained clinic CSV, XLSX and flat
            JSON inputs. Native reference adapters and network rosters keep
            their existing interpretation.
          </p>
        ) : (
          <>
            <p>
              Inspect every column, choose explicit rules, then review a bounded
              before-and-after sample. Applying a recipe creates a new
              interpretation; acceptance remains a separate decision.
            </p>
            {busy && <p role="status">Working on retained evidence…</p>}
            {error && (
              <p role="alert" className="iw-error">
                {error}{" "}
                <Button variant="outline"
                  type="button"
                  disabled={busy}
                  onClick={() => void load()}
                >
                  Reload profile
                </Button>
              </p>
            )}
            {status && <p role="status">{status}</p>}
            {profile && (
              <>
                <Suspense fallback={<p role="status">Loading optional assistance controls…</p>}>
                  <MappingAssistantPanel receiptId={receiptId} attemptId={attemptId} onProposalReady={load} />
                </Suspense>
                <h3>1. Inspect source columns</h3>
                <p>
                  {profile.row_count} source rows · {profile.columns.length}{" "}
                  columns. Counts cover all rows; examples are bounded and
                  retain nulls and blanks.
                </p>
                <div
                  className="np-scroll"
                  tabIndex={0}
                  role="region"
                  aria-label="Full source column counts"
                >
                  <table>
                    <thead>
                      <tr>
                        <th>Column</th>
                        <th>Nonempty</th>
                        <th>Missing</th>
                        <th>Distinct</th>
                        <th>Null / blank / absent</th>
                        <th>Examples</th>
                      </tr>
                    </thead>
                    <tbody>
                      {profile.columns.map((column) => (
                        <tr key={column.name}>
                          <th scope="row">{column.name}</th>
                          <td>{column.nonempty}</td>
                          <td>{column.missing}</td>
                          <td>{column.distinct_count}</td>
                          <td>
                            {column.null_count} / {column.blank_count} /{" "}
                            {column.absent_count}
                          </td>
                          <td>
                            <code>{show(column.examples)}</code>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <h3>2. Map fields and choose rules</h3>
                <p>
                  Header matches are suggestions. Listed and reference phone
                  extensions are retained in separate fields; dates require a
                  declared format. Literal NA stays source data.
                </p>
                <Button variant="outline"
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    edit({
                      ...definition,
                      mapping: profile.suggested_mapping,
                      transforms: {},
                    })
                  }
                >
                  Use suggested normalization columns
                </Button>
                {Object.entries(profile.mapping_candidates)
                  .filter(([, values]) => values.length > 1)
                  .map(([field, values]) => (
                    <p className="iw-notice" key={field}>
                      Choose {label(field)} explicitly: {values.join(", ")}
                    </p>
                  ))}
                <fieldset disabled={busy} className="np-fields">
                  <legend>Core fields</legend>
                  {requiredFields.map(binding)}
                </fieldset>
                <details>
                  <summary>
                    Additional identifiers, extension and source date
                  </summary>
                  <fieldset disabled={busy} className="np-fields">
                    <legend>Optional fields</legend>
                    {fields
                      .filter((field) => !requiredFields.includes(field))
                      .map(binding)}
                  </fieldset>
                </details>
                <Button variant="outline"
                  type="button"
                  disabled={busy || !Object.keys(definition.mapping).length}
                  onClick={() => void previewDefinition()}
                >
                  Preview normalization
                </Button>
                {preview && (
                  <div className="np-preview">
                    <h3>3. Review before and after</h3>
                    <p className="np-counts">
                      {preview.valid_count} valid · {preview.quarantined_count}{" "}
                      quarantined · {preview.total} total
                    </p>
                    <p>
                      Showing {preview.rows.length} rows on this page. Original
                      values and transformation findings remain inspectable.
                    </p>
                    {preview.rows.map((row, index) => (
                      <details key={index}>
                        <summary>
                          Sample row {index + 1} ·{" "}
                          {row.problems.length ? "Needs review" : "Valid"}
                        </summary>
                        <EvidenceComparison original={row.original} interpreted={row.normalized} mapping={definition.mapping} />
                        {row.problems.length > 0 && (
                          <ul>
                            {row.problems.map((problem, i) => (
                              <li key={i}>{problem}</li>
                            ))}
                          </ul>
                        )}
                        <details>
                          <summary>Field provenance and locator</summary>
                          <pre>
                            {show({
                              locator: row.locator,
                              fields: row.normalization,
                            })}
                          </pre>
                        </details>
                      </details>
                    ))}
                    {preview.next_offset !== null && (
                      <Button variant="outline"
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          void previewDefinition(preview.next_offset!)
                        }
                      >
                        Next sample rows
                      </Button>
                    )}
                  </div>
                )}
                <h3>Review retained proposals</h3>
                <p>
                  Proposals created through the workbench or MCP remain here
                  after reload. Approval requires a fresh preview of this
                  receipt and attempt.
                </p>
                <label>
                  Retained recipe proposal
                  <NativeSelect
                    value={inspectedProposal?.id ?? ""}
                    disabled={busy}
                    onChange={(event) => {
                      const revision =
                        revisions.find(
                          (item) => item.id === event.target.value,
                        ) ?? null;
                      setInspectedProposal(revision);
                      setPreview(null);
                      setSelected("");
                      setActor("");
                      setReason("");
                      setSaved(
                        revision?.receipt_id === receiptId ? revision : null,
                      );
                      if (revision) {
                        setDefinition(revision.definition);
                        setName(revision.name);
                        setStatus(
                          revision.receipt_id !== receiptId
                            ? "Rules copied from another receipt. Preview and save a new proposal for this delivery."
                            : revision.attempt_id !== attemptId
                              ? "This proposal belongs to an older attempt. Inspect its evidence or copy the rules into a new proposal."
                              : "Proposal loaded. Preview its rules, then enter your reviewer and approval reason.",
                        );
                      }
                    }}
                  >
                    <NativeSelectOption value="">Choose a retained proposal</NativeSelectOption>
                    {revisions
                      .filter((item) => item.state === "proposed")
                      .map((item) => (
                        <NativeSelectOption key={item.id} value={item.id}>
                          {item.name} ·{" "}
                          {item.receipt_id === receiptId &&
                          item.attempt_id === attemptId
                            ? "current attempt"
                            : item.receipt_id === receiptId
                              ? "older attempt — inspect only"
                              : "another receipt — copy rules"}{" "}
                          · {item.id}
                        </NativeSelectOption>
                      ))}
                  </NativeSelect>
                </label>
                {inspectedProposal && (
                  <Button variant="outline"
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      setSaved(null);
                      setPreview(null);
                      setSelected("");
                      setActor("");
                      setReason("");
                      setStatus(
                        "Rules copied into a new draft. Preview, then save a new proposal for the current attempt.",
                      );
                    }}
                  >
                    Copy proposal rules into a new draft
                  </Button>
                )}
                <h3>4. Save, approve and apply</h3>
                <p>
                  Each step records a distinct decision. Applying never accepts
                  or verifies source records.
                </p>
                <div className="np-review">
                  <label>
                    Recipe name
                    <Input
                      value={name}
                      disabled={busy}
                      onChange={(event) => setName(event.target.value)}
                    />
                  </label>
                  <label>
                    Recipe reviewer
                    <Input
                      value={actor}
                      disabled={busy}
                      onChange={(event) => setActor(event.target.value)}
                    />
                  </label>
                  <label>
                    Recipe decision reason
                    <Textarea
                      value={reason}
                      disabled={busy}
                      onChange={(event) => setReason(event.target.value)}
                    />
                  </label>
                </div>
                {inspectedDecision && (
                  <aside
                    className="iw-notice"
                    aria-label="Saved recipe decision"
                  >
                    <strong>
                      {inspectedDecision.name} · {inspectedDecision.state}
                    </strong>
                    <p>
                      Revision {inspectedDecision.id}
                      {inspectedDecision.actor
                        ? ` · ${inspectedDecision.actor}`
                        : ""}
                    </p>
                    {inspectedDecision.reason && (
                      <p>{inspectedDecision.reason}</p>
                    )}
                  </aside>
                )}
                <div className="np-actions">
                  <Button variant="outline"
                    type="button"
                    disabled={busy || !preview || !reviewed || Boolean(saved)}
                    onClick={() =>
                      void run(async () => {
                        const revision = await api<Revision>(
                          `${base}/recipes`,
                          {
                            definition,
                            expected_attempt: attemptId,
                            name,
                            actor,
                            reason,
                          },
                        );
                        if (alive.current) {
                          setSaved({
                            ...revision,
                            receipt_id: receiptId,
                            attempt_id: attemptId,
                          });
                          setRevisions([...revisions, revision]);
                          setStatus(
                            "Proposed revision saved. Review it, then explicitly approve.",
                          );
                        }
                      })
                    }
                  >
                    Save proposed recipe
                  </Button>
                  <Button variant="outline"
                    type="button"
                    disabled={
                      busy ||
                      !currentProposal ||
                      !preview ||
                      !actor.trim() ||
                      !reason.trim()
                    }
                    onClick={() =>
                      void run(async () => {
                        const revision = await api<Revision>(
                          `${base}/recipes/${saved!.id}/approve`,
                          { expected_attempt: attemptId, actor, reason },
                        );
                        if (alive.current) {
                          setSaved(revision);
                          setRevisions([...revisions, revision]);
                          setStatus(
                            "Approved recipe saved. Apply it to create a new interpretation.",
                          );
                        }
                      })
                    }
                  >
                    Approve recipe
                  </Button>
                  <Button variant="outline"
                    type="button"
                    disabled={busy || saved?.state !== "approved"}
                    onClick={() =>
                      void run(async () => {
                        await api(`${base}/recipes/${saved!.id}/apply`, {
                          expected_attempt: attemptId,
                        });
                        if (alive.current) {
                          setStatus(
                            "Recipe applied. Review the new interpretation before accepting valid rows.",
                          );
                          await onChanged();
                        }
                      })
                    }
                  >
                    Apply approved recipe
                  </Button>
                </div>
                <h3>Reuse an approved recipe</h3>
                <p>Check reviewed source profiles against this delivery before copying their rules. A structural match is not a semantic review.</p>
                <Button variant="outline" type="button" disabled={busy} onClick={() => void run(async () => {
                  const result = await api<Compatibility>(`${base}/recipe-compatibility?expected_attempt=${encodeURIComponent(attemptId)}&offset=0&limit=20`);
                  if (alive.current) setCompatibility(result);
                })}>Check reusable source profiles</Button>
                {compatibility && <section aria-label="Source profile compatibility">
                  <p>{compatibility.notice}</p>
                  <p className="iw-muted">Showing {compatibility.items.length} of {compatibility.total} reviewed profiles. Manual mapping remains available.</p>
                  {compatibility.items.length === 0 && <p>No reviewed profile is available for this source and scope. Continue with manual mapping above.</p>}
                  <ul className="np-profiles">{compatibility.items.map(item => <li key={item.revision_id}>
                    <strong>{item.name}</strong><span>{item.status.replaceAll("_", " ")}</span>
                    {item.missing_mapped_columns.length > 0 && <p>Missing mapped columns: {item.missing_mapped_columns.join(", ")}</p>}
                    {!!item.ambiguous_columns?.length && <p>Ambiguous source columns: {item.ambiguous_columns.join(", ")}. Choose a unique binding manually.</p>}
                    {item.added_columns.length > 0 && <p>Added columns: {item.added_columns.join(", ")}</p>}
                    {item.removed_columns.length > 0 && <p>Removed columns: {item.removed_columns.join(", ")}</p>}
                    <Button variant="outline" type="button" disabled={busy || !item.reusable || !actor.trim() || !reason.trim()} onClick={() => void run(async () => {
                      const proposal = await api<Revision>(`${base}/recipes/${encodeURIComponent(item.revision_id)}/reuse`, { expected_attempt: attemptId, actor, reason });
                      if (alive.current) {
                        setDefinition(proposal.definition); setName(proposal.name); setSaved(proposal); setInspectedProposal(proposal);
                        setPreview(null); setSelected(""); setRevisions([...revisions, proposal]);
                        setStatus("Reviewed profile copied into a new proposal. Preview this delivery before explicitly approving and applying it.");
                      }
                    })}>Copy {item.name} as a proposal</Button>
                  </li>)}</ul>
                  {compatibility.next_offset !== null && <Button variant="outline" type="button" disabled={busy} onClick={() => void run(async () => {
                    const next = await api<Compatibility>(`${base}/recipe-compatibility?expected_attempt=${encodeURIComponent(attemptId)}&offset=${compatibility.next_offset}&limit=20`);
                    if (alive.current) setCompatibility({ ...next, items: [...compatibility.items, ...next.items] });
                  })}>Load more reviewed profiles</Button>}
                  <p className="iw-muted">Enter the recipe reviewer and decision reason above to copy a compatible profile. Copying never accepts rows or approves a dataset.</p>
                </section>}
                <p>
                  Only revisions compatible with this source, input profile and
                  dataset scope appear.
                </p>
                <label>
                  Compatible approved recipe
                  <NativeSelect
                    value={selected}
                    disabled={busy}
                    onChange={(event) => {
                      setSelected(event.target.value);
                      setSaved(null);
                      setInspectedProposal(null);
                      setPreview(null);
                      const revision = revisions.find(
                        (item) => item.id === event.target.value,
                      );
                      if (revision) {
                        setDefinition(revision.definition);
                        setName(revision.name);
                        setStatus(
                          "Loaded approved rules. Preview this delivery before applying.",
                        );
                      }
                    }}
                  >
                    <NativeSelectOption value="">Choose a revision</NativeSelectOption>
                    {revisions
                      .filter((item) => item.state === "approved")
                      .map((item) => (
                        <NativeSelectOption key={item.id} value={item.id}>
                          {item.name} · {item.id}
                        </NativeSelectOption>
                      ))}
                  </NativeSelect>
                </label>
                <Button variant="outline"
                  type="button"
                  disabled={busy || !selected || !preview}
                  onClick={() =>
                    void run(async () => {
                      await api(`${base}/recipes/${selected}/apply`, {
                        expected_attempt: attemptId,
                      });
                      if (alive.current) await onChanged();
                    })
                  }
                >
                  Apply selected approved recipe
                </Button>
              </>
            )}
          </>
        ))}
    </section>
  );
}
