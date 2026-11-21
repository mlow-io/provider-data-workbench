import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ApprovedExportReview } from "./ApprovedExportReview";
import { FieldMaterialization } from "./FieldMaterialization";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import "./managed-feeds.css";
import { DeliveryReviewSummary } from "./DeliveryReviewSummary";
import type { DeliveryComparison } from "./RecurringImport";
import { navigateWorkspace, useWorkspaceQuery, workspaceHref, useWorkspaceActionGuard } from "./workspaceNavigation";

type Recipe = { id: string; name: string; source: string; scope: string | Record<string, unknown>; definition: { mapping: Record<string, string> } };
type Contract = { id: string; state: string; definition: { recipe_revision_id: string; required_headers: string[]; row_change_fraction?: number; designation?: string } };
type Job = { id: string; kind?: string; state: string; error?: string | null; receipt_id?: string; attempt_id?: string; execution_count: number };
type VersionSummary = { id: string; kind?: string; state: string; delivery_id: string; period: string; created_at: string };
type Feed = { id: string; name: string; source: string; scope: string | Record<string, unknown>; revision: number; config: { inbox: string; owner: string; enabled: boolean; contract_id: string | null; start_date?: string }; contracts: Contract[]; jobs: Job[]; versions: VersionSummary[]; windows: { period?: string; state?: string; status?: string }[]; issues?: { source_ref: string; message: string }[] };
type Finding = { code: string; severity: string; message: string };
type CorrectionPhone = { phone: string | null; phone_extension: string | null };
type EffectiveCorrections = { baseline_version: string; fields: string[]; notice: string; total: number; counts: { changed: number; unchanged: number; missing: number; blocked_invalid: number; unresolved: number }; entries: { key: unknown; status: string; old: CorrectionPhone; new: CorrectionPhone | null; previous_locator: string | null; current_locator: string | null; decision_id: string }[]; entry_count?: number };
type Version = { id: string; feed_id?: string; kind?: string; report_notice?: string; state: string; report_hash: string; report: { counts: Record<string, number | null>; baseline_version?: string | null; comparison: DeliveryComparison | null; effective_corrections?: EffectiveCorrections | null; findings: Finding[] }; review: { code: string; disposition: string; actor: string; reason: string }[]; rows: unknown[]; current_version: string | null; delivery: unknown; manifest: { receipt_id?: string; attempt_id?: string; designation?: string; notice?: string; source_delivery?: {period?: string}; [key: string]: unknown } };
type Current = { version_id: string; stale: boolean; notice: string };

function scopeLabel(scope: unknown) { return typeof scope === "string" ? scope : JSON.stringify(scope); }
function correctionPhone(value: CorrectionPhone | null) {
  return value ? `${value.phone ?? "Not supplied"} · extension: ${value.phone_extension ?? "Not supplied"}` : "Unavailable";
}
function EffectiveCorrectionReview({ comparison }: { comparison: EffectiveCorrections }) {
  const labels = [["changed", "Changed"], ["unchanged", "Unchanged"], ["missing", "Missing"], ["blocked_invalid", "Invalid"], ["unresolved", "Unresolved"]] as const;
  const entries = comparison.entries ?? [];
  return <section aria-label="Effective corrected roster comparison">
    <h3>Incoming source against corrected roster</h3>
    <p>Compares the incoming source with the effective phone and extension in approved baseline <code>{comparison.baseline_version}</code>, for previously corrected source keys. The source-to-source comparison follows separately.</p>
    <p>{comparison.notice} Missing or unresolved keys do not establish closure.</p>
    <dl className="mf-summary-counts"><div><dt>Corrected keys assessed</dt><dd>{comparison.total}</dd></div>{labels.map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{comparison.counts[key]}</dd></div>)}</dl>
    <p>Showing {entries.length} of {comparison.entry_count ?? comparison.total} comparison entries. This is a bounded sample; counts cover all assessed keys.</p>
    {entries.length > 0 && <div className="mf-evidence-table" role="region" aria-label="Corrected roster comparison sample" tabIndex={0}><Table aria-label="Corrected roster comparison entries"><TableHeader><TableRow><TableHead scope="col">Source key / status</TableHead><TableHead scope="col">Approved effective phone</TableHead><TableHead scope="col">Incoming source phone</TableHead><TableHead scope="col">Evidence</TableHead></TableRow></TableHeader><TableBody>{entries.map((entry, index) => <TableRow key={index}><TableCell>{scopeLabel(entry.key)}<br /><Badge variant="secondary">{entry.status.replaceAll("_", " ")}</Badge></TableCell><TableCell>{correctionPhone(entry.old)}</TableCell><TableCell>{correctionPhone(entry.new)}</TableCell><TableCell>Decision {entry.decision_id}<br />Prior row {entry.previous_locator ?? "Unavailable"}<br />Incoming row {entry.current_locator ?? "Unavailable"}</TableCell></TableRow>)}</TableBody></Table></div>}
  </section>;
}

