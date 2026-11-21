import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Field, FieldLabel } from "@/components/ui/field";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

type Phone = { number: string | null; extension: string | null };
type Choice = { clinician_id: string; location_id: string; clinician_label: string; location_label: string; snapshot: string; decision_id: string; decision_reason: string; old_value: Phone; new_value: Phone; selected_evidence: { source: string; locator: string }; row_locator: string };
type Payload = { clinician_id: string; location_id: string; snapshot: string; decision_id: string; actor: string; reason: string; idempotency_key: string };
type Page = { base_version: string; choices: Choice[]; total: number; next_offset: number | null };
function phone(value: Phone) { return `${value.number || "Not supplied"} · extension: ${value.extension || "Not supplied"}`; }
const payloadKeys = ["clinician_id", "location_id", "snapshot", "decision_id", "actor", "reason", "idempotency_key"] as const;
function savedIntent(key: string): { intent: Payload | null; warning: string } {
  try {
    const value = sessionStorage.getItem(key);
    if (!value) return { intent: null, warning: "" };
    const parsed: unknown = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed) || Object.keys(parsed).length !== payloadKeys.length || !payloadKeys.every(name => typeof (parsed as Record<string, unknown>)[name] === "string" && Boolean(((parsed as Record<string, unknown>)[name] as string).trim()))) {
      return { intent: null, warning: "A saved retry request is invalid. Inspect the latest decisions before creating a candidate." };
    }
    return { intent: parsed as Payload, warning: "" };
  } catch {
    return { intent: null, warning: "Saved retry information could not be read. If a previous request had an unknown outcome, check for its candidate before creating another." };
  }
}

