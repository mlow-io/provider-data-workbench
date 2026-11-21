import type { ReactNode } from "react";
import { navigateWorkspace, workspaceHref } from "./workspaceNavigation";
import "./workbench-shell.css";

const daily = [
  { view: "work", label: "Work queue", detail: "Investigate and follow up", mark: "01" },
  { view: "intake", label: "Receive data", detail: "Upload, map and review", mark: "02" },
  { view: "feeds", label: "Deliveries", detail: "Review recurring datasets", mark: "03" },
  { view: "reconciliation", label: "Provider records", detail: "Link identities and compare", mark: "04" },
];
const tools = [
  { view: "sources", label: "Sources", detail: "Capture and source history" },
  { view: "qa", label: "Legacy QA", detail: "Original batch review" },
  { view: "remediation", label: "Corrections", detail: "Original correction loop" },
];

export function WorkbenchShell({ workspace, children }: { workspace: string; children: ReactNode }) {
  const current = [...daily, ...tools].find(item => item.view === workspace)!;
  function link(item: { view: string; label: string; detail: string; mark?: string }) {
    return <a key={item.view} href={workspaceHref(item.view)} aria-current={workspace === item.view ? "page" : undefined}
      onClick={event => {
        if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
          event.preventDefault();
          navigateWorkspace(item.view);
        }
      }}>
      {item.mark && <span className="wb-nav-number" aria-hidden="true">{item.mark}</span>}
      <span><span className="wb-nav-label">{item.label}</span><small aria-hidden="true">{item.detail}</small></span>
    </a>;
  }
  return <div className="wb-app">
    <a className="wb-skip" href="#workspace-content">Skip to workspace</a>
    <aside className="wb-sidebar">
      <div className="wb-brand"><span className="wb-brand-mark" aria-hidden="true">pd<span> / </span></span><strong>Provider Directory<span>Workbench</span></strong></div>
      <nav aria-label="Workbench navigation">
        <p className="wb-nav-heading">Daily work</p>
        <div className="wb-nav-group">{daily.map(link)}</div>
        <p className="wb-nav-heading">Sources &amp; supporting tools</p>
        <div className="wb-nav-group wb-tools">{tools.map(link)}</div>
      </nav>
      <div className="wb-local"><span aria-hidden="true">●</span> Local workspace<small>Decisions and evidence are retained here.</small></div>
    </aside>
    <div className="wb-content">
      <header className="wb-context"><span>Provider operations <span aria-hidden="true">/</span> <strong>{current.label}</strong></span><span className="wb-local-label">Single-user workspace</span></header>
      <div id="workspace-content" tabIndex={-1}>{children}</div>
    </div>
  </div>;
}