async function request<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, body === undefined ? undefined : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const value = await response.json();
  if (!response.ok) throw new Error(typeof value.detail === "string" ? value.detail : "The request could not be completed. Reload the evidence before trying again.");
  return value as T;
}

export function ManagedFeeds() {
  const query = useWorkspaceQuery();
  const actionGuard = useWorkspaceActionGuard();
  const feedId = query.get("feed") ?? "";
  const versionId = query.get("version") ?? "";
  const inspectorRef = useRef<HTMLElement>(null);
  const listRef = useRef<HTMLElement>(null);
  const [focusDetail, setFocusDetail] = useState(Boolean(versionId));
  const focusDetailRef = useRef(focusDetail);
  focusDetailRef.current = focusDetail;
  const selection = `${feedId}:${versionId}`;
  const selectionRef = useRef(selection);
  selectionRef.current = selection;
  const feedRef = useRef(feedId); feedRef.current = feedId;
  const versionRef = useRef(versionId); versionRef.current = versionId;
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [registryLoaded, setRegistryLoaded] = useState(false);
  const [feed, setFeed] = useState<Feed | null>(null);
  const [version, setVersion] = useState<Version | null>(null);
  const [current, setCurrent] = useState<Current | null>(null);
  const [actor, setActor] = useState("");
  const [reason, setReason] = useState("");
  const [recipeId, setRecipeId] = useState("");
  const [name, setName] = useState("");
  const [inbox, setInbox] = useState("");
  const [owner, setOwner] = useState("");
  const [startDate, setStartDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reviewGeneration, setReviewGeneration] = useState(0);
  const selectedRecipe = recipes.find(item => item.id === recipeId);
  const attributed = actor.trim() !== "" && reason.trim() !== "";
  const attribution = { actor: actor.trim(), reason: reason.trim() };

  useEffect(() => {
    setFocusDetail(Boolean(versionId));
  }, [feedId, versionId]);

  useEffect(() => {
    if (focusDetail && version?.id === versionId) inspectorRef.current?.focus();
  }, [focusDetail, version?.id, versionId]);
  function selectVersion(id: string) {
    focusDetailRef.current = true;
    setFocusDetail(true);
    navigateWorkspace("feeds", { feed: feedId, version: id });
  }
  function returnToDeliveries() {
    focusDetailRef.current = false;
    setFocusDetail(false);
    requestAnimationFrame(() => {
      const focused = document.activeElement;
      // Restore focus only while it is still in the hidden detail. A user who
      // already moved to a list or navigation control keeps that new focus.
      if (!focusDetailRef.current && (focused === document.body || inspectorRef.current?.contains(focused))) listRef.current?.focus();
    });
  }

  async function loadRegistry() {
    setRegistryLoaded(false);
    const [registry, approved] = await Promise.all([request<{ items: Feed[] }>("/api/feeds"), request<{ items: Recipe[] }>("/api/feeds/recipes")]);
    setFeeds(registry.items);
    setRecipes(approved.items);
    setRegistryLoaded(true);
  }
  useEffect(() => {
    let active = true;
    Promise.all([request<{ items: Feed[] }>("/api/feeds"), request<{ items: Recipe[] }>("/api/feeds/recipes")])
      .then(([registry, approved]) => { if (active) { setFeeds(registry.items); setRecipes(approved.items); setRegistryLoaded(true); } })
      .catch(value => { if (active) setError(String(value.message)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setFeed(null); setVersion(null); setCurrent(null); setError("");
    if (!feedId) {
      if (versionId) setError("A dataset version needs its feed context. Choose a registered feed.");
      setPending(false);
      return;
    }
    setPending(true);
    void (async () => {
      const detail = await request<Feed>(`/api/feeds/${encodeURIComponent(feedId)}`);
      if (versionId && !detail.versions.some(item => item.id === versionId)) throw new Error("This version does not belong to the selected feed. Choose a version from that feed.");
      const response = await fetch(`/api/feeds/${encodeURIComponent(feedId)}/current`);
      if (!response.ok && response.status !== 404) throw new Error("Unable to read the approved consumer version. Reload the feed.");
      const approved = response.ok ? await response.json() as Current : null;
      const selectedVersion = versionId ? await request<Version>(`/api/feed-versions/${encodeURIComponent(versionId)}`) : null;
      if (selectedVersion?.feed_id && selectedVersion.feed_id !== feedId) throw new Error("Dataset version has incompatible feed context.");
      if (active) { setFeed(detail); setCurrent(approved); setVersion(selectedVersion); }
    })().catch(value => { if (active) setError(value.message); }).finally(() => { if (active) setPending(false); });
    return () => { active = false; };
  }, [feedId, versionId]);

  async function loadFeed(id: string) {
    if (feedRef.current !== id) return;
    const expectedSelection = selectionRef.current;
    const detail = await request<Feed>(`/api/feeds/${encodeURIComponent(id)}`);
    const response = await fetch(`/api/feeds/${id}/current`);
    if (!response.ok && response.status !== 404) throw new Error("Unable to read the approved consumer version. Reload the feed.");
    const approved = response.ok ? await response.json() as Current : null;
    if (selectionRef.current === expectedSelection) { setFeed(detail); setCurrent(approved); }
    return detail;
  }
  async function openVersion(id: string) {
    if (versionRef.current !== id) return;
    const expectedSelection = selectionRef.current;
    const detail = await request<Version>(`/api/feed-versions/${encodeURIComponent(id)}`);
    if (selectionRef.current === expectedSelection) setVersion(detail);
  }
  async function act(operation: (isCurrent: () => boolean) => Promise<void>) {
    const expectedSelection = selectionRef.current;
    const origin = actionGuard.capture();
    const isCurrent = () => actionGuard.isCurrent(origin) && selectionRef.current === expectedSelection;
    setPending(true); setError(""); setNotice("");
    try { await operation(isCurrent); }
    catch (value) { if (isCurrent()) setError(value instanceof Error ? value.message : String(value)); }
    finally { if (isCurrent()) setPending(false); }
  }
  function chooseFeed(id: string) {
    setNotice("");
    navigateWorkspace("feeds", { feed: id });
  }
  async function refresh() {
    setReviewGeneration(value => value + 1);
    await loadRegistry();
    if (feed) await loadFeed(feed.id);
    if (version) await openVersion(version.id);
  }
  function register(event: FormEvent) {
    event.preventDefault();
    if (!selectedRecipe || !attributed) return;
    void act(async (isCurrent) => {
      const saved = await request<Feed>("/api/feeds", { name, source: selectedRecipe.source, scope: selectedRecipe.scope, inbox, owner, ...(startDate ? { start_date: startDate } : {}), ...attribution });
      await loadRegistry(); if (!isCurrent()) return;
      setNotice("Feed registered and disabled. Propose and approve its contract before enabling deliveries.");
      navigateWorkspace("feeds", { feed: saved.id });
    });
  }
  function proposeContract() {
    if (!feed || !selectedRecipe) return;
    void act(async (isCurrent) => {
      await request(`/api/feeds/${feed.id}/contracts`, { definition: { recipe_revision_id: selectedRecipe.id, required_headers: [...new Set(Object.values(selectedRecipe.definition.mapping))], encoding: "utf-8-sig", delimiter: ",", row_change_fraction: 0.2 }, ...attribution });
      await loadFeed(feed.id); if (isCurrent()) setNotice("Contract proposed. Review it before approving; the feed remains unchanged.");
    });
  }
  function approveContract(contractId: string) {
    if (!feed) return;
    void act(async (isCurrent) => { await request(`/api/feeds/${feed.id}/contracts/${contractId}/approve`, attribution); await loadFeed(feed.id); if (isCurrent()) setNotice("Contract approved. Select Enable with this contract to begin managed deliveries."); });
  }
  function configure(enabled: boolean, contractId: string | null) {
    if (!feed) return;
    void act(async (isCurrent) => { await request(`/api/feeds/${feed.id}/configure`, { expected_revision: feed.revision, config: { enabled, contract_id: contractId }, ...attribution }); await loadFeed(feed.id); await loadRegistry(); if (isCurrent()) setNotice(enabled ? "Feed enabled. Processing still requires the running worker or an explicit check." : "Feed disabled for new deliveries. Retained jobs and evidence remain available."); });
  }
  function review(code: string, disposition: string) {
    if (!version) return;
    void act(async (isCurrent) => { await request(`/api/feed-versions/${version.id}/exceptions`, { expected_report: version.report_hash, code, disposition, ...attribution }); await openVersion(version.id); if (isCurrent()) setNotice(disposition === "acknowledged" ? "Risk acknowledged for this report. Dataset approval remains a separate decision." : "Exception deferred; its approval hold remains."); });
  }
  function decide(decision: string) {
    if (!version || !feed) return;
    void act(async (isCurrent) => {
      await request(`/api/feed-versions/${version.id}/decide`, { expected_report: version.report_hash, expected_current: version.current_version, decision, idempotency_key: crypto.randomUUID(), ...attribution });
      await openVersion(version.id); await loadFeed(feed.id); await loadRegistry(); if (isCurrent()) setNotice(decision === "approved" ? "Dataset version approved. The consumer can now retrieve this exact version." : "Candidate rejected. Its original delivery and review evidence are preserved.");
    });
  }
  const findings = version?.report.findings ?? [];
  const acknowledged = (code: string) => version?.review.filter(item => item.code === code).at(-1)?.disposition === "acknowledged";
  const blocked = findings.some(item => item.severity === "hard" || (item.severity === "hold" && !acknowledged(item.code)));
  const compatibleRecipes = feed ? recipes.filter(item => item.source === feed.source && JSON.stringify(item.scope) === JSON.stringify(feed.scope)) : recipes;

  const attributionForm = <section className="mf-attribution" aria-labelledby="feed-reviewer-heading"><h2 id="feed-reviewer-heading">Decision attribution</h2><p>Every configuration, exception and approval decision records a local reviewer assertion and its reason.</p><FieldGroup className="mf-form"><Field><FieldLabel htmlFor="feed-field-0">Reviewer</FieldLabel><Input id="feed-field-0" value={actor} onChange={event => setActor(event.target.value)} /></Field><Field><FieldLabel htmlFor="feed-field-1">Decision reason</FieldLabel><Input id="feed-field-1" value={reason} onChange={event => setReason(event.target.value)} /></Field></FieldGroup></section>;

  return <main className="iw-shell mf-shell" aria-busy={loading || pending}>
    <header className="iw-heading"><p className="iw-eyebrow">Recurring provider data</p><h1>Review deliveries</h1><p>Choose a feed and delivery, inspect changes and quality holds, then approve the exact dataset version for its consumer.</p></header>
    <p className="mf-boundary"><strong>Local dataset approval</strong> · Valid rows become available to the local consumer; recipient directories are unchanged.</p>
    <div className="mf-toolbar"><Button variant="outline" disabled={pending || loading} onClick={() => void act(refresh)}>Reload evidence</Button><span aria-live="polite">{pending ? "Saving or loading evidence…" : notice}</span></div>
    {error && <Alert variant="destructive"><AlertTitle>Action not completed.</AlertTitle><AlertDescription>{error} Reload evidence, review the latest report, then decide again.</AlertDescription></Alert>}
    {loading && <p role="status">Loading the source registry…</p>}
    <div className="mf-workbench" data-detail-open={focusDetail && Boolean(version)}><aside className="mf-selection-grid" ref={listRef} tabIndex={-1} aria-label="Delivery selection">
    <section className="mf-panel" aria-labelledby="feed-registry-heading"><div className="mf-section-heading"><div><p className="iw-eyebrow">Source selection</p><h2 id="feed-registry-heading">Registered feeds</h2></div></div>
      {!loading && registryLoaded && feeds.length === 0 && <p>No managed feeds yet. Start with an approved clinic normalization recipe in <a href="?view=intake">Intake</a>. For a guided first try, choose the synthetic clinic workbook there when sample mode is enabled.</p>}
      {!loading && !pending && !registryLoaded && <p>Registry information is unavailable. Any previously displayed feed list may be out of date.</p>}
      <div className="mf-feed-list">{feeds.map(item => <Button variant="outline" key={item.id} className={feed?.id === item.id ? "mf-feed selected" : "mf-feed"} disabled={pending} onClick={() => chooseFeed(item.id)} aria-pressed={feed?.id === item.id}><strong>{item.name}</strong><span>{item.source} · {scopeLabel(item.scope)}</span><small>{item.config.enabled ? "Enabled" : "Disabled"} · {item.config.owner}</small></Button>)}</div>
      <details key={`register:${feedId}:${versionId}`}><summary>Register a clinic CSV feed</summary><form className="mf-form" onSubmit={register}>
        <Field><FieldLabel htmlFor="feed-field-2">Feed name</FieldLabel><Input id="feed-field-2" required value={name} onChange={event => setName(event.target.value)} /></Field>
        <Field><FieldLabel htmlFor="feed-field-3">Approved source recipe</FieldLabel><NativeSelect id="feed-field-3" required value={recipeId} onChange={event => setRecipeId(event.target.value)}><NativeSelectOption value="">Choose an approved recipe</NativeSelectOption>{recipes.map(item => <NativeSelectOption key={item.id} value={item.id}>{item.name} · {item.source} · {scopeLabel(item.scope)}</NativeSelectOption>)}</NativeSelect></Field>
        <Field><FieldLabel htmlFor="feed-field-4">Local inbox directory</FieldLabel><Input id="feed-field-4" required value={inbox} onChange={event => setInbox(event.target.value)} placeholder="Absolute path to the delivery inbox" /></Field>
        <Field><FieldLabel htmlFor="feed-field-5">Feed owner</FieldLabel><Input id="feed-field-5" required value={owner} onChange={event => setOwner(event.target.value)} /></Field>
        <Field><FieldLabel htmlFor="feed-field-6">First expected period</FieldLabel><Input id="feed-field-6" type="date" value={startDate} onChange={event => setStartDate(event.target.value)} /></Field>
        <p className="mf-help">Weekly Monday 09:00 UTC, with a 24-hour arrival grace period. Registration preserves the approved recipe’s exact source and dataset scope. Add reviewer and reason below before saving.</p>
        <Button variant="outline" disabled={pending || !attributed || !selectedRecipe} type="submit">Register disabled feed</Button>
      </form></details>
    </section>
    {feed && feed.id === feedId && <section className="mf-panel" aria-labelledby="feed-versions-heading"><p className="iw-eyebrow">Delivery selection</p><h2 id="feed-versions-heading">Dataset versions</h2><h3>{feed.name}</h3><div className={current?.stale ? "mf-current stale" : "mf-current"}>{current ? <><strong>Current approved version</strong><details><summary>Approved version identifier</summary><code>{current.version_id}</code></details><p>{current.notice}{current.stale ? " · Freshness warning" : ""}</p><a href={`/api/feed-versions/${current.version_id}/export`}>Download current approved JSON</a><a href={workspaceHref("feeds", { feed: feed.id, version: current.version_id })}>Review current approved version</a></> : <p>No approved dataset is available to the consumer. New candidates do not become current automatically.</p>}</div>
        <div className="mf-version-list"><Table aria-label="Dataset versions"><TableHeader><TableRow><TableHead>Delivery / period</TableHead><TableHead>Status</TableHead></TableRow></TableHeader><TableBody>{feed.versions.map(item => <TableRow key={item.id} data-state={version?.id === item.id ? "selected" : undefined}><TableCell><Button variant="ghost" data-version-id={item.id} disabled={pending} aria-pressed={version?.id === item.id} onClick={() => selectVersion(item.id)}><span className="sr-only">{item.state} · </span>{item.kind === "derived_field_candidate" ? "Reviewed phone candidate · " : ""}{item.period}<span className="mf-version-id">{item.id.slice(0, 8)}</span></Button></TableCell><TableCell><Badge variant={item.state === "approved" ? "default" : "secondary"}>{item.state}</Badge></TableCell></TableRow>)}</TableBody></Table></div>{feed.versions.length === 0 && <p>No candidate versions yet.</p>}
      </section>}

    </aside>
    <div className="mf-inspector-column">
    {!version && <section className="mf-panel"><h2>{pending ? "Loading selected evidence…" : "Select a dataset version"}</h2><p>Choose a delivery to inspect its report, review holds and prepare an approved handoff.</p>{!pending && attributionForm}</section>}

    {version && version.id === versionId && <section ref={inspectorRef} tabIndex={-1} className="mf-panel mf-version-detail" aria-labelledby="feed-version-heading"><Button variant="ghost" className="mf-detail-return" onClick={returnToDeliveries}>← Back to deliveries</Button><p className="iw-eyebrow">Delivery decision</p><h2 id="feed-version-heading">Dataset review · {version.state}</h2><div className="mf-context"><strong>{feed?.name || "Selected delivery"}</strong><span>Source: {feed?.source || "Unavailable"} · Period: {String(version.manifest.source_delivery?.period ?? "Not supplied")}</span><details><summary>Dataset version identity</summary><code>{version.id}</code></details><span>Evidence designation: {version.manifest.designation || "Not supplied"}</span>{version.kind === "derived_field_candidate" && <p><strong>Reviewed phone candidate.</strong> {version.report_notice}</p>}{version.manifest.notice && <p>{version.manifest.notice}</p>}</div>
      <aside className="iw-notice" aria-label="Delivery next step">
        <strong>{version.kind === "derived_field_candidate" && version.state === "approved" ? "Approved correction is ready for handoff." : version.state === "approved" ? "Approved evidence is ready for comparison." : version.state === "rejected" ? "Rejected delivery retained for investigation." : blocked ? "Review the holds before approving this delivery." : "Review the evidence, then explicitly approve or reject."}</strong>
        <p>{version.kind === "derived_field_candidate" && version.state === "approved" ? "The approved candidate and its export include the reviewed correction. Reconciliation uses the retained original source interpretation, not the corrected roster." : version.state === "approved" ? "Prepare a comparison with this exact interpretation, choose other source deliveries, and review the evidence before creating a run." : "The previous approved consumer version remains available. Processing and navigation never approve a candidate."}</p>
        <div className="mf-actions">
          {version.manifest.receipt_id && <a href={workspaceHref("intake", { receipt: version.manifest.receipt_id, attempt: version.manifest.attempt_id })}>{version.kind === "derived_field_candidate" ? "Inspect original source evidence" : "Inspect this version's retained evidence"}</a>}
          {version.state === "approved" && version.manifest.receipt_id && version.manifest.attempt_id && <a href={workspaceHref("reconciliation", { feed: feed?.id, version: version.id, receipt: version.manifest.receipt_id, attempt: version.manifest.attempt_id })}>{version.kind === "derived_field_candidate" ? "Prepare reconciliation from original source evidence" : "Prepare reconciliation from this approved version"}</a>}
        </div>
      </aside>
      <dl className="mf-counts">{Object.entries(version.report.counts).map(([key, value]) => <div key={key}><dt>{{raw: "Source rows", valid: "Valid rows", quarantined: "Quarantined rows", unique: "Distinct source keys"}[key] ?? key.replaceAll("_", " ")}</dt><dd>{value === null ? "Not assessed" : value}</dd></div>)}</dl>
      {version.state === "approved" && <ApprovedExportReview key={version.id} versionId={version.id} />}
      <Tabs key={version.id} defaultValue="evidence"><TabsList aria-label="Delivery evidence views"><TabsTrigger value="evidence">Evidence & holds</TabsTrigger><TabsTrigger value="original">Original & history</TabsTrigger></TabsList><TabsContent value="evidence">
      <h3>Quality and drift findings</h3>{findings.length === 0 && <p>No quality holds. Explicit dataset approval is still required.</p>}<ul className="mf-findings">{findings.map(finding => <li key={finding.code} className={`mf-finding ${finding.severity}`}><div><strong>{finding.severity === "hard" ? "Approval blocked" : finding.severity === "hold" ? "Review hold" : "Warning"}</strong><p>{finding.message}</p><code>{finding.code}</code>{acknowledged(finding.code) && <p>Risk acknowledged for this report.</p>}</div>{version.state === "candidate" && finding.severity === "hold" && <div className="mf-actions"><Button variant="outline" disabled={pending || !attributed} onClick={() => review(finding.code, "acknowledged")}>Acknowledge {finding.code}</Button><Button variant="outline" disabled={pending || !attributed} onClick={() => review(finding.code, "deferred")}>Defer {finding.code}</Button></div>}{finding.severity === "hard" && <p>Correct the source or contract and reprocess. Acknowledgement cannot bypass this blocker.</p>}</li>)}</ul>
      {version.report.effective_corrections && <EffectiveCorrectionReview comparison={version.report.effective_corrections} />}
      <p>Source-to-source comparison:</p><DeliveryReviewSummary comparison={version.report.comparison} baselineVersion={version.report.baseline_version} /></TabsContent><TabsContent value="original">      <details><summary>Comparison and original evidence</summary><h4>Pinned comparison</h4><pre>{JSON.stringify(version.report.comparison, null, 2)}</pre><h4>Delivery manifest</h4><pre>{JSON.stringify(version.manifest, null, 2)}</pre><h4>Retained delivery</h4><pre>{JSON.stringify(version.delivery, null, 2)}</pre><h4>Sample rows</h4><p>This preview is bounded. The approved JSON export retains the complete selected dataset and quarantine evidence.</p><pre>{JSON.stringify(version.rows, null, 2)}</pre></details>
      {version.review.length > 0 && <details><summary>Exception review history</summary><ul>{version.review.map((item, index) => <li key={index}>{item.code} · {item.disposition} · {item.actor}: {item.reason}</li>)}</ul></details>}

</TabsContent></Tabs>
      {version.state === "candidate" ? attributionForm : <details><summary>Decision attribution for additional actions</summary>{attributionForm}</details>}
      {version.state === "approved" && current?.version_id === version.id && <FieldMaterialization key={`${version.id}:${reviewGeneration}`} versionId={version.id} actor={actor} reason={reason} onCreated={async id => { const expected = `${feedId}:${version.id}`; if (selectionRef.current !== expected) return; const origin = actionGuard.capture(); await loadFeed(feedId); if (actionGuard.isCurrent(origin) && selectionRef.current === expected) selectVersion(id); }} />}
      {version.state === "candidate" ? <><p>{blocked ? "Resolve hard blockers and explicitly acknowledge or resolve review holds before approval." : "Only validated rows will be approved. Quarantine and review limitations remain in the evidence envelope."}</p><div className="mf-actions"><Button disabled={pending || !attributed || blocked || Boolean(error)} onClick={() => decide("approved")}>Approve dataset version</Button><Button variant="outline" disabled={pending || !attributed} onClick={() => decide("rejected")}>Reject candidate</Button></div></> : version.state === "approved" ? <a className="mf-download" href={`/api/feed-versions/${version.id}/export`}>Download this approved version JSON</a> : <p>This candidate was rejected. Its evidence remains retained.</p>}
    </section>}
    </div></div>
    {feed && feed.id === feedId && <>
<details className="mf-panel mf-secondary"><summary>Processing and delivery history</summary><section className="mf-panel" aria-labelledby="feed-jobs-heading"><p className="iw-eyebrow">Processing history</p><h2 id="feed-jobs-heading">Deliveries and jobs</h2><Button variant="outline" disabled={pending || !feed.config.enabled} onClick={() => void act(async (isCurrent) => { await request(`/api/feeds/${feed.id}/tick`, {}); await loadFeed(feed.id); await loadRegistry(); if (isCurrent()) setNotice("Delivery check completed. Review the processing history and candidate results."); })}>Check deliveries and process one job</Button>
        {(feed.issues ?? []).length > 0 && <div className="mf-error" role="status"><strong>Delivery discovery issues</strong><ul>{feed.issues!.map((issue, index) => <li key={index}>{issue.source_ref}: {issue.message}</li>)}</ul></div>}
        <details><summary>Processing history and delivery windows ({feed.jobs.length} jobs)</summary><p>The local background worker checks finalized delivery manifests while running. An explicit check processes at most one job. Retained jobs resume when the worker restarts.</p>
        <ul className="mf-jobs">{feed.jobs.map(job => <li key={job.id}><div><strong>{job.kind === "derived_field_candidate" ? "Reviewed phone candidate" : "Source delivery"} · {job.state}</strong> · {job.execution_count} execution attempts<code>{job.id}</code>{job.error && <p className="mf-error-text">{job.error}</p>}{job.receipt_id && <span><a href={workspaceHref("intake", { receipt: job.receipt_id, attempt: job.attempt_id })}>Open retained delivery</a><code>Receipt {job.receipt_id}</code></span>}</div><div className="mf-actions">{job.kind !== "derived_field_candidate" && job.state === "failed" && <Button variant="outline" disabled={pending || !attributed} onClick={() => void act(async (isCurrent) => { await request(`/api/feed-jobs/${job.id}/retry`, attribution); await loadFeed(feed.id); })}>Retry job</Button>}{job.kind !== "derived_field_candidate" && ["succeeded", "failed"].includes(job.state) && <Button variant="outline" disabled={pending || !attributed} onClick={() => void act(async (isCurrent) => { await request(`/api/feed-jobs/${job.id}/reprocess`, attribution); await loadFeed(feed.id); if (isCurrent()) setNotice("New processing job requested against the active contract and approved baseline. Prior evidence is retained."); })}>Reprocess with current contract</Button>}{job.kind !== "derived_field_candidate" && ["queued", "running", "retry_wait", "retry-wait"].includes(job.state) && <Button variant="outline" disabled={pending || !attributed} onClick={() => void act(async (isCurrent) => { await request(`/api/feed-jobs/${job.id}/cancel`, attribution); await loadFeed(feed.id); })}>Cancel job</Button>}</div></li>)}</ul>{feed.jobs.length === 0 && <p>No deliveries processed yet.</p>}
        {feed.windows.length > 0 && <details><summary>Expected delivery windows</summary><ul>{feed.windows.map((window, index) => <li key={index}>{window.period} · {window.state ?? window.status}</li>)}</ul></details>}
        </details>
      </section></details>
<details className="mf-panel mf-configuration" open={!version}><summary>Source configuration and contract revisions</summary><p className="iw-eyebrow">Source setup</p><h2 id="feed-contract-heading">Configuration details</h2><dl className="mf-meta"><div><dt>Source / dataset</dt><dd>{feed.source} / {scopeLabel(feed.scope)}</dd></div><div><dt>Inbox</dt><dd>{feed.config.inbox}</dd></div><div><dt>Owner / configuration</dt><dd>{feed.config.owner} · revision {feed.revision}</dd></div><div><dt>Cadence</dt><dd>Monday 09:00 UTC · 24-hour grace</dd></div></dl>
        <h3>Contract revisions</h3><p>Contract approval authorizes the interpretation rules. Dataset approval separately authorizes each delivery’s valid rows for consumption.</p>
        {feed.contracts.length === 0 && <p>No contract revision yet.</p>}
        <div className="mf-contracts">{feed.contracts.map(contract => <article key={contract.id}><strong>{contract.state === "approved" ? "Approved contract" : "Proposed contract"}</strong><code>{contract.id}</code><p>Required headers: {contract.definition.required_headers.join(", ")}</p><p>Data designation: {contract.definition.designation ?? "Inspect retained recipe source"}</p><p>Row-count drift hold: {Math.round((contract.definition.row_change_fraction ?? 0.2) * 100)}% · Recipe <code>{contract.definition.recipe_revision_id}</code></p>{contract.state === "proposed" && <Button variant="outline" disabled={pending || !attributed} onClick={() => approveContract(contract.id)}>Approve contract</Button>}{contract.state === "approved" && <Button variant="outline" disabled={pending || !attributed || (feed.config.enabled && feed.config.contract_id === contract.id)} onClick={() => configure(true, contract.id)}>{feed.config.contract_id === contract.id && feed.config.enabled ? "Active contract" : "Enable with this contract"}</Button>}</article>)}</div>
        <div className="mf-actions"><Field><FieldLabel htmlFor="feed-field-7">Recipe for new contract</FieldLabel><NativeSelect id="feed-field-7" value={recipeId} onChange={event => setRecipeId(event.target.value)}><NativeSelectOption value="">Choose a compatible recipe</NativeSelectOption>{compatibleRecipes.map(item => <NativeSelectOption key={item.id} value={item.id}>{item.name}</NativeSelectOption>)}</NativeSelect></Field><Button variant="outline" disabled={pending || !attributed || !compatibleRecipes.some(item => item.id === recipeId)} onClick={proposeContract}>Propose contract</Button>{feed.config.enabled && <Button variant="outline" disabled={pending || !attributed} onClick={() => configure(false, feed.config.contract_id)}>Disable new deliveries</Button>}</div>
      </details>
    </>}
  </main>;
}