export function FieldMaterialization({ versionId, actor, reason, onCreated }: { versionId: string; actor: string; reason: string; onCreated: (id: string) => Promise<void> }) {
  const storageKey = `field-materialization:${versionId}`;
  const [saved] = useState(() => savedIntent(storageKey));
  const [intent, setIntent] = useState<Payload | null>(saved.intent);
  const [storageWarning, setStorageWarning] = useState(saved.warning);
  const [choices, setChoices] = useState<Choice[] | null>(null);
  const [selected, setSelected] = useState("");
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [created, setCreated] = useState("");
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const choice = choices?.find(item => item.decision_id === selected);
  function remember(value: Payload | null) {
    setIntent(value);
    try {
      if (value) sessionStorage.setItem(storageKey, JSON.stringify(value));
      else sessionStorage.removeItem(storageKey);
      setStorageWarning("");
    } catch {
      setStorageWarning(value
        ? "This browser could not save the retry request. If the outcome is unknown, keep this page open and retry here with the same request; check for a candidate before leaving."
        : "This browser could not clear saved retry information. A later retry may recover the same candidate; check the candidate list before starting another request.");
    }
  }
  async function load(offset = 0) {
    setPending(true); setError(""); setSelected("");
    // Never leave a selectable result after a failed refresh or page request.
    if (offset === 0) { setChoices(null); setNextOffset(null); }
    try {
      const response = await fetch(`/api/feed-versions/${encodeURIComponent(versionId)}/field-materialization?offset=${offset}&limit=20`);
      const result = await response.json() as Page & { detail?: string };
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Unable to inspect reviewed fields.");
      if (result.base_version !== versionId || (result.next_offset !== null && result.next_offset <= offset)) throw new Error("The review page was inconsistent. Inspect again.");
      if (!alive.current) return;
      setChoices(previous => offset === 0 ? result.choices : [...(previous ?? []), ...result.choices]);
      setTotal(result.total); setNextOffset(result.next_offset);
    } catch (err) { if (alive.current) { setChoices(null); setNextOffset(null); setError(err instanceof Error ? err.message : "Unable to inspect reviewed fields."); } }
    finally { if (alive.current) setPending(false); }
  }
  async function create(payload: Payload) {
    setPending(true); setError(""); remember(payload);
    try {
      const response = await fetch(`/api/feed-versions/${encodeURIComponent(versionId)}/field-materialization`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const result = await response.json();
      if (!response.ok) {
        if (response.status >= 400 && response.status < 500) { remember(null); setChoices(null); setSelected(""); setNextOffset(null); }
        throw new Error(typeof result.detail === "string" ? result.detail : "Unable to create candidate.");
      }
      remember(null);
      if (alive.current) { setCreated(result.id); setChoices(null); setSelected(""); }
      await onCreated(result.id);
    } catch (err) { if (alive.current) setError(err instanceof Error ? err.message : "Unable to create candidate."); }
    finally { if (alive.current) setPending(false); }
  }
  function submit() {
    if (!choice || !actor.trim() || !reason.trim()) return;
    void create({ clinician_id: choice.clinician_id, location_id: choice.location_id, snapshot: choice.snapshot, decision_id: choice.decision_id, actor: actor.trim(), reason: reason.trim(), idempotency_key: crypto.randomUUID() });
  }
  return <section aria-labelledby="materialization-heading" className="mf-panel">
    <h3 id="materialization-heading">Create a candidate from a reviewed phone</h3>
    <p>Choose a reviewed office phone to copy into a complete new roster. The current approved version remains available until a separate approval. This does not verify a provider or update a payer.</p>
    {storageWarning && <Alert><AlertTitle>Retry storage unavailable</AlertTitle><AlertDescription>{storageWarning}</AlertDescription></Alert>}
    {error && <Alert variant="destructive"><AlertTitle>Action not completed</AlertTitle><AlertDescription>{error}{intent ? " The outcome may be unknown. Retry the same request before starting another." : " Inspect the latest decisions before trying again."}</AlertDescription></Alert>}
    {created ? <><p>Candidate created. It still needs a separate dataset review and approval.</p><Button variant="outline" disabled={pending} onClick={() => void onCreated(created).catch(err => setError(err instanceof Error ? err.message : "Unable to open candidate."))}>Open created candidate</Button></> : intent ? <><p>A previous request may have created a candidate. Retry sends the same selection, attribution and request key.</p><Button disabled={pending} onClick={() => void create(intent)}>Retry same candidate request</Button></> : <>
      <Button variant="outline" disabled={pending} onClick={() => void load()}>Inspect reviewed phone decisions</Button>
      {choices && <><p>{choices.length} eligible {choices.length === 1 ? "decision" : "decisions"} found{nextOffset !== null ? ` so far; more reviewed scopes remain (up to ${total} scopes total)` : ` across ${total} reviewed scopes`}.</p>
        {choices.length === 0 && nextOffset === null && <p>No current selected phone decision changes exactly one linked row in this version. Review identity links and a phone in Reconciliation first.</p>}
        {choices.length > 0 && <Field><FieldLabel htmlFor="materialization-choice">Reviewed office and clinician</FieldLabel><NativeSelect id="materialization-choice" value={selected} disabled={pending} onChange={event => setSelected(event.target.value)}><NativeSelectOption value="">Choose a reviewed phone</NativeSelectOption>{choices.map(item => <NativeSelectOption value={item.decision_id} key={item.decision_id}>{item.clinician_label} · {item.location_label}</NativeSelectOption>)}</NativeSelect></Field>}
        {nextOffset !== null && <Button variant="outline" disabled={pending} onClick={() => void load(nextOffset)}>Inspect more reviewed scopes</Button>}
        {choice && <><p><strong>Scope:</strong> {choice.clinician_label} · {choice.location_label} · roster row {choice.row_locator}</p><p><strong>Current roster phone:</strong> {phone(choice.old_value)}<br /><strong>Reviewed phone:</strong> {phone(choice.new_value)}</p><p><strong>Selected source:</strong> {choice.selected_evidence.source} · {choice.selected_evidence.locator}<br /><strong>Review reason:</strong> {choice.decision_reason || "Not supplied"}</p><Button disabled={pending || !actor.trim() || !reason.trim()} onClick={submit}>Create roster candidate</Button>{(!actor.trim() || !reason.trim()) && <p>Enter a reviewer and decision reason in Decision attribution before creating the candidate.</p>}</>}
      </>}
    </>}
  </section>;
}
